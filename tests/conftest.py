import pytest
from datetime import date, timedelta
from decimal import Decimal
from app import create_app
from app.extensions import db
from app.models.user import User, Customer, Role
from app.models.setting import Setting
from app.services.settings_service import SettingsService


@pytest.fixture
def app():
    """Create test application instance using in-memory SQLite."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        SettingsService.seed_defaults()

        # Create test users
        superadmin = User(username="test_superadmin", full_name="Super Admin", role=Role.SUPER_ADMIN)
        superadmin.set_password("pass123")
        db.session.add(superadmin)

        owner = User(username="test_owner", full_name="Owner Mama", role=Role.ADMIN)
        owner.set_password("pass123")
        db.session.add(owner)

        partner = User(username="test_partner", full_name="Staff Partner", role=Role.STAFF_PARTNER)
        partner.set_password("pass123")
        db.session.add(partner)

        security = User(username="test_security", full_name="Security Guard", role=Role.SECURITY)
        security.set_password("pass123")
        db.session.add(security)

        content = User(username="test_content", full_name="Content Staff", role=Role.STAFF_PARTNER)
        content.set_password("pass123")
        content.set_permissions(["CONTENT_MANAGEMENT"])
        db.session.add(content)

        customer = Customer(phone="9876543210", name="Test Customer")
        db.session.add(customer)

        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test HTTP client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Test CLI runner."""
    return app.test_cli_runner()
