from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.models.content import ContentItem, ContentType
from app.models.booking import Booking, BookingStatus
from app.services.settings_service import SettingsService
from app.services.booking_service import BookingService

public_bp = Blueprint("public", __name__)

@public_bp.route("/favicon.ico")
def favicon():
    return ("", 204)


@public_bp.route("/_debug_files")
def debug_files():
    import os
    from flask import current_app
    if not current_app.debug:
        return "", 404
    tf = current_app.template_folder
    tmpl_exists = os.path.exists(tf) if tf else False
    tmpl_index_exists = os.path.exists(os.path.join(tf, "public", "index.html")) if tf else False
    res = {
        "cwd": os.getcwd(),
        "template_folder": tf,
        "template_folder_exists": tmpl_exists,
        "template_index_exists": tmpl_index_exists,
        "init_file": __file__,
        "task_app_files": os.listdir("/var/task/app") if os.path.exists("/var/task/app") else [],
        "task_app_templates": os.listdir("/var/task/app/templates") if os.path.exists("/var/task/app/templates") else [],
    }
    return res



@public_bp.route("/")
def index():
    """Main landing homepage for Freedom Park."""
    # Fetch active CMS items
    activities = ContentItem.query.filter_by(
        content_type=ContentType.ACTIVITY, is_active=True
    ).order_by(ContentItem.display_order.asc()).all()
    
    facilities = ContentItem.query.filter_by(
        content_type=ContentType.FACILITY, is_active=True
    ).order_by(ContentItem.display_order.asc()).all()

    rules = ContentItem.query.filter_by(
        content_type=ContentType.RULE, is_active=True
    ).order_by(ContentItem.display_order.asc()).all()

    gallery_photos = ContentItem.query.filter_by(
        content_type=ContentType.GALLERY, is_active=True
    ).order_by(ContentItem.display_order.asc()).limit(6).all()

    return render_template(
        "public/index.html",
        activities=activities,
        facilities=facilities,
        rules=rules,
        gallery_photos=gallery_photos,
    )


@public_bp.route("/about")
def about():
    """About Freedom Park page."""
    about_items = ContentItem.query.filter_by(
        content_type=ContentType.ABOUT, is_active=True
    ).order_by(ContentItem.display_order.asc()).all()
    return render_template("public/about.html", about_items=about_items)


@public_bp.route("/activities")
def activities():
    """Park activities page."""
    items = ContentItem.query.filter_by(
        content_type=ContentType.ACTIVITY, is_active=True
    ).order_by(ContentItem.display_order.asc()).all()
    return render_template("public/activities.html", activities=items)


@public_bp.route("/facilities")
def facilities():
    """Park amenities & facilities page."""
    items = ContentItem.query.filter_by(
        content_type=ContentType.FACILITY, is_active=True
    ).order_by(ContentItem.display_order.asc()).all()
    return render_template("public/facilities.html", facilities=items)


@public_bp.route("/rules")
def rules():
    """Park policies, rules, and guidelines."""
    items = ContentItem.query.filter_by(
        content_type=ContentType.RULE, is_active=True
    ).order_by(ContentItem.display_order.asc()).all()
    return render_template("public/rules.html", rules=items)


@public_bp.route("/pricing")
def pricing():
    """Transparent pricing & booking info."""
    return render_template("public/pricing.html")


@public_bp.route("/gallery")
def gallery():
    """Park photo gallery."""
    photos = ContentItem.query.filter_by(
        content_type=ContentType.GALLERY, is_active=True
    ).order_by(ContentItem.display_order.asc()).all()
    return render_template("public/gallery.html", photos=photos)


@public_bp.route("/contact")
def contact():
    """Contact, location, and Google Maps info."""
    return render_template("public/contact.html")


@public_bp.route("/verify/<booking_uid>")
def verify_ticket(booking_uid: str):
    """
    Public ticket verification endpoint accessed via QR code scans.
    Shows entry verification status without exposing customer private data.
    """
    booking = Booking.query.filter_by(booking_uid=booking_uid.strip().upper()).first()
    if not booking:
        return render_template("public/verify_ticket.html", found=False, booking=None)

    is_valid = booking.status == BookingStatus.CONFIRMED and not booking.is_past
    return render_template(
        "public/verify_ticket.html",
        found=True,
        booking=booking,
        is_valid=is_valid,
    )
