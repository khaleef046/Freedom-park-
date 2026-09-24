from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.models.booking import Booking, BookingSource, BookingStatus
from app.models.feedback import Feedback, FeedbackStatus
from app.services.feedback_service import FeedbackService


def _customer_booking(app, booking_uid="FP-FEEDBACK-1"):
    with app.app_context():
        booking = Booking(
            booking_uid=booking_uid,
            booking_date=datetime.now().date(),
            customer_id=1,
            customer_name="Test Customer",
            customer_phone="9876543210",
            num_people=2,
            amount=Decimal("2000.00"),
            status=BookingStatus.CONFIRMED,
            source=BookingSource.WEBSITE,
        )
        db.session.add(booking)
        db.session.commit()
        return booking.booking_uid


def _login_customer(client):
    response = client.post("/auth/customer-login", data={
        "name": "Test Customer",
        "phone": "9876543210",
    })
    assert response.status_code == 302


def test_feedback_window_and_guest_hub(client, app, monkeypatch):
    booking_uid = _customer_booking(app)
    end = datetime.combine(datetime.now().date(), time(20, 0))
    monkeypatch.setattr(FeedbackService, "now", staticmethod(lambda: end - timedelta(minutes=1)))
    _login_customer(client)
    assert client.get(f"/my/feedback/{booking_uid}").status_code == 302

    monkeypatch.setattr(FeedbackService, "now", staticmethod(lambda: end + timedelta(hours=1)))
    response = client.get("/my/dashboard")
    assert b"How was your experience?" in response.data
    hub = client.get(f"/guest-hub/{booking_uid}")
    assert hub.status_code == 200
    assert b"Share Your Feedback" in hub.data
    assert b"Test Customer" not in hub.data

    monkeypatch.setattr(FeedbackService, "now", staticmethod(lambda: end + timedelta(hours=25)))
    assert client.get(f"/my/feedback/{booking_uid}").status_code == 302


@pytest.mark.parametrize("rating, message, expected_status", [
    (5, "", 302),
    (3, "", 302),
    (1, "Needs cleaner changing rooms", 302),
])
def test_feedback_rating_storage_and_low_rating_validation(client, app, monkeypatch, rating, message, expected_status):
    booking_uid = _customer_booking(app, f"FP-FEEDBACK-{rating}")
    end = datetime.combine(datetime.now().date(), time(20, 0))
    monkeypatch.setattr(FeedbackService, "now", staticmethod(lambda: end + timedelta(hours=1)))
    _login_customer(client)
    response = client.post(f"/my/feedback/{booking_uid}", data={"rating": rating, "message": message})
    assert response.status_code == expected_status
    with app.app_context():
        booking = Booking.query.filter_by(booking_uid=booking_uid).one()
        feedback = Feedback.query.filter_by(booking_id=booking.id).first()
        if rating in (1, 3, 5):
            assert feedback is not None
            assert feedback.rating == rating
            assert feedback.status == FeedbackStatus.NEW


def test_low_rating_requires_reason_and_duplicate_is_blocked(client, app, monkeypatch):
    booking_uid = _customer_booking(app, "FP-FEEDBACK-LOW")
    end = datetime.combine(datetime.now().date(), time(20, 0))
    monkeypatch.setattr(FeedbackService, "now", staticmethod(lambda: end + timedelta(hours=1)))
    _login_customer(client)
    response = client.post(f"/my/feedback/{booking_uid}", data={"rating": 2, "message": ""})
    assert response.status_code == 200
    with app.app_context():
        assert Feedback.query.count() == 0
    response = client.post(f"/my/feedback/{booking_uid}", data={"rating": 2, "message": "Please improve the shade"})
    assert response.status_code == 302
    assert client.get(f"/my/feedback/{booking_uid}").status_code == 302


def test_feedback_admin_permissions(client, app, monkeypatch):
    booking_uid = _customer_booking(app, "FP-FEEDBACK-ADMIN")
    end = datetime.combine(datetime.now().date(), time(20, 0))
    monkeypatch.setattr(FeedbackService, "now", staticmethod(lambda: end + timedelta(hours=1)))
    _login_customer(client)
    client.post(f"/my/feedback/{booking_uid}", data={"rating": 4, "message": "Lovely day"})
    client.get("/auth/logout")

    client.post("/auth/staff-login", data={"username": "test_owner", "password": "pass123"})
    response = client.get("/admin/feedback")
    assert response.status_code == 200
    assert b"Total feedback" in response.data
    client.get("/auth/logout")
    for username in ("test_partner", "test_security"):
        client.post("/auth/staff-login", data={"username": username, "password": "pass123"})
        assert client.get("/admin/feedback").status_code == 403
        client.get("/auth/logout")