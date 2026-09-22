from functools import wraps
from flask import abort, redirect, url_for, flash, request
from flask_login import current_user
from app.models.user import Role


def role_required(*allowed_roles: str):
    """
    Ensure user is authenticated, active, and has one of the allowed roles.
    SUPER_ADMIN always has access to all administrative/staff routes.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                # Redirect to staff login if attempting to access staff/admin routes
                flash("Please log in with your staff account to access this section.", "warning")
                return redirect(url_for("auth.staff_login", next=request.url))
            
            # Check account active state
            if not getattr(current_user, "is_active", True):
                flash("Your account has been deactivated. Please contact the administrator.", "danger")
                return redirect(url_for("auth.logout"))

            # Super admin has universal bypass for staff roles
            if current_user.role == Role.SUPER_ADMIN:
                return f(*args, **kwargs)

            if current_user.role not in allowed_roles:
                abort(403)
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Shorthand decorator for Super Admin and Owner/Admin only."""
    return role_required(Role.SUPER_ADMIN, Role.ADMIN)(f)


def super_admin_only(f):
    """Shorthand decorator for Super Admin only."""
    return role_required(Role.SUPER_ADMIN)(f)


def staff_required(f):
    """Requires any authenticated staff role."""
    return role_required(*Role.STAFF_ROLES)(f)


def customer_required(f):
    """Ensure user is an authenticated customer."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in with your mobile number to continue.", "info")
            return redirect(url_for("auth.customer_login", next=request.url))
        
        if getattr(current_user, "role", None) != "CUSTOMER":
            # Staff attempting to access customer-only page (or vice-versa)
            flash("Please log in as a customer to view customer bookings.", "warning")
            return redirect(url_for("auth.customer_login", next=request.url))

        if not getattr(current_user, "is_active", True):
            flash("Your account is currently disabled.", "danger")
            return redirect(url_for("auth.logout"))

        return f(*args, **kwargs)
    return decorated_function


def content_permission_required(f):
    """Require Content Management permission for a staff account."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.staff_login", next=request.url))
        if not getattr(current_user, "is_active", True):
            flash("Your account has been deactivated. Please contact the administrator.", "danger")
            return redirect(url_for("auth.logout"))
        if not current_user.has_permission("CONTENT_MANAGEMENT"):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
