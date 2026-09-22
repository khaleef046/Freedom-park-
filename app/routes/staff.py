from datetime import datetime, date
from decimal import Decimal
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func
from app.extensions import db
from app.models.booking import Booking, BookingStatus, BookingSource
from app.models.commission import CommissionRecord, CommissionStatus
from app.models.cancellation import CancellationRequest, CancellationRequestStatus
from app.models.feedback import StaffSupportTicket
from app.models.user import Role
from app.services.booking_service import BookingService
from app.services.notification_service import NotificationService
from app.services.settings_service import SettingsService
from app.utils.decorators import role_required

staff_bp = Blueprint("staff", __name__)


@staff_bp.route("/")
@staff_bp.route("/dashboard")
@role_required(Role.STAFF_PARTNER, Role.ADMIN, Role.SUPER_ADMIN)
def dashboard():
    """Staff Partner dashboard with personal performance and commission metrics."""
    staff_id = current_user.id
    
    # Bookings made by this partner
    bookings = Booking.query.filter_by(staff_partner_id=staff_id).order_by(
        Booking.booking_date.desc()
    ).all()

    # Commission calculations
    total_commission = db.session.query(func.sum(CommissionRecord.amount)).filter(
        CommissionRecord.staff_user_id == staff_id,
        CommissionRecord.status.in_([CommissionStatus.APPROVED, CommissionStatus.PAID]),
    ).scalar() or Decimal("0.00")

    pending_commission = db.session.query(func.sum(CommissionRecord.amount)).filter(
        CommissionRecord.staff_user_id == staff_id,
        CommissionRecord.status == CommissionStatus.PENDING,
    ).scalar() or Decimal("0.00")

    paid_commission = db.session.query(func.sum(CommissionRecord.amount)).filter(
        CommissionRecord.staff_user_id == staff_id,
        CommissionRecord.status == CommissionStatus.PAID,
    ).scalar() or Decimal("0.00")

    successful_count = Booking.query.filter_by(staff_partner_id=staff_id, status="CONFIRMED").count()
    if successful_count <= 2: partner_level = "Starter"
    elif successful_count <= 5: partner_level = "Active Partner"
    elif successful_count <= 10: partner_level = "Top Partner"
    else: partner_level = "Gold Partner"
    referral_enabled = SettingsService.get_bool("partner_referral_links_enabled", True)
    referral_link = url_for("customer.book", partner=current_user.staff_id or current_user.formatted_staff_id, _external=False)

    return render_template(
        "staff/dashboard.html",
        bookings=bookings,
        total_commission=total_commission,
        pending_commission=pending_commission,
        paid_commission=paid_commission,
        partner_level=partner_level,
        successful_count=successful_count,
        referral_enabled=referral_enabled,
        referral_link=referral_link,
    )


@staff_bp.route("/calendar")
@role_required(Role.STAFF_PARTNER, Role.ADMIN, Role.SUPER_ADMIN)
def calendar_view():
    """Staff Partner availability calendar. Booked dates reveal customer details but not cancellation controls."""
    return render_template("staff/calendar.html")


@staff_bp.route("/book", methods=["GET", "POST"])
@role_required(Role.STAFF_PARTNER, Role.ADMIN, Role.SUPER_ADMIN)
def create_booking():
    """Staff Partner creates booking on behalf of customer."""
    if request.method == "POST":
        date_str = request.form.get("booking_date")
        customer_name = request.form.get("customer_name")
        customer_phone = request.form.get("customer_phone")
        guest_count = request.form.get("num_people", "1")
        notes = request.form.get("notes")

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            flash("Please enter a valid date.", "danger")
            return redirect(url_for("staff.create_booking"))

        try:
            num_people = int(guest_count)
        except ValueError:
            num_people = 1

        booking, msg = BookingService.create_manual_booking(
            booking_date=target_date,
            customer_name=customer_name,
            customer_phone=customer_phone,
            num_people=num_people,
            source=BookingSource.STAFF_PARTNER,
            created_by_user_id=current_user.id,
            staff_partner_id=current_user.id,
            notes=notes,
        )

        if not booking:
            flash(msg, "danger")
            return render_template("staff/book.html", prefill_date=date_str)

        NotificationService.notify_admins(
            title="New Staff Partner Booking",
            message=f"{current_user.full_name} booked {booking.booking_date} for {booking.customer_name}.",
            reference_type="booking",
            reference_id=booking.id,
        )

        flash(f"Booking {booking.booking_uid} confirmed! Commission record registered.", "success")
        return redirect(url_for("staff.dashboard"))

    prefill_date = request.args.get("date", "")
    return render_template("staff/book.html", prefill_date=prefill_date)


