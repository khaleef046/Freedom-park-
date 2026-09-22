from datetime import date, datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models.booking import Booking, BookingStatus
from app.models.equipment import (
    Equipment, EquipmentChecklist, EquipmentChecklistItem,
    EquipmentReport, ChecklistType, EquipmentItemStatus
)
from app.models.user import Role
from app.services.notification_service import NotificationService
from app.utils.decorators import role_required

security_bp = Blueprint("security_bp", __name__)


@security_bp.route("/")
@security_bp.route("/dashboard")
@role_required(Role.SECURITY, Role.ADMIN, Role.SUPER_ADMIN)
def dashboard():
    """Security dashboard: Today's active bookings, guest entry, and equipment check."""
    today = date.today()
    today_bookings = Booking.query.filter_by(
        booking_date=today, status=BookingStatus.CONFIRMED
    ).all()

    # Active equipment items available
    equipment_items = Equipment.query.filter_by(is_active=True).all()

    return render_template(
        "security/dashboard.html",
        today=today,
        bookings=today_bookings,
        equipment_items=equipment_items,
    )


@security_bp.route("/checkin/<int:booking_id>", methods=["GET", "POST"])
@role_required(Role.SECURITY, Role.ADMIN, Role.SUPER_ADMIN)
def checkin(booking_id: int):
    """Guest entry check-in and equipment handover checklist."""
    booking = db.get_or_404(Booking, booking_id)
    equipment_list = Equipment.query.filter_by(is_active=True).all()

    if request.method == "POST":
        notes = request.form.get("notes", "")

        checklist = EquipmentChecklist(
            booking_id=booking.id,
            type=ChecklistType.CHECK_IN,
            completed_by=current_user.id,
            notes=notes,
        )
        db.session.add(checklist)
        db.session.flush()

        for eq in equipment_list:
            qty_field = f"qty_{eq.id}"
            actual_qty = max(0, int(request.form.get(qty_field, eq.quantity)))
            item = EquipmentChecklistItem(
                checklist_id=checklist.id,
                equipment_id=eq.id,
                expected_qty=eq.quantity,
                actual_qty=actual_qty,
                status=EquipmentItemStatus.PRESENT,
            )
            db.session.add(item)

        db.session.commit()
        flash(f"Check-in and equipment handover for booking {booking.booking_uid} completed!", "success")
        return redirect(url_for("security_bp.dashboard"))

    return render_template(
        "security/checkin.html",
        booking=booking,
        equipment_list=equipment_list,
    )


@security_bp.route("/checkout/<int:booking_id>", methods=["GET", "POST"])
@role_required(Role.SECURITY, Role.ADMIN, Role.SUPER_ADMIN)
def checkout(booking_id: int):
    """Guest departure checkout, equipment return verification, and damage/loss reporting."""
    booking = db.get_or_404(Booking, booking_id)
    equipment_list = Equipment.query.filter_by(is_active=True).all()

    if request.method == "POST":
        notes = request.form.get("notes", "")

        checklist = EquipmentChecklist(
            booking_id=booking.id,
            type=ChecklistType.CHECK_OUT,
            completed_by=current_user.id,
            notes=notes,
        )
        db.session.add(checklist)
        db.session.flush()

        has_incidents = False

        for eq in equipment_list:
            status_field = f"status_{eq.id}"
            actual_qty_field = f"qty_{eq.id}"
            item_status = request.form.get(status_field, EquipmentItemStatus.RETURNED)
            actual_qty = int(request.form.get(actual_qty_field, eq.quantity))
            note = request.form.get(f"note_{eq.id}", "")

            item = EquipmentChecklistItem(
                checklist_id=checklist.id,
                equipment_id=eq.id,
                expected_qty=eq.quantity,
                actual_qty=actual_qty,
                status=item_status,
                note=note,
            )
            db.session.add(item)

            if item_status in (EquipmentItemStatus.MISSING, EquipmentItemStatus.DAMAGED):
                has_incidents = True
                missing_qty = max(1, eq.quantity - actual_qty)
                report = EquipmentReport(
                    booking_id=booking.id,
                    equipment_id=eq.id,
                    quantity=missing_qty,
                    status=item_status,
                    note=note or f"{item_status} reported during checkout.",
                    reported_by=current_user.id,
                )
                db.session.add(report)

        if has_incidents:
            NotificationService.notify_admins(
                title="Equipment Incident Reported",
                message=f"Missing or damaged equipment reported during checkout for booking {booking.booking_uid}.",
                priority="IMPORTANT",
                reference_type="equipment",
                reference_id=booking.id,
            )

        # Mark booking as COMPLETED
        booking.status = BookingStatus.COMPLETED
        db.session.commit()

        flash(f"Checkout completed for {booking.booking_uid}. Status updated to Completed.", "success")
        return redirect(url_for("security_bp.dashboard"))

    return render_template(
        "security/checkout.html",
        booking=booking,
        equipment_list=equipment_list,
    )
