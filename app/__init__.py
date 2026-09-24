import os
from flask import Flask, render_template
from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Engine
from app.config import get_config
from app.extensions import db, login_manager, csrf, migrate, oauth
from app.utils.helpers import format_currency, format_date_long, format_time_12hr


def create_app(config_name: str = None) -> Flask:
    """Application factory for Freedom Park web platform."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(project_root, "templates")
    static_dir = os.path.join(project_root, "static")
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    config_obj = get_config(config_name)
    app.config.from_object(config_obj)

    if config_obj.__name__ == "ProductionConfig":
        if not os.environ.get("SECRET_KEY"):
            raise RuntimeError("SECRET_KEY must be set in production.")
        if not os.environ.get("DATABASE_URL"):
            raise RuntimeError("DATABASE_URL must be set in production; use persistent PostgreSQL.")

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    oauth.init_app(app)
    oauth.register(
        name="google",
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        client_kwargs={"scope": "openid email profile"},
    )

    # Configure login manager
    login_manager.login_view = "auth.staff_login"
    login_manager.login_message_category = "warning"
    login_manager.login_message = "Please log in to access this page."

    # SQLite connection pragmas (Foreign Keys, WAL Mode, Busy Timeout)
    register_sqlite_pragmas(app)

    # User loader for polymorphic session support (Staff and Customers)
    register_user_loader()

    # Template context processors
    register_context_processors(app)

    # Error handlers
    register_error_handlers(app)

    # Register all Blueprints
    register_blueprints(app)

    # Lightweight compatibility migration for existing SQLite databases.
    # Adds the optional staff permissions column without replacing the database.
    ensure_compatibility_columns(app)

    # Ensure upload directory exists.
    # Use an explicit upload directory when the hosting platform requires it.
    upload_folder = app.config.get("UPLOAD_FOLDER", "uploads")

    if os.environ.get("UPLOAD_FOLDER"):
        upload_folder = os.environ["UPLOAD_FOLDER"]

    app.config["UPLOAD_FOLDER"] = upload_folder
    os.makedirs(upload_folder, exist_ok=True)

    return app


def register_sqlite_pragmas(app: Flask):
    """Enforce Foreign Keys, WAL journal mode, and busy timeout for SQLite."""
    with app.app_context():
        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            # Only apply SQLite pragmas if the driver connection is sqlite3
            if "sqlite" in app.config.get("SQLALCHEMY_DATABASE_URI", ""):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON;")
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA busy_timeout=5000;")
                cursor.close()


def register_user_loader():
    """Polymorphic user loader for Flask-Login supporting both Staff and Customers."""
    from app.models.user import User, Customer

    @login_manager.user_loader
    def load_user(user_id: str):
        if not user_id:
            return None
        try:
            if user_id.startswith("staff_"):
                uid = int(user_id.replace("staff_", ""))
                return User.query.get(uid)
            elif user_id.startswith("cust_"):
                cid = int(user_id.replace("cust_", ""))
                return Customer.query.get(cid)
        except (ValueError, TypeError):
            return None
        return None


def register_context_processors(app: Flask):
    """Inject helpers, business settings, and role constants globally into Jinja2 templates."""
    from app.models.user import Role
    from app.services.settings_service import SettingsService

    @app.context_processor
    def inject_global_vars():
        return {
            "format_currency": format_currency,
            "format_date_long": format_date_long,
            "format_time_12hr": format_time_12hr,
            "Role": Role,
            "get_setting": SettingsService.get,
            "get_setting_decimal": SettingsService.get_decimal,
            "get_setting_int": SettingsService.get_int,
        }


def register_error_handlers(app: Flask):
    """Handle HTTP errors with branded, friendly user interfaces."""
    @app.errorhandler(400)
    def bad_request(error):
        return render_template("errors/400.html", error=error), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html", error=error), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html", error=error), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template("errors/500.html", error=error), 500


def register_blueprints(app: Flask):
    """Register all modular application blueprints."""
    from app.routes.public import public_bp
    from app.routes.auth import auth_bp
    from app.routes.customer import customer_bp
    from app.routes.admin import admin_bp
    from app.routes.staff import staff_bp
    from app.routes.security import security_bp
    from app.routes.content import content_bp
    from app.routes.api import api_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(customer_bp, url_prefix="/my")
    app.add_url_rule(
        "/book",
        endpoint="customer_book_legacy",
        view_func=app.view_functions["customer.book"],
        methods=["GET", "POST"],
    )
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(staff_bp, url_prefix="/staff")
    app.register_blueprint(security_bp, url_prefix="/security")
    app.register_blueprint(content_bp, url_prefix="/content-manage")
    app.register_blueprint(api_bp, url_prefix="/api")


def ensure_compatibility_columns(app):
    """Add safe additive columns needed by newer builds to an existing SQLite DB."""
    with app.app_context():
        try:
            from app.models.expenditure import Expenditure
            from app.models.feedback import Feedback

            Expenditure.__table__.create(bind=db.engine, checkfirst=True)
            inspector = inspect(db.engine)
            if "feedback" in inspector.get_table_names():
                feedback_columns = {c["name"] for c in inspector.get_columns("feedback")}
                if "submitted_at" not in feedback_columns:
                    with db.engine.begin() as conn:
                        conn.execute(text("ALTER TABLE feedback ADD COLUMN submitted_at DATETIME"))
                with db.engine.begin() as conn:
                    conn.execute(text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_feedback_booking "
                        "ON feedback (booking_id) WHERE booking_id IS NOT NULL"
                    ))
            if "users" in inspector.get_table_names():
                cols = {c["name"] for c in inspector.get_columns("users")}
                if "permissions" not in cols:
                    with db.engine.begin() as conn:
                        conn.execute(
                            text(
                                "ALTER TABLE users "
                                "ADD COLUMN permissions TEXT DEFAULT '[]'"
                            )
                        )

                # Existing non-system staff should retain the intended optional content access.
                with db.engine.begin() as conn:
                    conn.execute(
                        text(
                            "UPDATE users SET permissions='[\"CONTENT_MANAGEMENT\"]' "
                            "WHERE role IN ('ADMIN','STAFF_PARTNER','SECURITY') "
                            "AND (permissions IS NULL OR permissions='')"
                        )
                    )
        except Exception:
            # Never prevent the application from starting because of a compatibility helper.
            pass