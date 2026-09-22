from app.models.user import User, Customer, Role
from app.services.auth_service import AuthService


def test_staff_authentication_success(app):
    with app.app_context():
        user, err = AuthService.authenticate_staff("test_owner", "pass123")
        assert user is not None
        assert user.role == Role.ADMIN


def test_staff_authentication_invalid_password(app):
    with app.app_context():
        user, err = AuthService.authenticate_staff("test_owner", "wrongpassword")
        assert user is None
        assert "Invalid" in err


def test_customer_otp_flow(app):
    with app.app_context():
        # Step 1: Request OTP
        success, msg = AuthService.request_customer_otp("9123456789")
        assert success is True

        # Step 2: Verify OTP using mock mode code '123456'
        customer, msg = AuthService.verify_customer_otp("9123456789", "123456")
        assert customer is not None
        assert customer.phone == "9123456789"


def test_customer_otp_invalid(app):
    with app.app_context():
        AuthService.request_customer_otp("9123456789")
        customer, msg = AuthService.verify_customer_otp("9123456789", "000000")
        assert customer is None
        assert "Invalid" in msg


def test_staff_login_http_route(client):
    res = client.post("/auth/staff-login", data={
        "username": "test_owner",
        "password": "pass123"
    }, follow_redirects=False)
    assert res.status_code == 302
    assert "/admin" in res.location
