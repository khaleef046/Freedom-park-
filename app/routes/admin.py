from datetime import datetime, date, timedelta
import json
from decimal import Decimal
from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file
from flask_login import login_required, current_user
from sqlalchemy import func
from app.extensions import db
from app.models.booking import Booking, BlockedDate, BookingStatus, BookingSource
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, Role
from app.models.feedback import Feedback, Complaint, FeedbackStatus, StaffSupportTicket
from app.models.commission import CommissionRecord, CommissionStatus
from app.models.notification import Notification
from app.models.audit_log import AuditLog, AuditAction
from app.models.cancellation import CancellationRequest, CancellationRequestStatus
from app.models.equipment import Equipment, EquipmentReport, EquipmentChecklist
from app.services.booking_service import BookingService
from app.services.settings_service import SettingsService
from app.services.audit_service import AuditService
from app.utils.decorators import admin_required, super_admin_only
from io import BytesIO
from openpyxl import Workbook

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/homepage", methods=["GET", "POST"])
@admin_required
def homepage_editor():
    """Edit the public homepage hero/branding text without touching source code."""
    editable = [
        "brand_subtitle", "hero_kicker", "hero_title_line1", "hero_title_line2",
        "hero_subtitle", "hero_background_path", "gallery_heading", "gallery_subtitle",
    ]
    if request.method == "POST":
        for key in editable:
            if key in request.form:
                SettingsService.set(key, request.form.get(key, "").strip(), current_user.id)
        AuditService.log(
            action="HOMEPAGE_UPDATED",
            target_type="homepage",
            details="Homepage hero and gallery presentation updated from admin console",
            user_id=current_user.id,
        )
        flash("Homepage settings saved successfully!", "success")
        return redirect(url_for("admin.homepage_editor"))

    homepage = {key: SettingsService.get(key) for key in editable}
    return render_template("admin/homepage.html", homepage=homepage)


@admin_bp.route("/")
@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    """Business Command Center for Owner (M. Asrar Ul Haq) and System Administrator."""
    today = date.today()

    # Core statistics
    today_booking = Booking.query.filter_by(
        booking_date=today, status=BookingStatus.CONFIRMED
    ).first()

    today_checklist = None
    if today_booking:
        today_checklist = EquipmentChecklist.query.filter_by(
            booking_id=today_booking.id, type="CHECK_IN"
        ).first()

    next_booking = Booking.query.filter(
        Booking.booking_date > today,
        Booking.status == BookingStatus.CONFIRMED,
    ).order_by(Booking.booking_date.asc()).first()

    total_bookings = Booking.query.filter_by(status=BookingStatus.CONFIRMED).count()
    total_cancelled = Booking.query.filter_by(status=BookingStatus.CANCELLED).count()

    total_revenue = db.session.query(func.sum(Booking.amount)).filter(
        Booking.status == BookingStatus.CONFIRMED
    ).scalar() or Decimal("0.00")

    # Booking source distribution
    source_stats = {
        src: Booking.query.filter_by(source=src, status=BookingStatus.CONFIRMED).count()
        for src in BookingSource.ALL
    }

    # Operational Alerts & Pending items
    pending_complaints = Complaint.query.filter_by(status="NEW").count()
    pending_cancellations = CancellationRequest.query.filter_by(status=CancellationRequestStatus.PENDING).count()
    pending_commissions = CommissionRecord.query.filter_by(status=CommissionStatus.PENDING).count()
    equipment_incidents = EquipmentReport.query.count()
    support_tickets = StaffSupportTicket.query.filter_by(status="NEW").count()

    # Recent items
    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(8).all()
    recent_feedback = Feedback.query.order_by(Feedback.created_at.desc()).limit(5).all()

    unread_notifications = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).order_by(Notification.created_at.desc()).limit(5).all()

    return render_template(
        "admin/dashboard.html",
        today=today,
        today_booking=today_booking,
        today_checklist=today_checklist,
        next_booking=next_booking,
        total_bookings=total_bookings,
        total_cancelled=total_cancelled,
        total_revenue=total_revenue,
        source_stats=source_stats,
        pending_complaints=pending_complaints,
        pending_cancellations=pending_cancellations,
        pending_commissions=pending_commissions,
        equipment_incidents=equipment_incidents,
        support_tickets=support_tickets,
        recent_bookings=recent_bookings,
        recent_feedback=recent_feedback,
        notifications=unread_notifications,
    )


