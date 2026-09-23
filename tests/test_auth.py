from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db, oauth
from app.models.user import User, Customer, CustomerIdentity, Role
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


def _google_claims(subject="google-subject-1", email="person@example.com"):
    return {
        "iss": "https://accounts.google.com",
        "aud": "test-google-client-id",
        "sub": subject,
        "email": email,
        "email_verified": True,
        "name": "Google Person",
        "exp": (datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp(),
    }


def test_google_login_redirect_requires_configuration(client, app):
    app.config["GOOGLE_CLIENT_ID"] = None
    response = client.get("/auth/google/login")
    assert response.status_code == 302
    assert response.location.endswith("/auth/customer-login")


def test_google_new_customer_login(client, app, monkeypatch):
    app.config.update(
        GOOGLE_CLIENT_ID="test-google-client-id",
        GOOGLE_CLIENT_SECRET="test-google-client-secret",
        GOOGLE_REDIRECT_URI="http://localhost/auth/google/callback",
    )
    claims = _google_claims()
    monkeypatch.setattr(oauth.google, "authorize_access_token", lambda **kwargs: {"userinfo": claims})

    response = client.get("/auth/google/callback")

    assert response.status_code == 302
    assert response.location.endswith("/my/dashboard")
    with app.app_context():
        customer = Customer.query.filter_by(phone=None).one()
        identity = CustomerIdentity.query.filter_by(provider="google").one()
        assert identity.customer_id == customer.id
        assert identity.provider_subject == claims["sub"]
        assert customer.name == "Google Person"


def test_google_existing_customer_login(client, app, monkeypatch):
    app.config.update(
        GOOGLE_CLIENT_ID="test-google-client-id",
        GOOGLE_CLIENT_SECRET="test-google-client-secret",
        GOOGLE_REDIRECT_URI="http://localhost/auth/google/callback",
    )
    with app.app_context():
        customer = Customer(phone=None, name="Existing Google Customer")
        identity = CustomerIdentity(
            customer=customer,
            provider="google",
            provider_subject="existing-subject",
            email="existing@example.com",
            email_verified=True,
        )
        db.session.add_all([customer, identity])
        db.session.commit()

    claims = _google_claims("existing-subject", "different@example.com")
    monkeypatch.setattr(oauth.google, "authorize_access_token", lambda **kwargs: {"userinfo": claims})
    response = client.get("/auth/google/callback")

    assert response.status_code == 302
    with app.app_context():
        assert Customer.query.count() == 2
        assert CustomerIdentity.query.filter_by(provider="google").count() == 1


@pytest.mark.parametrize("callback_url", [
    "/auth/google/callback",
    "/auth/google/callback?error=access_denied",
])
def test_google_callback_failure(client, monkeypatch, callback_url):
    def fail(**kwargs):
        raise ValueError("invalid callback")

    monkeypatch.setattr(oauth.google, "authorize_access_token", fail)
    response = client.get(callback_url)
    assert response.status_code == 400
    assert response.location.endswith("/auth/customer-login")


def test_google_invalid_state(client, monkeypatch):
    def fail(**kwargs):
        raise ValueError("invalid state")

    monkeypatch.setattr(oauth.google, "authorize_access_token", fail)
    response = client.get("/auth/google/callback?code=code&state=bad")
    assert response.status_code == 400


def test_google_invalid_token(client, monkeypatch):
    monkeypatch.setattr(
        oauth.google,
        "authorize_access_token",
        lambda **kwargs: {"userinfo": {"sub": "missing-required-claims"}},
    )
    response = client.get("/auth/google/callback?code=code&state=state")
    assert response.status_code == 400


def test_google_duplicate_identity_constraint(app):
    with app.app_context():
        first = Customer(phone=None, name="First")
        second = Customer(phone=None, name="Second")
        db.session.add_all([first, second])
        db.session.flush()
        db.session.add_all([
            CustomerIdentity(customer_id=first.id, provider="google", provider_subject="same-subject"),
            CustomerIdentity(customer_id=second.id, provider="google", provider_subject="same-subject"),
        ])
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_google_unsafe_next_url_is_ignored(client, app, monkeypatch):
    app.config.update(
        GOOGLE_CLIENT_ID="test-google-client-id",
        GOOGLE_CLIENT_SECRET="test-google-client-secret",
        GOOGLE_REDIRECT_URI="http://localhost/auth/google/callback",
    )
    authorize_calls = []

    def start(redirect_uri, **kwargs):
        authorize_calls.append(kwargs)
        return "redirected"

    monkeypatch.setattr(oauth.google, "authorize_redirect", start)
    response = client.get("/auth/google/login?next=https://evil.example/steal")
    assert response.status_code == 200
    with client.session_transaction() as state:
        assert state.get("google_next") is None
    assert authorize_calls


def test_existing_phone_login_unchanged(client, app):
    response = client.post("/auth/customer-login", data={
        "name": "Phone Customer",
        "phone": "9123456789",
    })
    assert response.status_code == 302
    assert response.location.endswith("/my/dashboard")
    with app.app_context():
        customer = Customer.query.filter_by(phone="9123456789").one()
        assert customer.name == "Phone Customer"
