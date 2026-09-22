from datetime import date, timedelta
from decimal import Decimal
import pytest
from app.extensions import db
from app.models.booking import Booking, BookingStatus, BookingSource, BlockedDate
from app.models.user import Customer, User
from app.services.booking_service import BookingService
from app.services.payment_service import PaymentService


def test_date_availability_past_rejected(app):
    with app.app_context():
        past_date = date.today() - timedelta(days=1)
        available, msg = BookingService.is_date_available(past_date)
        assert available is False
        assert "past" in msg.lower()


def test_date_availability_valid_future(app):
    with app.app_context():
        future_date = date.today() + timedelta(days=10)
        available, msg = BookingService.is_date_available(future_date)
        assert available is True


def test_capacity_validation(app):
    with app.app_context():
        target_date = date.today() + timedelta(days=5)
        # 0 guests should fail
        b, msg = BookingService.create_customer_booking(
            customer_id=1, booking_date=target_date, customer_name="Test",
            customer_phone="9876543210", num_people=0
        )
        assert b is None
        assert "between 1 and 100" in msg

        # 101 guests should fail
        b, msg = BookingService.create_customer_booking(
            customer_id=1, booking_date=target_date, customer_name="Test",
            customer_phone="9876543210", num_people=101
        )
        assert b is None
        assert "between 1 and 100" in msg


def test_price_calculation_dynamic(app):
    with app.app_context():
        # Find next Saturday (weekday() == 5)
        d = date.today()
        while d.weekday() != 5:
            d += timedelta(days=1)
        weekend_price = BookingService.calculate_price_for_date(d)
        assert weekend_price == Decimal("3000.00")

        # Find next Wednesday (weekday() == 2)
        while d.weekday() != 2:
            d += timedelta(days=1)
        weekday_price = BookingService.calculate_price_for_date(d)
        assert weekday_price == Decimal("2000.00")


def test_booking_creation_and_sandbox_payment(app):
    with app.app_context():
        cust = Customer.query.first()
        target_date = date.today() + timedelta(days=7)

        booking, msg = BookingService.create_customer_booking(
            customer_id=cust.id,
            booking_date=target_date,
            customer_name="Test Guest",
            customer_phone="9876543210",
            num_people=20,
        )
        assert booking is not None
        assert booking.status == BookingStatus.PENDING_PAYMENT
        assert booking.booking_uid.startswith("FP-")

        # Verify payment sandbox
        success, p_msg = PaymentService.verify_sandbox_payment(booking, simulate_success=True)
        assert success is True
        assert booking.status == BookingStatus.CONFIRMED

        # Date should now be booked and unavailable
        available, a_msg = BookingService.is_date_available(target_date)
        assert available is False
        assert "already been booked" in a_msg


def test_prevent_double_booking_same_date(app):
    """CRITICAL TEST: Ensure two bookings can NEVER exist for the same date."""
    with app.app_context():
        cust = Customer.query.first()
        target_date = date.today() + timedelta(days=12)

        # Booking 1
        b1, _ = BookingService.create_customer_booking(
            customer_id=cust.id,
            booking_date=target_date,
            customer_name="First Guest",
            customer_phone="9876543210",
            num_people=15,
        )
        assert b1 is not None

        # Booking 2 for same date must be rejected by service
        b2, msg2 = BookingService.create_customer_booking(
            customer_id=cust.id,
            booking_date=target_date,
            customer_name="Second Guest",
            customer_phone="9876543210",
            num_people=30,
        )
        assert b2 is None
        assert "already been booked" in msg2


def test_cancellation_and_refund_calculation(app):
    with app.app_context():
        target_date = date.today() + timedelta(days=15)
        booking, _ = BookingService.create_manual_booking(
            booking_date=target_date,
            customer_name="Refund Test",
            customer_phone="9876543210",
            num_people=10,
            source=BookingSource.PHONE,
            created_by_user_id=1,
            custom_amount=Decimal("2000.00"),
        )
        assert booking.status == BookingStatus.CONFIRMED

        # Cancelled > 24 hours in advance -> 50% refund
        refund_amount, exp = BookingService.calculate_refund_amount(booking, is_park_cancellation=False)
        assert refund_amount == Decimal("1000.00")

        # If Park cancels -> 100% refund
        park_refund, exp_park = BookingService.calculate_refund_amount(booking, is_park_cancellation=True)
        assert park_refund == Decimal("2000.00")

        # Execute cancellation
        success, c_msg = BookingService.cancel_booking(booking.id, "Customer request", 1)
        assert success is True
        assert booking.status == BookingStatus.CANCELLED

        # Date is released and available again!
        available, _ = BookingService.is_date_available(target_date)
        assert available is True


def test_emergency_date_locking(app):
    with app.app_context():
        target_date = date.today() + timedelta(days=20)
        success, msg = BookingService.lock_emergency_date(target_date, "Scheduled Lawn Renovation", 1)
        assert success is True

        # Date is unavailable
        available, a_msg = BookingService.is_date_available(target_date)
        assert available is False
        assert "Scheduled Lawn Renovation" in a_msg

        # Unlock
        unlocked, u_msg = BookingService.unlock_date(target_date, 1)
        assert unlocked is True
        assert BookingService.is_date_available(target_date)[0] is True
