from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models.content import ContentItem, ContentType
from app.models.user import Role
from app.utils.decorators import content_permission_required

content_bp = Blueprint("content_bp", __name__)


@content_bp.route("/")
@content_bp.route("/dashboard")
@content_permission_required
def dashboard():
    """Content Staff dashboard: manage gallery, activities, facilities, and rules without financial access."""
    content_type = request.args.get("type", ContentType.GALLERY)
    items = ContentItem.query.filter_by(content_type=content_type).order_by(
        ContentItem.display_order.asc(), ContentItem.created_at.desc()
    ).all()

    return render_template(
        "content/dashboard.html",
        items=items,
        current_type=content_type,
        content_types=ContentType.ALL,
    )


@content_bp.route("/add", methods=["GET", "POST"])
@content_permission_required
def add_item():
    """Add new CMS item (photo, activity, facility, rule, etc.)."""
    if request.method == "POST":
        content_type = request.form.get("content_type", ContentType.GALLERY)
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        image_path = request.form.get("image_path", "").strip()
        display_order = int(request.form.get("display_order", "0"))

        item = ContentItem(
            content_type=content_type,
            title=title,
            body=body,
            image_path=image_path,
            display_order=display_order,
            created_by=current_user.id,
        )
        db.session.add(item)
        db.session.commit()
        flash(f"{content_type.capitalize()} item added successfully!", "success")
        return redirect(url_for("content_bp.dashboard", type=content_type))

    prefill_type = request.args.get("type", ContentType.GALLERY)
    return render_template("content/edit_item.html", item=None, prefill_type=prefill_type)


@content_bp.route("/edit/<int:id>", methods=["GET", "POST"])
@content_permission_required
def edit_item(id: int):
    """Edit existing CMS item."""
    item = db.get_or_404(ContentItem, id)

    if request.method == "POST":
        item.title = request.form.get("title", item.title).strip()
        item.body = request.form.get("body", item.body).strip()
        item.image_path = request.form.get("image_path", item.image_path).strip()
        item.display_order = int(request.form.get("display_order", item.display_order))
        item.is_active = "is_active" in request.form
        item.updated_by = current_user.id

        db.session.commit()
        flash("Content item updated successfully!", "success")
        return redirect(url_for("content_bp.dashboard", type=item.content_type))

    return render_template("content/edit_item.html", item=item, prefill_type=item.content_type)


@content_bp.route("/toggle/<int:id>", methods=["POST"])
@content_permission_required
def toggle_status(id: int):
    """Toggle visibility state of content item."""
    item = db.get_or_404(ContentItem, id)
    item.is_active = not item.is_active
    item.updated_by = current_user.id
    db.session.commit()
    flash(f"Item status changed to {'Active' if item.is_active else 'Hidden'}.", "info")
    return redirect(url_for("content_bp.dashboard", type=item.content_type))