@staff_bp.route("/request-cancellation/<int:booking_id>", methods=["GET", "POST"])
@role_required(Role.STAFF_PARTNER, Role.ADMIN, Role.SUPER_ADMIN)
def request_cancellation(booking_id: int):
    """Staff Partners cannot cancel directly; they submit a request to Owner/Admin."""
    booking = Booking.query.filter_by(
        id=booking_id, staff_partner_id=current_user.id
    ).first_or_404()

    if request.method == "POST":
        reason = request.form.get("reason", "").strip()
        if not reason:
            flash("Please state the reason for requesting cancellation.", "warning")
            return render_template("staff/request_cancellation.html", booking=booking)

        req = CancellationRequest(
            booking_id=booking.id,
            requested_by=current_user.id,
            reason=reason,
            status=CancellationRequestStatus.PENDING,
        )
        db.session.add(req)
        db.session.commit()

        NotificationService.notify_admins(
            title="Cancellation Request from Staff Partner",
            message=f"{current_user.full_name} requested cancellation for booking {booking.booking_uid}: {reason}",
            notification_type="CANCELLATION",
            reference_type="cancellation_request",
            reference_id=req.id,
        )

        flash("Cancellation request submitted. Owner/Admin will review it.", "info")
        return redirect(url_for("staff.dashboard"))

    return render_template("staff/request_cancellation.html", booking=booking)


@staff_bp.route("/support", methods=["GET", "POST"])
@role_required(Role.STAFF_PARTNER, Role.ADMIN, Role.SUPER_ADMIN)
def support():
    """Submit internal support ticket to Admin."""
    if request.method == "POST":
        category = request.form.get("category", "Booking Problem")
        message = request.form.get("message", "").strip()

        ticket = StaffSupportTicket(
            staff_user_id=current_user.id,
            category=category,
            message=message,
        )
        db.session.add(ticket)
        db.session.commit()
        NotificationService.notify_admins(
            title="New Staff Support Request",
            message=f"{current_user.full_name}: {category} — {message}",
            notification_type="SUPPORT",
            reference_type="staff_support",
            reference_id=ticket.id,
        )
        flash("Support request submitted to Admin.", "success")
        return redirect(url_for("staff.dashboard"))

    tickets = StaffSupportTicket.query.filter_by(staff_user_id=current_user.id).order_by(
        StaffSupportTicket.created_at.desc()
    ).all()
    return render_template("staff/support.html", tickets=tickets)


@staff_bp.route("/share-availability")
@role_required(Role.STAFF_PARTNER, Role.ADMIN, Role.SUPER_ADMIN)
def share_availability():
    """Return a WhatsApp-ready share page for currently available dates."""
    today = date.today()
    end = today + __import__("datetime").timedelta(days=SettingsService.get_int("booking_window_days", 30))
    available = []
    d = today
    while d <= end:
        if BookingService.is_date_available(d):
            available.append(d)
        d += __import__("datetime").timedelta(days=1)
    return render_template("staff/share_availability.html", available=available[:20], referral_link=url_for("customer.book", partner=current_user.staff_id or current_user.formatted_staff_id, _external=True))