@admin_bp.route("/bookings")
@admin_required
def bookings():
    """All bookings table with search, status filters, and source filters."""
    query = Booking.query

    # Search filter
    q = request.args.get("q", "").strip()
    if q:
        query = query.filter(
            (Booking.customer_name.ilike(f"%{q}%")) |
            (Booking.customer_phone.ilike(f"%{q}%")) |
            (Booking.booking_uid.ilike(f"%{q}%"))
        )

    # Status filter
    status_filter = request.args.get("status")
    if status_filter and status_filter in BookingStatus.ALL:
        query = query.filter_by(status=status_filter)

    # Source filter
    source_filter = request.args.get("source")
    if source_filter and source_filter in BookingSource.ALL:
        query = query.filter_by(source=source_filter)

    bookings_list = query.order_by(Booking.booking_date.desc()).limit(100).all()

    return render_template(
        "admin/bookings.html",
        bookings=bookings_list,
        search_query=q,
        current_status=status_filter,
        current_source=source_filter,
        statuses=BookingStatus.ALL,
        sources=BookingSource.ALL,
    )


@admin_bp.route("/bookings/export/<string:file_format>")
@admin_required
def export_bookings(file_format: str):
    """Download booking records as Excel (.xlsx) or CSV for admin reporting."""
    if file_format not in {"xlsx", "csv"}:
        return "Unsupported export format", 400

    query = Booking.query

    q = request.args.get("q", "").strip()
    if q:
        query = query.filter(
            (Booking.customer_name.ilike(f"%{q}%")) |
            (Booking.customer_phone.ilike(f"%{q}%")) |
            (Booking.booking_uid.ilike(f"%{q}%"))
        )

    status_filter = request.args.get("status")
    if status_filter and status_filter in BookingStatus.ALL:
        query = query.filter_by(status=status_filter)

    source_filter = request.args.get("source")
    if source_filter and source_filter in BookingSource.ALL:
        query = query.filter_by(source=source_filter)

    bookings_list = query.order_by(Booking.booking_date.desc(), Booking.id.desc()).all()
    headers = [
        "Booking ID", "Booking Date", "Customer Name", "Phone", "Guests",
        "Amount", "Status", "Source", "Notes", "Created At", "Updated At"
    ]

    rows = [
        [
            b.booking_uid,
            b.booking_date,
            b.customer_name,
            b.customer_phone,
            b.num_people,
            float(b.amount or 0),
            b.status,
            b.source,
            b.notes or "",
            b.created_at,
            b.updated_at,
        ]
        for b in bookings_list
    ]

    if file_format == "csv":
        import csv
        import io
        text_buffer = io.StringIO(newline="")
        writer = csv.writer(text_buffer, lineterminator="\n")
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
        output = BytesIO(text_buffer.getvalue().encode("utf-8-sig"))
        output.seek(0)
        return send_file(
            output,
            mimetype="text/csv; charset=utf-8",
            as_attachment=True,
            download_name="freedom_park_bookings.csv",
        )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Bookings"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    widths = [20, 16, 24, 18, 10, 14, 20, 18, 35, 22, 22]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + index)].width = width

    # Excel date/time cells should remain real date values.
    for cell in sheet["B"][1:]:
        cell.number_format = "yyyy-mm-dd"
    for column in ("J", "K"):
        for cell in sheet[column][1:]:
            cell.number_format = "yyyy-mm-dd hh:mm"
    for cell in sheet["F"][1:]:
        cell.number_format = '₹#,##0.00'

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="freedom_park_bookings.xlsx",
    )


@admin_bp.route("/calendar")
@admin_required
def calendar_view():
    """Interactive administrative calendar for booking overview and date locking."""
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)

    month_days = BookingService.get_calendar_month_data(year, month)
    
    # Map bookings for easy lookup
    bookings_in_month = Booking.query.filter(
        func.strftime("%Y-%m", Booking.booking_date) == f"{year:04d}-{month:02d}",
        Booking.status.in_(BookingStatus.ACTIVE_STATUSES),
    ).all()
    booking_map = {b.booking_date.isoformat(): b for b in bookings_in_month}

    # Blocked dates map
    blocked_in_month = BlockedDate.query.filter(
        func.strftime("%Y-%m", BlockedDate.blocked_date) == f"{year:04d}-{month:02d}"
    ).all()
    blocked_map = {bd.blocked_date.isoformat(): bd for bd in blocked_in_month}

    return render_template(
        "admin/calendar.html",
        year=year,
        month=month,
        month_days=month_days,
        booking_map=booking_map,
        blocked_map=blocked_map,
        today=today,
    )


