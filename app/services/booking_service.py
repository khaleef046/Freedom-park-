import calendar
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, Tuple, List, Dict
from sqlalchemy import func, or_
from app.extensions import db
from app.models.booking import Booking, BlockedDate, BookingStatus, BookingSource
from app.models.payment import Payment, PaymentStatus, PaymentMode
from app.models.commission import CommissionRecord, CommissionStatus
from app.models.audit_log import AuditAction
from app.services.settings_service import SettingsService
from app.services.audit_service import AuditService
from app.utils.helpers import generate_booking_uid, normalize_phone


class BookingService:
    """
    Central Booking Service — Single Source of Truth for Park Availability and State Transitions.
    Enforces concurrency checks, transactions, and business rules.
    """

    @classmethod
    def calculate_price_for_date(cls, target_date: date) -> Decimal:
        """
        Calculate fixed day price based on day of week from dynamic settings.
        Saturday (5) and Sunday (6) are weekends.
        """
        if target_date.weekday() >= 5:  # Saturday or Sunday
            return SettingsService.get_decimal("weekend_price", Decimal("3000.00"))
        return SettingsService.get_decimal("weekday_price", Decimal("2000.00"))

    @classmethod
    def is_date_available(cls, target_date: date) -> Tuple[bool, str]:
        """
        Validate whether a specific date is open for booking.
        Enforces:
          1. Not in the past
          2. Within booking window (admin-configurable)
          3. Not manually blocked
          4. Not already booked by any active booking
        """
        today = date.today()
        if target_date < today:
            return False, "This date is in the past."

        # Booking window validation
        window_days = SettingsService.get_int("booking_window_days", 30)
        max_date = today + timedelta(days=window_days)
        if target_date > max_date:
            return False, f"Bookings are currently only accepted up to {window_days} days in advance."

        # Check manually blocked dates
        blocked = BlockedDate.query.filter_by(blocked_date=target_date).first()
        if blocked:
            return False, f"Date is unavailable: {blocked.reason}"

        # Check existing active bookings (PENDING_PAYMENT or CONFIRMED)
        existing = Booking.query.filter(
            Booking.booking_date == target_date,
            Booking.status.in_(BookingStatus.ACTIVE_STATUSES),
        ).first()
        if existing:
            return False, "This date has already been booked by another guest."

        return True, "Date is available."

    @classmethod
    def get_date_status(cls, target_date: date) -> str:
        """Return one of: 'PAST', 'BLOCKED', 'BOOKED', 'AVAILABLE'."""
        today = date.today()
        if target_date < today:
            return "PAST"

        if BlockedDate.query.filter_by(blocked_date=target_date).first():
            return "BLOCKED"

        active_booking = Booking.query.filter(
            Booking.booking_date == target_date,
            Booking.status.in_(BookingStatus.ACTIVE_STATUSES),
        ).first()
        if active_booking:
            return "BOOKED"

        return "AVAILABLE"

    @classmethod
    def get_calendar_month_data(cls, year: int, month: int) -> List[Dict]:
        """Generate structured calendar data for month with availability and pricing."""
        num_days = calendar.monthrange(year, month)[1]
        days_data = []

        for day in range(1, num_days + 1):
            d = date(year, month, day)
            status = cls.get_date_status(d)
            price = cls.calculate_price_for_date(d)
            days_data.append({
                "date": d.isoformat(),
                "day": day,
                "weekday": d.strftime("%A"),
                "status": status,
                "price": float(price),
                "is_weekend": d.weekday() >= 5,
            })
        return days_data

    @classmethod
    def _next_booking_uid(cls, year: int) -> str:
        """Generate next sequence UID, e.g. FP-2026-0001."""
        count = db.session.query(func.count(Booking.id)).filter(
            func.strftime("%Y", Booking.created_at) == str(year)
        ).scalar() or 0
        return generate_booking_uid(year, count + 1)

    @classmethod
    def create_customer_booking(
        cls,
        customer_id: int,
        booking_date: date,
        customer_name: str,
        customer_phone: str,
        num_people: int,
        special_requests: Optional[str] = None,
        staff_partner_id: Optional[int] = None,
    ) -> Tuple[Optional[Booking], str]:
        """
        Initiate an online customer booking in PENDING_PAYMENT state.
        Uses database transaction to guarantee no double-booking.
        """
        # Validate capacity
        max_cap = SettingsService.get_int("max_capacity", 100)
        if num_people < 1 or num_people > max_cap:
            return None, f"Number of guests must be between 1 and {max_cap}."

        # Server-side availability verification
        available, msg = cls.is_date_available(booking_date)
        if not available:
            return None, msg

        # Authoritative server pricing
        amount = cls.calculate_price_for_date(booking_date)
        year = booking_date.year

        try:
            # Transaction block
            uid = cls._next_booking_uid(year)
            booking = Booking(
                booking_uid=uid,
                booking_date=booking_date,
                customer_id=customer_id,
                customer_name=customer_name.strip(),
                customer_phone=normalize_phone(customer_phone),
                num_people=num_people,
                amount=amount,
                status=BookingStatus.PENDING_PAYMENT,
                source=BookingSource.WEBSITE,
                special_requests=special_requests,
                staff_partner_id=staff_partner_id,
            )
            db.session.add(booking)
            db.session.flush()  # Flushes and verifies DB constraints without final commit

            # Create associated pending payment
            payment = Payment(
                booking_id=booking.id,
                amount=amount,
                status=PaymentStatus.PENDING,
                provider="SANDBOX_MOCK",
                payment_mode=PaymentMode.SANDBOX,
            )
            db.session.add(payment)
            db.session.commit()

            AuditService.log(
                action=AuditAction.BOOKING_CREATED,
                target_type="booking",
                target_id=booking.id,
                details={"uid": uid, "date": str(booking_date), "amount": str(amount), "status": booking.status},
            )
            return booking, "Booking initiated successfully. Please proceed with payment."
        except Exception as e:
            db.session.rollback()
            return None, f"Booking creation failed: {str(e)}"

    @classmethod
    def create_manual_booking(
        cls,
        booking_date: date,
        customer_name: str,
        customer_phone: str,
        num_people: int,
        source: str,
        created_by_user_id: int,
        staff_partner_id: Optional[int] = None,
        notes: Optional[str] = None,
        custom_amount: Optional[Decimal] = None,
    ) -> Tuple[Optional[Booking], str]:
        """
        Create a direct manual booking by Admin, Owner, or Staff Partner.
        Locks the date immediately into CONFIRMED state.
        """
        # Validate date availability (past dates cannot be booked)
        if booking_date < date.today():
            return None, "Cannot create a booking on a past date."

        blocked = BlockedDate.query.filter_by(blocked_date=booking_date).first()
        if blocked:
            return None, f"This date is blocked: {blocked.reason}"

        existing = Booking.query.filter(
            Booking.booking_date == booking_date,
            Booking.status.in_(BookingStatus.ACTIVE_STATUSES),
        ).first()
        if existing:
            return None, f"This date is already booked ({existing.booking_uid})."

        max_cap = SettingsService.get_int("max_capacity", 100)
        if num_people < 1 or num_people > max_cap:
            return None, f"Number of guests must be between 1 and {max_cap}."

        amount = custom_amount if custom_amount is not None else cls.calculate_price_for_date(booking_date)
        year = booking_date.year

        try:
            uid = cls._next_booking_uid(year)
            booking = Booking(
                booking_uid=uid,
                booking_date=booking_date,
                customer_name=customer_name.strip(),
                customer_phone=normalize_phone(customer_phone),
                num_people=num_people,
                amount=amount,
                status=BookingStatus.CONFIRMED,
                source=source,
                notes=notes,
                created_by=created_by_user_id,
                staff_partner_id=staff_partner_id,
            )
            db.session.add(booking)
            db.session.flush()

            # Record cash/manual payment
            payment = Payment(
                booking_id=booking.id,
                amount=amount,
                status=PaymentStatus.SUCCESSFUL,
                provider="MANUAL_CASH",
                payment_mode=PaymentMode.CASH,
                paid_at=datetime.utcnow(),
            )
            db.session.add(payment)

            # If created by / for a Staff Partner, record commission
            if staff_partner_id:
                comm_amount = SettingsService.get_decimal("default_commission", Decimal("500.00"))
                commission = CommissionRecord(
                    booking_id=booking.id,
                    staff_user_id=staff_partner_id,
                    amount=comm_amount,
                    status=CommissionStatus.PENDING,
                )
                db.session.add(commission)

            db.session.commit()

            AuditService.log(
                action=AuditAction.BOOKING_CREATED,
                target_type="booking",
                target_id=booking.id,
                details={"uid": uid, "date": str(booking_date), "source": source, "amount": str(amount)},
                user_id=created_by_user_id,
            )
            return booking, "Manual booking created and date locked successfully."
        except Exception as e:
            db.session.rollback()
            return None, f"Failed to create manual booking: {str(e)}"

    @classmethod
    def calculate_refund_amount(cls, booking: Booking, is_park_cancellation: bool = False) -> Tuple[Decimal, str]:
        """
        Calculate refund according to business policy:
        - If Park cancels: 100% refund
        - If Customer cancels:
          - >= threshold hours (default 24h): 50% refund
          - < threshold hours: 0% refund
        """
        if is_park_cancellation:
            return booking.amount, "Park cancellation policy: 100% full refund."

        booking_datetime = datetime.combine(booking.booking_date, datetime.min.time()) + timedelta(hours=8)
        hours_until = (booking_datetime - datetime.utcnow()).total_seconds() / 3600

        threshold = SettingsService.get_int("customer_cancel_threshold_hours", 24)
        if hours_until >= threshold:
            pct = SettingsService.get_decimal("customer_cancel_refund_before", Decimal("50"))
            refund = (booking.amount * pct) / Decimal("100")
            return refund, f"Customer cancelled {hours_until:.1f} hrs in advance ({pct}% refund applied)."
        else:
            pct = SettingsService.get_decimal("customer_cancel_refund_after", Decimal("0"))
            refund = (booking.amount * pct) / Decimal("100")
            return refund, f"Customer cancelled within {threshold} hrs window ({pct}% refund applied)."

    @classmethod
    def cancel_booking(
        cls,
        booking_id: int,
        reason: str,
        cancelled_by_user_id: Optional[int] = None,
        is_park_cancellation: bool = False,
    ) -> Tuple[bool, str]:
        """
        Cancel a booking, release the locked date, process refund record,
        and update any associated commission records.
        """
        booking = db.session.get(Booking, booking_id)
        if not booking:
            return False, "Booking not found."

        if booking.status == BookingStatus.CANCELLED:
            return False, "Booking is already cancelled."

        refund_amount, refund_explanation = cls.calculate_refund_amount(booking, is_park_cancellation)

        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = datetime.utcnow()
        booking.cancelled_by = cancelled_by_user_id
        booking.cancellation_reason = f"{reason} | {refund_explanation}"

        # If booking had an associated staff commission, cancel it
        if booking.commission and booking.commission.status != CommissionStatus.PAID:
            booking.commission.status = CommissionStatus.CANCELLED

        # Record refund on payment
        if booking.payment:
            booking.payment.refund_amount = refund_amount
            booking.payment.refund_reason = reason
            booking.payment.refund_requested_by = cancelled_by_user_id
            booking.payment.refunded_at = datetime.utcnow()
            if refund_amount >= booking.amount:
                booking.payment.status = PaymentStatus.REFUNDED
            elif refund_amount > Decimal("0"):
                booking.payment.status = PaymentStatus.PARTIALLY_REFUNDED

        db.session.commit()

        AuditService.log(
            action=AuditAction.BOOKING_CANCELLED,
            target_type="booking",
            target_id=booking.id,
            details={"uid": booking.booking_uid, "refund": str(refund_amount), "reason": reason},
            user_id=cancelled_by_user_id,
        )
        return True, f"Booking {booking.booking_uid} has been cancelled. {refund_explanation}"

    @classmethod
    def lock_emergency_date(cls, target_date: date, reason: str, user_id: int) -> Tuple[bool, str]:
        """Emergency lock of date by Admin / Super Admin."""
        if target_date < date.today():
            return False, "Cannot block past dates."

        existing = Booking.query.filter(
            Booking.booking_date == target_date,
            Booking.status.in_(BookingStatus.ACTIVE_STATUSES),
        ).first()
        if existing:
            return False, f"Cannot block this date: Active booking exists ({existing.booking_uid})."

        blocked = BlockedDate.query.filter_by(blocked_date=target_date).first()
        if blocked:
            return False, "This date is already blocked."

        new_blocked = BlockedDate(
            blocked_date=target_date,
            reason=reason.strip(),
            blocked_by=user_id,
        )
        db.session.add(new_blocked)
        db.session.commit()

        AuditService.log(
            action=AuditAction.DATE_BLOCKED,
            target_type="blocked_date",
            details={"date": str(target_date), "reason": reason},
            user_id=user_id,
        )
        return True, f"Date {target_date} is now emergency locked."

    @classmethod
    def unlock_date(cls, target_date: date, user_id: int) -> Tuple[bool, str]:
        """Remove emergency block on a date."""
        blocked = BlockedDate.query.filter_by(blocked_date=target_date).first()
        if not blocked:
            return False, "Date is not currently blocked."

        db.session.delete(blocked)
        db.session.commit()

        AuditService.log(
            action=AuditAction.DATE_UNBLOCKED,
            target_type="blocked_date",
            details={"date": str(target_date)},
            user_id=user_id,
        )
        return True, f"Date {target_date} has been unblocked."
