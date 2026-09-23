from flask import Blueprint, current_app, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from authlib.integrations.base_client import OAuthError
import re
import time
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService
from app.models.audit_log import AuditAction
from app.models.user import Customer, CustomerIdentity, Role
from app.extensions import db, oauth
from app.utils.helpers import is_safe_redirect_url, normalize_phone

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/staff-login", methods=["GET", "POST"])
def staff_login():
    """Secure login endpoint for internal staff, security, owner and system administration."""
    if current_user.is_authenticated:
        if getattr(current_user, "role", None) == Role.SUPER_ADMIN:
            return redirect(url_for("admin.super_dashboard"))
        elif getattr(current_user, "role", None) == Role.ADMIN:
            return redirect(url_for("admin.dashboard"))
        elif getattr(current_user, "role", None) == Role.STAFF_PARTNER:
            return redirect(url_for("staff.dashboard"))
        elif getattr(current_user, "role", None) == Role.SECURITY:
            return redirect(url_for("security_bp.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = "remember" in request.form

        user, err = AuthService.authenticate_staff(username, password)
        if not user:
            flash(err, "danger")
            AuditService.log(
                action=AuditAction.LOGIN_FAILED,
                target_type="user",
                details={"username": username, "reason": err},
            )
            return render_template("auth/staff_login.html")

        login_user(user, remember=remember)
        AuditService.log(
            action=AuditAction.LOGIN_SUCCESS,
            target_type="user",
            target_id=user.id,
            user_id=user.id,
            user_role=user.role,
        )

        next_page = request.args.get("next")
        if next_page and is_safe_redirect_url(next_page):
            return redirect(next_page)

        # Redirect according to role
        if user.is_super_admin:
            return redirect(url_for("admin.super_dashboard"))
        elif user.role == Role.ADMIN:
            return redirect(url_for("admin.dashboard"))
        elif user.is_staff_partner:
            return redirect(url_for("staff.dashboard"))
        elif user.is_security:
            return redirect(url_for("security_bp.dashboard"))
        return redirect(url_for("public.index"))

    return render_template("auth/staff_login.html")


@auth_bp.route("/customer-login", methods=["GET", "POST"])
def customer_login():
    """Simple customer identification using name + mobile number; no OTP required."""
    if current_user.is_authenticated and getattr(current_user, "role", None) == "CUSTOMER":
        return redirect(url_for("customer.dashboard"))

    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        if request.form.get("step") == "verify":
            customer, error = AuthService.verify_customer_otp(
                phone, request.form.get("otp", "")
            )
            if not customer:
                flash(error, "danger")
                return render_template("auth/customer_login.html", phone=phone)
            login_user(customer, remember=True)
            return redirect(url_for("customer.dashboard"))

        name = request.form.get("name", "").strip()
        clean_phone = normalize_phone(phone)

        if not clean_phone or not re.fullmatch(r"[6-9]\d{9}", clean_phone):
            flash("Please enter a valid 10-digit Indian mobile number.", "danger")
            return render_template("auth/customer_login.html", phone=phone)
        if not name:
            flash("Please enter your name.", "danger")
            return render_template("auth/customer_login.html", phone=phone)

        from app.models.user import Customer
        from app.extensions import db
        customer = Customer.query.filter_by(phone=clean_phone).first()
        if not customer:
            customer = Customer(phone=clean_phone, name=name)
            db.session.add(customer)
        elif name and customer.name != name:
            customer.name = name
        db.session.commit()

        login_user(customer, remember=True)
        flash(f"Welcome to Freedom Park, {customer.name}!", "success")
        next_page = request.args.get("next")
        if next_page and is_safe_redirect_url(next_page):
            return redirect(next_page)
        return redirect(url_for("customer.dashboard"))

    return render_template("auth/customer_login.html")


@auth_bp.route("/google/login")
def google_login():
    """Start Google OpenID Connect authentication for customers."""
    if current_user.is_authenticated and getattr(current_user, "role", None) == "CUSTOMER":
        return redirect(url_for("customer.dashboard"))

    client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET")
    redirect_uri = current_app.config.get("GOOGLE_REDIRECT_URI")
    if not client_id or not client_secret or not redirect_uri:
        flash("Google Sign-In is not configured yet.", "warning")
        return redirect(url_for("auth.customer_login"))

    next_page = request.args.get("next")
    session["google_next"] = next_page if next_page and is_safe_redirect_url(next_page) else None
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/google/callback")
def google_callback():
    """Validate Google OIDC claims and establish a Flask-Login customer session."""
    try:
        token = oauth.google.authorize_access_token(
            claims_options={
                "iss": {"values": ["https://accounts.google.com"]},
                "aud": {"values": [current_app.config.get("GOOGLE_CLIENT_ID")]},
            }
        )
        claims = token.get("userinfo")
        if not claims or not claims.get("sub"):
            raise OAuthError(description="Google did not return a valid identity.")
        if claims.get("iss") != "https://accounts.google.com":
            raise OAuthError(description="Invalid Google issuer.")
        audience = claims.get("aud")
        if audience != current_app.config.get("GOOGLE_CLIENT_ID") and not (
            isinstance(audience, list)
            and current_app.config.get("GOOGLE_CLIENT_ID") in audience
        ):
            raise OAuthError(description="Invalid Google audience.")
        if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] <= time.time():
            raise OAuthError(description="Google identity has no expiry.")
    except Exception:
        session.pop("google_next", None)
        flash("Google Sign-In could not be completed. Please try again.", "danger")
        return redirect(url_for("auth.customer_login")), 400

    provider_subject = str(claims["sub"])
    identity = CustomerIdentity.query.filter_by(
        provider="google", provider_subject=provider_subject
    ).first()
    if identity:
        customer = identity.customer
    else:
        customer = Customer(
            phone=None,
            name=claims.get("name") or claims.get("email") or "Google customer",
        )
        identity = CustomerIdentity(
            customer=customer,
            provider="google",
            provider_subject=provider_subject,
            email=claims.get("email"),
            email_verified=bool(claims.get("email_verified", False)),
        )
        db.session.add(customer)
        db.session.add(identity)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            existing = CustomerIdentity.query.filter_by(
                provider="google", provider_subject=provider_subject
            ).first()
            if not existing:
                flash("Google Sign-In could not create your account.", "danger")
                return redirect(url_for("auth.customer_login")), 400
            customer = existing.customer

    login_user(customer, remember=True)
    next_page = session.pop("google_next", None)
    if next_page and is_safe_redirect_url(next_page):
        return redirect(next_page)
    return redirect(url_for("customer.dashboard"))


@auth_bp.route("/logout")
@login_required
def logout():
    """Terminate current user session."""
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("public.index"))
