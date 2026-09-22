from datetime import datetime, date
from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.booking import Booking, BookingStatus
from app.models.user import User, Role
from app.models.commission import CommissionRecord, CommissionStatus
from app.models.feedback import Feedback, Complaint, FeedbackStatus, ComplaintPriority
from app.services.booking_service import BookingService
from app.services.payment_service import PaymentService
from app.services.qr_service import QRService
from app.services.settings_service import SettingsService
from app.services.notification_service import NotificationService
from app.utils.decorators import customer_required

customer_bp = Blueprint("customer", __name__)


@customer_bp.route("/dashboard")
@customer_required
def dashboard():
    """Customer account dashboard displaying bookings segmented by status."""
    bookings = Booking.query.filter_by(customer_id=current_user.id).order_by(
        Booking.booking_date.desc()
    ).all()

    today = date.today()
    upcoming = [b for b in bookings if b.booking_date >= today and b.status == BookingStatus.CONFIRMED]
    completed = [b for b in bookings if b.booking_date < today or b.status == BookingStatus.COMPLETED]
    cancelled = [b for b in bookings if b.status == BookingStatus.CANCELLED]
    pending = [b for b in bookings if b.status == BookingStatus.PENDING_PAYMENT and b.booking_date >= today]

    return render_template(
        "customer/dashboard.html",
        upcoming=upcoming,
        completed=completed,
        cancelled=cancelled,
        pending=pending,
    )


@customer_bp.route("/book", methods=["GET", "POST"])
@customer_required
def book():
    """
    Customer Booking Flow:
    Step 1: Dedicated Availability Calendar
    Step 2: Guest details form for selected date
    """
    if request.method == "POST":
        date_str = request.form.get("booking_date")
        guest_count = request.form.get("num_people") or request.form.get("guest_count", "1")
        name = request.form.get("customer_name") or current_user.name or ""
        phone = request.form.get("customer_phone") or current_user.phone
        special_requests = request.form.get("special_requests")
        partner_code = request.form.get("partner_code", "").strip()
        staff_partner_id = None
        if partner_code and SettingsService.get_bool("partner_referral_links_enabled", True):
            partner = User.query.filter(User.staff_id == partner_code, User.role == Role.STAFF_PARTNER, User.is_active.is_(True)).first()
            if partner:
                staff_partner_id = partner.id

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            flash("Please choose a valid booking date.", "danger")
            return redirect(url_for("customer.book"))

        try:
            num_people = int(guest_count)
        except ValueError:
            num_people = 1

        booking, msg = BookingService.create_customer_booking(
            customer_id=current_user.id,
            booking_date=target_date,
            customer_name=name,
            customer_phone=phone,
            num_people=num_people,
            special_requests=special_requests,
            staff_partner_id=staff_partner_id,
        )

        if not booking:
            flash(msg, "danger")
            price = BookingService.calculate_price_for_date(target_date)
            return render_template(
                "customer/book.html",
                step=2,
                selected_date=date_str,
                target_date=target_date,
                price=price,
                is_weekend=target_date.weekday() >= 5,
                partner_code=partner_code,
            )

        # Update customer profile name if empty
        if name and not current_user.name:
            current_user.name = name
            db.session.commit()

        # Step 3: Proceed to Review Booking
        return redirect(url_for("customer.review_booking", booking_uid=booking.booking_uid))

    selected_date_str = request.args.get("date", "").strip()
    partner_code = request.args.get("partner", "").strip()
    if selected_date_str:
        try:
            target_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
            available, msg = BookingService.is_date_available(target_date)
            if not available:
                flash(msg, "warning")
                return redirect(url_for("customer.book"))
            price = BookingService.calculate_price_for_date(target_date)
            return render_template(
                "customer/book.html",
                step=2,
                selected_date=selected_date_str,
                target_date=target_date,
                price=price,
                is_weekend=target_date.weekday() >= 5,
                partner_code=partner_code,
            )
        except ValueError:
            pass

    # Step 1: Default to date selection calendar
    return render_template("customer/book.html", step=1, partner_code=partner_code)


@customer_bp.route("/review/<booking_uid>")
@customer_required
def review_booking(booking_uid: str):
    """Step 3: Review booking details and cancellation policy before checkout."""
    booking = Booking.query.filter_by(
        booking_uid=booking_uid, customer_id=current_user.id
    ).first_or_404()

    if booking.status == BookingStatus.CONFIRMED:
        return redirect(url_for("customer.confirmation", booking_uid=booking.booking_uid))

    policy_text = SettingsService.get("cancellation_policy_text")
    operating_hours = SettingsService.get("operating_hours", "8:00 AM – 8:00 PM")

    return render_template(
        "customer/review.html",
        booking=booking,
        policy_text=policy_text,
        operating_hours=operating_hours,
    )