@admin_bp.route("/manual-booking", methods=["GET", "POST"])
@admin_required
def manual_booking():
    """Create manual booking (for phone, WhatsApp, or direct walk-in inquiries)."""
    if request.method == "POST":
        date_str = request.form.get("booking_date")
        customer_name = request.form.get("customer_name")
        customer_phone = request.form.get("customer_phone")
        guest_count = request.form.get("num_people", "1")
        source = request.form.get("source", BookingSource.PHONE)
        notes = request.form.get("notes")
        custom_amount_str = request.form.get("custom_amount")

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            flash("Please enter a valid date.", "danger")
            return redirect(url_for("admin.manual_booking"))

        try:
            num_people = int(guest_count)
        except ValueError:
            num_people = 1

        custom_amount = None
        if custom_amount_str:
            try:
                custom_amount = Decimal(custom_amount_str)
            except Exception:
                custom_amount = None

        booking, msg = BookingService.create_manual_booking(
            booking_date=target_date,
            customer_name=customer_name,
            customer_phone=customer_phone,
            num_people=num_people,
            source=source,
            created_by_user_id=current_user.id,
            notes=notes,
            custom_amount=custom_amount,
        )

        if not booking:
            flash(msg, "danger")
            return render_template("admin/manual_booking.html", prefill_date=date_str)

        flash(f"Booking {booking.booking_uid} confirmed and date locked successfully!", "success")
        return redirect(url_for("admin.bookings"))

    prefill_date = request.args.get("date", "")
    return render_template(
        "admin/manual_booking.html",
        prefill_date=prefill_date,
        sources=BookingSource.ALL,
    )


@admin_bp.route("/lock-date", methods=["POST"])
@admin_required
def lock_date():
    """Emergency date lock by Admin / System Administrator."""
    date_str = request.form.get("date")
    reason = request.form.get("reason", "Maintenance / Park unavailable")

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        flash("Invalid date provided.", "danger")
        return redirect(url_for("admin.calendar_view"))

    success, msg = BookingService.lock_emergency_date(
        target_date=target_date, reason=reason, user_id=current_user.id
    )
    if success:
        flash(msg, "success")
    else:
        flash(msg, "danger")
    return redirect(url_for("admin.calendar_view"))


@admin_bp.route("/unlock-date", methods=["POST"])
@admin_required
def unlock_date():
    """Remove emergency lock on date."""
    date_str = request.form.get("date")
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        flash("Invalid date provided.", "danger")
        return redirect(url_for("admin.calendar_view"))

    success, msg = BookingService.unlock_date(target_date, current_user.id)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "danger")
    return redirect(url_for("admin.calendar_view"))


@admin_bp.route("/cancel-booking/<int:id>", methods=["POST"])
@admin_required
def cancel_booking(id: int):
    """Admin-initiated booking cancellation with reason and automatic refund policy."""
    reason = request.form.get("reason", "Cancelled by park admin")
    is_park_fault = "is_park_fault" in request.form

    success, msg = BookingService.cancel_booking(
        booking_id=id,
        reason=reason,
        cancelled_by_user_id=current_user.id,
        is_park_cancellation=is_park_fault,
    )
    if success:
        flash(msg, "info")
    else:
        flash(msg, "danger")
    return redirect(url_for("admin.bookings"))


