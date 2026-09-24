from datetime import date, timedelta
from decimal import Decimal

from app.extensions import db
from app.models.booking import BlockedDate, Booking, BookingSource, BookingStatus
from app.services.booking_service import BookingService


def test_staff_partner_can_share_only_available_dates(client, app):
    with app.app_context():
        target_booked = date.today() + timedelta(days=2)
        target_blocked = date.today() + timedelta(days=3)
        db.session.add(BlockedDate(blocked_date=target_blocked, reason="Maintenance"))
        db.session.add(Booking(
            booking_uid="FP-TEST-SHARE-1",
            booking_date=target_booked,
            customer_name="Private Customer",
            customer_phone="9999999999",
            num_people=2,
            amount=Decimal("2000.00"),
            status=BookingStatus.CONFIRMED,
            source=BookingSource.WEBSITE,
        ))
        db.session.commit()

    response = client.post(
        "/auth/staff-login",
        data={"username": "test_partner", "password": "pass123"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    response = client.get("/staff/share-availability")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "WhatsApp message" in body
    assert "Private Customer" not in body
    assert target_booked.strftime("%d %b %Y") not in body
    assert target_blocked.strftime("%d %b %Y") not in body
    assert "Weekday rate" in body or "Weekend rate" in body
    assert "https://wa.me/?text=" in body


def test_staff_partner_share_availability_uses_booking_price_rules(app):
    with app.app_context():
        saturday = date.today()
        while saturday.weekday() != 5:
            saturday += timedelta(days=1)
        assert BookingService.calculate_price_for_date(saturday) == Decimal("3000.00")