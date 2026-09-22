from datetime import datetime, date
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.booking import Booking, BookingStatus, BlockedDate
from app.models.notification import Notification
from app.services.booking_service import BookingService
from app.services.settings_service import SettingsService

api_bp = Blueprint("api", __name__)


@api_bp.route("/calendar")
def calendar_feed():
    """
    JSON calendar feed for interactive frontend booking calendar.
    Parameters: year (int), month (int).
    Returns list of day objects with date, status (AVAILABLE, BOOKED, BLOCKED, PAST), and price.
    """
    today = date.today()
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
    except (ValueError, TypeError):
        year, month = today.year, today.month

    days_data = BookingService.get_calendar_month_data(year, month)
    return jsonify({
        "year": year,
        "month": month,
        "days": days_data,
    })


@api_bp.route("/check-date")
def check_date():
    """
    Server-side authoritative date verification API.
    Returns availability status and authoritative calculated price.
    """
    date_str = request.args.get("date")
    if not date_str:
        return jsonify({"available": False, "message": "Date parameter is required."}), 400

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"available": False, "message": "Invalid date format. Expected YYYY-MM-DD."}), 400

    available, msg = BookingService.is_date_available(target_date)
    price = float(BookingService.calculate_price_for_date(target_date))

    return jsonify({
        "date": date_str,
        "available": available,
        "message": msg,
        "price": price,
        "is_weekend": target_date.weekday() >= 5,
        "operating_hours": SettingsService.get("operating_hours", "8:00 AM – 8:00 PM"),
        "max_capacity": SettingsService.get_int("max_capacity", 100),
    })


@api_bp.route("/notifications/unread")
@login_required
def unread_notifications():
    """Returns unread notification count and list for staff/admin header."""
    notifs = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).order_by(Notification.created_at.desc()).limit(10).all()

    return jsonify({
        "count": len(notifs),
        "notifications": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "priority": n.priority,
                "created_at": n.created_at.strftime("%b %d, %H:%M"),
            }
            for n in notifs
        ],
    })


@api_bp.route("/notifications/mark-read/<int:id>", methods=["POST"])
@login_required
def mark_notification_read(id: int):
    """Mark a notification as read."""
    notif = Notification.query.filter_by(id=id, user_id=current_user.id).first()
    if notif:
        notif.is_read = True
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Notification not found"}), 404


@api_bp.route("/calendar/booking-details")
@login_required
def calendar_booking_details():
    """Return booking details for authenticated staff calendar users."""
    if getattr(current_user, "role", None) not in ("SUPER_ADMIN", "ADMIN", "STAFF_PARTNER", "SECURITY"):
        return jsonify({"booking": None}), 403
    date_str = request.args.get("date", "")
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"booking": None, "message": "Invalid date"}), 400
    booking = Booking.query.filter(Booking.booking_date == target, Booking.status.in_(BookingStatus.ACTIVE_STATUSES)).first()
    if not booking:
        return jsonify({"booking": None})
    return jsonify({"booking": {"id": booking.id, "booking_uid": booking.booking_uid, "customer_name": booking.customer_name, "customer_phone": booking.customer_phone, "num_people": booking.num_people, "amount": str(booking.amount), "status": booking.status, "staff_partner_id": booking.staff_partner_id}})