@admin_bp.route("/pricing", methods=["GET", "POST"])
@admin_required
def pricing():
    """Manage dynamic pricing rules without code modification."""
    if request.method == "POST":
        weekday_price = request.form.get("weekday_price")
        weekend_price = request.form.get("weekend_price")

        if weekday_price:
            SettingsService.set("weekday_price", weekday_price, current_user.id)
        if weekend_price:
            SettingsService.set("weekend_price", weekend_price, current_user.id)

        AuditService.log(
            action="PRICE_CHANGED",
            target_type="setting",
            details={"weekday": weekday_price, "weekend": weekend_price},
            user_id=current_user.id,
        )
        flash("Pricing rules updated successfully!", "success")
        return redirect(url_for("admin.pricing"))

    weekday_val = SettingsService.get("weekday_price", "2000")
    weekend_val = SettingsService.get("weekend_price", "3000")
    return render_template(
        "admin/pricing.html",
        weekday_price=weekday_val,
        weekend_price=weekend_val,
    )


@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    """Configurable system settings panel."""
    if request.method == "POST":
        keys_to_update = [
            "park_name", "park_location", "park_phone", "park_whatsapp",
            "operating_hours", "max_capacity", "booking_window_days",
            "customer_cancel_threshold_hours", "customer_cancel_refund_before",
            "customer_cancel_refund_after", "park_cancel_refund_percentage",
            "cancellation_policy_text", "default_commission",
            "google_maps_url", "instagram_url", "facebook_url",
            "partner_commission_enabled", "partner_commission_wallet_enabled",
            "partner_levels_enabled", "partner_share_availability_enabled", "partner_referral_links_enabled"
        ]
        checkbox_keys = {"partner_commission_enabled", "partner_commission_wallet_enabled", "partner_levels_enabled", "partner_share_availability_enabled"}
        if current_user.is_super_admin:
            checkbox_keys.add("partner_referral_links_enabled")
        for k in keys_to_update:
            if k in checkbox_keys:
                SettingsService.set(k, "1" if k in request.form else "0", current_user.id)
            elif k in request.form:
                SettingsService.set(k, request.form.get(k), current_user.id)

        AuditService.log(
            action="SETTINGS_UPDATED",
            target_type="setting",
            details="Business settings updated via admin console",
            user_id=current_user.id,
        )
        flash("Settings saved successfully!", "success")
        return redirect(url_for("admin.settings"))

    current_settings = {k: SettingsService.get(k) for k in SettingsService.DEFAULTS.keys()}
    return render_template("admin/settings.html", settings=current_settings)


@admin_bp.route("/complaints")
@admin_required
def complaints():
    """Complaints management list."""
    all_complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    return render_template("admin/complaints.html", complaints=all_complaints)


@admin_bp.route("/complaints/<int:id>/update", methods=["POST"])
@admin_required
def update_complaint(id: int):
    complaint = db.get_or_404(Complaint, id)
    status = request.form.get("status", complaint.status)
    if status not in ("NEW", "IN_PROGRESS", "RESOLVED", "CLOSED"): status = complaint.status
    complaint.status = status
    complaint.resolution_note = request.form.get("resolution_note", "").strip() or complaint.resolution_note
    complaint.assigned_to = current_user.id
    db.session.commit()
    flash("Complaint updated successfully.", "success")
    return redirect(url_for("admin.complaints"))


@admin_bp.route("/feedback")
@admin_required
def feedback_list():
    """Customer ratings and feedback list."""
    all_feedback = Feedback.query.order_by(Feedback.created_at.desc()).all()
    return render_template("admin/feedback.html", feedback_list=all_feedback)


@admin_bp.route("/reports")
@admin_required
def reports():
    """Compact business reporting page using live booking/payment data."""
    confirmed = Booking.query.filter_by(status=BookingStatus.CONFIRMED).all()
    by_source = {src: sum(1 for b in confirmed if b.source == src) for src in BookingSource.ALL}
    monthly = {}
    for b in confirmed:
        key = b.booking_date.strftime("%Y-%m")
        monthly.setdefault(key, {"bookings": 0, "revenue": Decimal("0.00")})
        monthly[key]["bookings"] += 1
        monthly[key]["revenue"] += Decimal(str(b.amount or 0))
    return render_template("admin/reports.html", confirmed=confirmed, by_source=by_source, monthly=dict(sorted(monthly.items(), reverse=True)[:12]))


@admin_bp.route("/feedback/<int:id>/update", methods=["POST"])
@admin_required
def update_feedback(id: int):
    feedback = db.get_or_404(Feedback, id)
    status = request.form.get("status", feedback.status)
    if status not in ("NEW", "REVIEWING", "RESOLVED", "CLOSED"): status = feedback.status
    feedback.status = status
    feedback.admin_notes = request.form.get("admin_notes", "").strip() or feedback.admin_notes
    db.session.commit()
    flash("Feedback updated successfully.", "success")
    return redirect(url_for("admin.feedback_list"))