@customer_bp.route("/pay/<booking_uid>", methods=["GET", "POST"])
@customer_required
def pay(booking_uid: str):
    """
    Payment Checkout Screen:
    Displays Freedom Park details, date, hours, guests, price, and clear cancellation policy BEFORE payment.
    In development, uses SANDBOX payment simulation.
    """
    booking = Booking.query.filter_by(
        booking_uid=booking_uid, customer_id=current_user.id
    ).first_or_404()

    if booking.status == BookingStatus.CONFIRMED:
        return redirect(url_for("customer.confirmation", booking_uid=booking.booking_uid))

    if booking.status == BookingStatus.CANCELLED:
        flash("This booking has been cancelled and cannot be paid for.", "warning")
        return redirect(url_for("customer.dashboard"))

    if request.method == "POST":
        action = request.form.get("action", "pay_success")
        simulate_success = (action == "pay_success")

        success, msg = PaymentService.verify_sandbox_payment(
            booking=booking, simulate_success=simulate_success
        )

        if success:
            # Dispatch WhatsApp confirmation mock
            if booking.staff_partner_id and SettingsService.get_bool("partner_commission_enabled", True):
                existing_commission = CommissionRecord.query.filter_by(booking_id=booking.id).first()
                if not existing_commission:
                    db.session.add(CommissionRecord(
                        booking_id=booking.id,
                        staff_user_id=booking.staff_partner_id,
                        amount=SettingsService.get_decimal("default_commission", Decimal("500.00")),
                        status=CommissionStatus.PENDING,
                    ))
                    db.session.commit()

            NotificationService.send_whatsapp_booking_confirmation(
                recipient_phone=booking.customer_phone,
                booking_uid=booking.booking_uid,
                booking_date=str(booking.booking_date),
                num_people=booking.num_people,
                amount=str(booking.amount),
                customer_name=booking.customer_name,
            )
            flash("Sandbox payment verified! Your booking is confirmed.", "success")
            return redirect(url_for("customer.confirmation", booking_uid=booking.booking_uid))
        else:
            flash(msg, "danger")
            return redirect(url_for("customer.dashboard"))

    policy_text = SettingsService.get("cancellation_policy_text")
    return render_template("customer/pay.html", booking=booking, policy_text=policy_text)


@customer_bp.route("/confirmation/<booking_uid>")
@customer_required
def confirmation(booking_uid: str):
    """Booking Confirmation Page with QR code and ticket pass."""
    booking = Booking.query.filter_by(
        booking_uid=booking_uid, customer_id=current_user.id
    ).first_or_404()

    qr_data_uri = QRService.generate_booking_qr_svg_uri(booking.booking_uid)
    return render_template("customer/confirmation.html", booking=booking, qr_data_uri=qr_data_uri)


@customer_bp.route("/pass/<booking_uid>")
@customer_required
def digital_pass(booking_uid: str):
    """Clean mobile digital pass optimized for display on arrival at park gates."""
    booking = Booking.query.filter_by(
        booking_uid=booking_uid, customer_id=current_user.id
    ).first_or_404()

    qr_data_uri = QRService.generate_booking_qr_svg_uri(booking.booking_uid)
    return render_template("customer/digital_pass.html", booking=booking, qr_data_uri=qr_data_uri)


@customer_bp.route("/cancel/<booking_uid>", methods=["POST"])
@customer_required
def cancel_booking(booking_uid: str):
    """Customer self-cancellation adhering to configured cancellation policy."""
    booking = Booking.query.filter_by(
        booking_uid=booking_uid, customer_id=current_user.id
    ).first_or_404()

    reason = request.form.get("reason", "Cancelled by customer")
    success, msg = BookingService.cancel_booking(
        booking_id=booking.id,
        reason=reason,
        cancelled_by_user_id=None,
        is_park_cancellation=False,
    )
    if success:
        flash(msg, "info")
    else:
        flash(msg, "danger")
    return redirect(url_for("customer.dashboard"))


@customer_bp.route("/feedback/<booking_uid>", methods=["GET", "POST"])
@customer_required
def submit_feedback(booking_uid: str):
    """Submit post-visit feedback with 1-5 star rating and optional photo."""
    booking = Booking.query.filter_by(
        booking_uid=booking_uid, customer_id=current_user.id
    ).first_or_404()

    if request.method == "POST":
        rating = int(request.form.get("rating", "5"))
        category = request.form.get("category", "Positive Feedback")
        message = request.form.get("message", "")

        feedback = Feedback(
            customer_id=current_user.id,
            booking_id=booking.id,
            category=category,
            rating=rating,
            message=message,
        )
        db.session.add(feedback)
        db.session.commit()
        flash("Thank you for sharing your feedback with Freedom Park!", "success")
        return redirect(url_for("customer.dashboard"))

    return render_template("customer/feedback.html", booking=booking)


@customer_bp.route("/complaint", methods=["GET", "POST"])
@customer_required
def submit_complaint():
    """File a formal complaint for park management investigation."""
    if request.method == "POST":
        booking_uid = request.form.get("booking_uid", "").strip()
        category = request.form.get("category", "Facility Problem")
        priority = request.form.get("priority", ComplaintPriority.NORMAL)
        message = request.form.get("message", "")

        booking = None
        if booking_uid:
            booking = Booking.query.filter_by(booking_uid=booking_uid).first()

        complaint = Complaint(
            customer_id=current_user.id,
            booking_id=booking.id if booking else None,
            category=category,
            priority=priority,
            message=message,
        )
        db.session.add(complaint)
        db.session.commit()
        flash("Your complaint has been submitted. Park management will review it promptly.", "warning")
        return redirect(url_for("customer.dashboard"))

    return render_template("customer/complaint.html")
