import pytest
from datetime import date, timedelta
from app.models.user import User, Role
from app.models.booking import Booking, BookingSource, BookingStatus
from app.models.expenditure import Expenditure
from app.extensions import db
from decimal import Decimal


def test_super_admin_redirect_to_super_dashboard(client):
    """Verify SUPER_ADMIN login redirects directly to the SaaS super-dashboard."""
    res = client.post("/auth/staff-login", data={
        "username": "test_superadmin",
        "password": "pass123"
    }, follow_redirects=False)
    assert res.status_code == 302
    assert "/admin/super-dashboard" in res.location


def test_owner_redirect_to_owner_dashboard(client):
    """Verify ADMIN (Owner) login redirects to the Owner command center /admin/dashboard."""
    res = client.post("/auth/staff-login", data={
        "username": "test_owner",
        "password": "pass123"
    }, follow_redirects=False)
    assert res.status_code == 302
    assert res.location.endswith("/admin/dashboard") or "/admin/dashboard" in res.location


def test_owner_forbidden_from_super_dashboard(client):
    """Verify ADMIN (Owner) is strictly forbidden (403) from accessing Super Admin dashboard."""
    client.post("/auth/staff-login", data={
        "username": "test_owner",
        "password": "pass123"
    })
    res = client.get("/admin/super-dashboard")
    assert res.status_code == 403


def test_super_admin_can_access_all_super_features(client):
    """Verify SUPER_ADMIN can access super-dashboard, staff management, cancellations, equipment reports, and notifications."""
    client.post("/auth/staff-login", data={
        "username": "test_superadmin",
        "password": "pass123"
    })
    # Super Dashboard
    res = client.get("/admin/super-dashboard")
    assert res.status_code == 200
    assert b"M. Mohammed Khaleef" in res.data or b"Super Admin" in res.data

    # Staff Management
    res_staff = client.get("/admin/staff")
    assert res_staff.status_code == 200
    assert b"Staff Accounts" in res_staff.data

    # Partner Cancellations
    res_canc = client.get("/admin/cancellations")
    assert res_canc.status_code == 200

    # Equipment Reports
    res_equip = client.get("/admin/equipment-reports")
    assert res_equip.status_code == 200

    # Notification Center
    res_notif = client.get("/admin/notifications")
    assert res_notif.status_code == 200


def test_owner_forbidden_from_staff_management(client):
    """Verify ADMIN (Owner) is strictly forbidden (403) from accessing staff management."""
    client.post("/auth/staff-login", data={
        "username": "test_owner",
        "password": "pass123"
    })
    res = client.get("/admin/staff")
    assert res.status_code == 403
    assert b"Staff Login" not in res.data


def test_staff_management_is_visible_only_to_super_admin(client):
    client.post("/auth/staff-login", data={"username": "test_superadmin", "password": "pass123"})
    response = client.get("/admin/dashboard")
    assert response.status_code == 200
    assert b"Staff" in response.data

    client.get("/auth/logout")
    client.post("/auth/staff-login", data={"username": "test_owner", "password": "pass123"})
    response = client.get("/admin/dashboard")
    assert response.status_code == 200
    assert b"Manage staff accounts and access" not in response.data


@pytest.mark.parametrize("username", ["test_partner", "test_security"])
def test_non_admin_roles_cannot_access_finances(client, username):
    client.post("/auth/staff-login", data={"username": username, "password": "pass123"})
    assert client.get("/admin/finances").status_code == 403