@admin_bp.route("/audit-logs")
@super_admin_only
def audit_logs():
    """System Administrator immutable audit trail viewer."""
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("admin/audit_logs.html", logs=logs)


@admin_bp.route("/super-dashboard")
@super_admin_only
def super_dashboard():
    """Technical/SaaS Command Center for System Administrator (M. Mohammed Khaleef)."""
    today = date.today()

    # Smart Overview: TODAY
    today_booking = Booking.query.filter_by(
        booking_date=today, status=BookingStatus.CONFIRMED
    ).first()
    today_checkin = None
    if today_booking:
        today_checkin = EquipmentChecklist.query.filter_by(
            booking_id=today_booking.id, type="CHECK_IN"
        ).first()

    # Smart Overview: UPCOMING
    next_booking = Booking.query.filter(
        Booking.booking_date > today,
        Booking.status == BookingStatus.CONFIRMED,
    ).order_by(Booking.booking_date.asc()).first()
    upcoming_count = Booking.query.filter(
        Booking.booking_date >= today,
        Booking.status == BookingStatus.CONFIRMED,
    ).count()

    # Smart Overview: BOOKINGS
    total_bookings = Booking.query.count()
    confirmed_count = Booking.query.filter_by(status=BookingStatus.CONFIRMED).count()
    pending_count = Booking.query.filter_by(status=BookingStatus.PENDING_PAYMENT).count()
    cancelled_count = Booking.query.filter_by(status=BookingStatus.CANCELLED).count()

    # Smart Overview: BUSINESS
    total_revenue = db.session.query(func.sum(Booking.amount)).filter(
        Booking.status == BookingStatus.CONFIRMED
    ).scalar() or Decimal("0.00")
    total_refunded = db.session.query(func.sum(Payment.refund_amount)).filter(
        Payment.status.in_([PaymentStatus.REFUNDED, PaymentStatus.PARTIALLY_REFUNDED])
    ).scalar() or Decimal("0.00")

    # Smart Overview: STAFF
    total_staff = User.query.count()
    active_staff = User.query.filter_by(is_active=True).count()
    partner_bookings_count = Booking.query.filter(Booking.staff_partner_id.isnot(None)).count()

    # Smart Overview: ALERTS
    cancellation_requests = CancellationRequest.query.filter_by(status=CancellationRequestStatus.PENDING).all()
    unresolved_complaints = Complaint.query.filter(Complaint.status.in_(["NEW", "IN_PROGRESS"])).all()
    equipment_reports = EquipmentReport.query.order_by(EquipmentReport.created_at.desc()).limit(5).all()
    pending_commissions = CommissionRecord.query.filter_by(status=CommissionStatus.PENDING).count()
    support_tickets = StaffSupportTicket.query.filter_by(status="NEW").all()

    # Smart Activity Feed
    activity_feed = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(12).all()

    # System Health Diagnostics
    system_health = {
        "app_status": "Operational",
        "database_status": "Connected (SQLite WAL)",
        "auth_status": "Active (scrypt + TOTP)",
        "payment_integration": f"Active ({SettingsService.get('payment_mode', 'SANDBOX')})",
        "whatsapp_integration": "Active (Dev Mock Logger)",
        "total_db_records": total_bookings + total_staff + len(activity_feed),
        "last_activity": activity_feed[0].created_at if activity_feed else None,
    }

    return render_template(
        "admin/super_dashboard.html",
        today=today,
        today_booking=today_booking,
        today_checkin=today_checkin,
        next_booking=next_booking,
        upcoming_count=upcoming_count,
        total_bookings=total_bookings,
        confirmed_count=confirmed_count,
        pending_count=pending_count,
        cancelled_count=cancelled_count,
        total_revenue=total_revenue,
        total_refunded=total_refunded,
        total_staff=total_staff,
        active_staff=active_staff,
        partner_bookings_count=partner_bookings_count,
        cancellation_requests=cancellation_requests,
        unresolved_complaints=unresolved_complaints,
        equipment_reports=equipment_reports,
        pending_commissions=pending_commissions,
        support_tickets=support_tickets,
        activity_feed=activity_feed,
        system_health=system_health,
    )


