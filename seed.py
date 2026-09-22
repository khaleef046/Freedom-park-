from datetime import date
from decimal import Decimal
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app
from app.extensions import db
from app.models.user import User, Customer, Role
from app.models.equipment import Equipment
from app.models.content import ContentItem, ContentType
from app.services.settings_service import SettingsService


def seed_all():
    """Seed comprehensive initial development data into the database."""
    app = create_app("development")
    with app.app_context():
        # Create all tables
        db.create_all()

        # 1. Seed Business Settings
        SettingsService.seed_defaults()
        print("[OK] System and business settings seeded.")

        # 2. Seed Staff Accounts
        staff_data = [
            ("developer", "gojothedev", "M. Mohammed Khaleef", Role.SUPER_ADMIN, "9999900001", "FP-ADMIN-001"),
            ("admin", "admin123", "M. Asrar Ul Haq", Role.ADMIN, "9999900002", "FP-OWNER-002"),
            ("partner1", "partner123", "Pernambut Staff Partner", Role.STAFF_PARTNER, "9999900003", "FP-PARTNER-001"),
            ("security1", "security123", "Gate Security Guard", Role.SECURITY, "9999900004", "FP-SEC-001"),
        ]

        for username, pwd, name, role, phone, staff_code in staff_data:
            existing = User.query.filter_by(username=username).first()
            if not existing:
                u = User(username=username, full_name=name, role=role, phone=phone, staff_id=staff_code)
                u.set_password(pwd)
                db.session.add(u)
            else:
                existing.full_name = name
                existing.staff_id = staff_code
        db.session.commit()
        print("[OK] Staff accounts created (Super Admin, Owner/Mama, Partner, Security).")

        # 3. Seed Standard Equipment Inventory
        equipment_list = [
            ("Cricket Bats", 2),
            ("Cricket Balls", 3),
            ("Cricket Stumps & Bails Set", 1),
            ("Carrom Board & Coin Set", 1),
            ("Badminton Rackets", 4),
            ("Shuttlecock Pack", 6),
            ("Tennis / Soft Balls", 4),
        ]
        for eq_name, qty in equipment_list:
            if not Equipment.query.filter_by(name=eq_name).first():
                eq = Equipment(name=eq_name, quantity=qty, is_active=True)
                db.session.add(eq)
        db.session.commit()
        print("[OK] Equipment inventory seeded.")

        # 4. Seed CMS Showcase Content
        activities = [
            ("Family Cricket Matches", "Full pitch grass area suitable for casual and spirited family matches. Bats, balls, and wickets supplied.", 1),
            ("Carrom Board Battles", "Tournament-grade carrom boards set up in covered gazebos for relaxing afternoon rallies.", 2),
            ("Open Lawn Games", "Spacious open green lawns ideal for frisbee, badminton, and children's tag games.", 3),
        ]
        for title, desc, order in activities:
            if not ContentItem.query.filter_by(title=title, content_type=ContentType.ACTIVITY).first():
                db.session.add(ContentItem(
                    content_type=ContentType.ACTIVITY,
                    title=title,
                    body=desc,
                    display_order=order,
                    is_active=True,
                ))

        facilities = [
            ("Covered Dining Gazebos", "Shaded pavilions with dining tables and chairs for entire family meals.", 1),
            ("Hygienic Restrooms", "Maintained, separate clean restrooms for male and female guests.", 2),
            ("Ample Gated Parking", "Safe on-site parking for four-wheelers and two-wheelers inside park perimeter.", 3),
        ]
        for title, desc, order in facilities:
            if not ContentItem.query.filter_by(title=title, content_type=ContentType.FACILITY).first():
                db.session.add(ContentItem(
                    content_type=ContentType.FACILITY,
                    title=title,
                    body=desc,
                    display_order=order,
                    is_active=True,
                ))

        rules = [
            ("Operating Schedule", "Park opens at 8:00 AM and closes promptly at 8:00 PM.", 1),
            ("Guest Limit", "Strict limit of 100 guests per booking for safety and comfort.", 2),
            ("Equipment Care", "All sports equipment must be returned to security upon checkout.", 3),
        ]
        for title, desc, order in rules:
            if not ContentItem.query.filter_by(title=title, content_type=ContentType.RULE).first():
                db.session.add(ContentItem(
                    content_type=ContentType.RULE,
                    title=title,
                    body=desc,
                    display_order=order,
                    is_active=True,
                ))

        # 5. Seed Test Customer
        test_customer_phone = "9876543210"
        if not Customer.query.filter_by(phone=test_customer_phone).first():
            cust = Customer(phone=test_customer_phone, name="Ahmed Family")
            db.session.add(cust)

        db.session.commit()
        print("[OK] CMS showcase items and test customer created.")


if __name__ == "__main__":
    seed_all()