def test_admin_and_super_admin_can_access_finances_and_owner_can_manage_expenses(client, app):
    with app.app_context():
        booking = Booking(
            booking_uid="FP-FINANCE-TEST",
            booking_date=date.today(),
            customer_name="Financial Test",
            customer_phone="9000000000",
            num_people=2,
            amount=Decimal("2500.00"),
            status=BookingStatus.CONFIRMED,
            source=BookingSource.WEBSITE,
        )
        db.session.add(booking)
        db.session.commit()

    client.post("/auth/staff-login", data={"username": "test_owner", "password": "pass123"})
    response = client.get("/admin/finances")
    assert response.status_code == 200
    assert b"2,500" in response.data

    response = client.post("/admin/finances", data={
        "expense_date": date.today().isoformat(),
        "category": "Cleaning",
        "amount": "400.00",
        "description": "Monthly cleaning",
    })
    assert response.status_code == 302
    with app.app_context():
        expense = Expenditure.query.one()
        expense_id = expense.id

    response = client.post(f"/admin/finances/{expense_id}/edit", data={
        "expense_date": date.today().isoformat(),
        "category": "Supplies",
        "amount": "450.00",
        "description": "Updated supplies",
    })
    assert response.status_code == 302
    response = client.post(f"/admin/finances/{expense_id}/delete")
    assert response.status_code == 302
    with app.app_context():
        assert Expenditure.query.count() == 0

    client.get("/auth/logout")
    client.post("/auth/staff-login", data={"username": "test_superadmin", "password": "pass123"})
    assert client.get("/admin/finances").status_code == 200


def test_user_staff_id_property(app):
    """Verify formatted_staff_id helper generates consistent IDs."""
    with app.app_context():
        user = User(username="temp_partner", full_name="Temp Partner", role=Role.STAFF_PARTNER)
        assert "PARTNER" in user.formatted_staff_id

        user_custom = User(username="custom_partner", full_name="Custom", role=Role.STAFF_PARTNER, staff_id="FP-PARTNER-777")
        assert user_custom.formatted_staff_id == "FP-PARTNER-777"


def test_customer_5_step_booking_flow(client, app):
    """Verify the 5-step customer booking flow:
    Step 1: /book (GET calendar)
    Step 2: /book (POST details -> redirect to /my/review/<uid>)
    Step 3: /my/review/<uid> (GET review summary)
    Step 4: /my/pay/<uid> (GET payment screen & POST sandbox pay)
    Step 5: /my/confirmation/<uid> (GET confirmation pass)
    """
    # Authenticate customer via OTP flow
    from app.services.auth_service import AuthService
    with app.app_context():
        AuthService.request_customer_otp("9876543210")
    
    res_login = client.post("/auth/customer-login", data={
        "step": "verify",
        "phone": "9876543210",
        "otp": "123456"
    }, follow_redirects=True)
    assert res_login.status_code == 200

    # Step 1: Check availability & select date
    res_step1 = client.get("/book")
    assert res_step1.status_code == 200
    assert b"Step 1" in res_step1.data or b"Select Date" in res_step1.data

    # Step 2: Submit booking details
    target_date = (date.today() + timedelta(days=20)).isoformat()
    res_step2 = client.post("/book", data={
        "booking_date": target_date,
        "guest_count": "25",
        "customer_name": "Test Customer",
        "customer_phone": "9876543210",
        "customer_email": "test@example.com",
        "purpose": "Family Reunion"
    }, follow_redirects=False)

    # Must redirect to Step 3: Review
    assert res_step2.status_code == 302
    assert "/my/review/" in res_step2.location

    review_url = res_step2.location

    # Step 3: View Review Page
    res_step3 = client.get(review_url)
    assert res_step3.status_code == 200
    assert b"Review &amp; Confirm" in res_step3.data or b"Review" in res_step3.data
    assert b"Proceed to Payment" in res_step3.data

    # Extract booking_uid from location
    booking_uid = review_url.split("/my/review/")[-1]

    # Step 4: Access Payment Screen
    pay_url = f"/my/pay/{booking_uid}"
    res_step4_get = client.get(pay_url)
    assert res_step4_get.status_code == 200
    assert b"Payment" in res_step4_get.data

    # Complete sandbox payment
    res_step4_post = client.post(pay_url, data={
        "payment_method": "upi",
        "upi_id": "test@okhdfcbank"
    }, follow_redirects=False)
    assert res_step4_post.status_code == 302
    assert f"/my/confirmation/{booking_uid}" in res_step4_post.location

    # Step 5: View Confirmation Page
    conf_url = f"/my/confirmation/{booking_uid}"
    res_step5 = client.get(conf_url)
    assert res_step5.status_code == 200
    assert b"Confirmed" in res_step5.data or b"Entry Pass" in res_step5.data