@admin_bp.route("/staff")
@super_admin_only
def staff_management():
    """Staff account directory and lifecycle management."""
    staff_members = User.query.order_by(User.role.asc(), User.id.asc()).all()
    roles = Role.STAFF_ROLES
    return render_template(
        "admin/staff_management.html",
        staff_members=staff_members,
        roles=roles,
    )


@admin_bp.route("/staff/add", methods=["POST"])
@super_admin_only
def add_staff():
    """Create a new staff account with unique Staff ID."""
    username = request.form.get("username", "").strip().lower()
    full_name = request.form.get("full_name", "").strip()
    phone = request.form.get("phone", "").strip()
    role = request.form.get("role", Role.STAFF_PARTNER)
    password = request.form.get("password", "")
    custom_staff_id = request.form.get("staff_id", "").strip().upper() or None

    if not username or not password or not full_name:
        flash("Username, password, and full name are required.", "danger")
        return redirect(url_for("admin.staff_management"))

    existing = User.query.filter((User.username == username) | (User.staff_id == custom_staff_id)).first()
    if existing:
        flash("A user with this username or Staff ID already exists.", "danger")
        return redirect(url_for("admin.staff_management"))

    user = User(
        username=username,
        full_name=full_name,
        phone=phone,
        role=role,
        staff_id=custom_staff_id,
        created_by=current_user.id,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    AuditService.log(
        action=AuditAction.STAFF_CREATED,
        target_type="user",
        target_id=user.id,
        details={"username": user.username, "role": user.role, "staff_id": user.formatted_staff_id},
        user_id=current_user.id,
    )

    flash(f"Staff account for {user.full_name} ({user.formatted_staff_id}) created successfully!", "success")
    return redirect(url_for("admin.staff_management"))


@admin_bp.route("/staff/edit/<int:id>", methods=["GET", "POST"])
@super_admin_only
def edit_staff(id: int):
    """Edit staff profile/access fields. Existing passwords are never displayed; only a new password can be set."""
    user = db.get_or_404(User, id)
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        staff_id = request.form.get("staff_id", "").strip() or None
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip() or None
        role = request.form.get("role", Role.STAFF_PARTNER)
        new_password = request.form.get("new_password", "").strip()
        permissions = request.form.getlist("permissions")
        if not username or not full_name or role not in Role.ALL:
            flash("Name, username and a valid role are required.", "danger"); return redirect(url_for("admin.staff_management"))
        dup = User.query.filter(User.id != user.id, (User.username == username) | (User.staff_id == staff_id if staff_id else False)).first()
        if dup:
            flash("That username or Staff ID is already in use.", "danger"); return redirect(url_for("admin.staff_management"))
        user.username, user.staff_id, user.full_name, user.phone, user.role = username, staff_id, full_name, phone, role
        user.set_permissions(permissions)
        user.is_active = "is_active" in request.form
        if new_password:
            if len(new_password) < 6: flash("New password must be at least 6 characters.", "danger"); return redirect(url_for("admin.staff_management"))
            user.set_password(new_password)
        db.session.commit()
        AuditService.log(action=AuditAction.STAFF_UPDATED,target_type="user",target_id=user.id,details={"action":"profile_edit","username":user.username},user_id=current_user.id)
        flash(f"{user.full_name}'s account updated successfully.", "success")
        return redirect(url_for("admin.staff_management"))
    return render_template("admin/staff_management.html", staff_members=User.query.order_by(User.id).all(), Role=Role, edit_user=user, permission_options=[("CONTENT_MANAGEMENT", "Content Management")])


@admin_bp.route("/staff/toggle/<int:id>", methods=["POST"])
@super_admin_only
def toggle_staff(id: int):
    """Activate or deactivate a staff member account."""
    if id == current_user.id:
        flash("You cannot deactivate your own System Administrator account.", "warning")
        return redirect(url_for("admin.staff_management"))

    user = db.get_or_404(User, id)
    user.is_active = not user.is_active
    db.session.commit()

    action = AuditAction.STAFF_UPDATED if user.is_active else AuditAction.STAFF_DEACTIVATED
    AuditService.log(
        action=action,
        target_type="user",
        target_id=user.id,
        details={"username": user.username, "is_active": user.is_active},
        user_id=current_user.id,
    )

    flash(f"Account for {user.full_name} is now {'Active' if user.is_active else 'Deactivated'}.", "info")
    return redirect(url_for("admin.staff_management"))


@admin_bp.route("/staff/reset-password/<int:id>", methods=["POST"])
@super_admin_only
def reset_staff_password(id: int):
    """Reset password for a staff account."""
    user = db.get_or_404(User, id)
    new_password = request.form.get("new_password", "").strip()

    if not new_password or len(new_password) < 6:
        flash("Password must be at least 6 characters long.", "danger")
        return redirect(url_for("admin.staff_management"))

    user.set_password(new_password)
    db.session.commit()

    AuditService.log(
        action=AuditAction.STAFF_UPDATED,
        target_type="user",
        target_id=user.id,
        details={"action": "password_reset", "username": user.username},
        user_id=current_user.id,
    )

    flash(f"Password for {user.full_name} reset successfully.", "success")
    return redirect(url_for("admin.staff_management"))


@admin_bp.route("/cancellations")
@admin_required
def cancellations_list():
    """Review cancellation requests submitted by Staff Partners."""
    requests_list = CancellationRequest.query.order_by(CancellationRequest.created_at.desc()).all()
    return render_template("admin/cancellations.html", requests=requests_list)


@admin_bp.route("/cancellations/<int:id>/review", methods=["POST"])
@admin_required
def review_cancellation(id: int):
    """Approve or reject a cancellation request."""
    req = db.get_or_404(CancellationRequest, id)
    action = request.form.get("action")
    note = request.form.get("note", "").strip()

    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.utcnow()
    req.review_note = note

    if action == "approve":
        req.status = CancellationRequestStatus.APPROVED
        # Cancel the booking
        success, msg = BookingService.cancel_booking(
            booking_id=req.booking_id,
            reason=f"Partner cancellation request approved: {req.reason}",
            cancelled_by_user_id=current_user.id,
            is_park_cancellation=False,
        )
        flash(f"Cancellation request approved. {msg}", "success")
    else:
        req.status = CancellationRequestStatus.REJECTED
        flash("Cancellation request was rejected.", "info")

    db.session.commit()
    return redirect(url_for("admin.cancellations_list"))


@admin_bp.route("/equipment-reports")
@admin_required
def equipment_reports():
    """Operational incident log of missing/damaged equipment."""
    reports = EquipmentReport.query.order_by(EquipmentReport.created_at.desc()).all()
    return render_template("admin/equipment_reports.html", reports=reports)


@admin_bp.route("/support")
@admin_required
def support_tickets():
    tickets = StaffSupportTicket.query.order_by(StaffSupportTicket.created_at.desc()).all()
    return render_template("admin/support_tickets.html", tickets=tickets)


@admin_bp.route("/support/<int:id>/respond", methods=["POST"])
@admin_required
def respond_support(id: int):
    ticket = db.get_or_404(StaffSupportTicket, id)
    note = request.form.get("admin_notes", "").strip()
    status = request.form.get("status", "REVIEWING")
    if note: ticket.admin_notes = note
    ticket.status = status if status in ("NEW", "REVIEWING", "RESOLVED") else "REVIEWING"
    db.session.commit()
    NotificationService.notify_user(ticket.staff_user_id, "Support request updated", f"Your support request #{ticket.id} is now {ticket.status}." + (f" Admin note: {ticket.admin_notes}" if ticket.admin_notes else ""), notification_type="SUPPORT", reference_type="staff_support", reference_id=ticket.id)
    flash("Support request updated and staff member notified.", "success")
    return redirect(url_for("admin.support_tickets"))


@admin_bp.route("/notifications")
@admin_required
def notifications_view():
    """Notification center for Admin / Owner."""
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).all()
    return render_template("admin/notifications.html", notifications=notifs)


@admin_bp.route("/notifications/mark-all-read", methods=["POST"])
@admin_required
def mark_all_notifications_read():
    """Mark all notifications as read for current user."""
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("All notifications marked as read.", "info")
    return redirect(url_for("admin.notifications_view"))
