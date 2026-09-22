import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Tuple
from app.extensions import db
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus, PaymentMode
from app.services.audit_service import AuditService
from app.models.audit_log import AuditAction


class PaymentService:
    """
    Payment abstraction layer.
    Uses Sandbox/Test mode for local development. Never processes real money in dev.
    """

    @staticmethod
    def create_pending_payment(booking: Booking, provider: str = "SANDBOX_MOCK") -> Payment:
        """Create or return an existing pending payment record for a booking."""
        existing = Payment.query.filter_by(booking_id=booking.id).first()
        if existing:
            return existing

        payment = Payment(
            booking_id=booking.id,
            amount=booking.amount,
            status=PaymentStatus.PENDING,
            provider=provider,
            payment_mode=PaymentMode.SANDBOX,
        )
        db.session.add(payment)
        db.session.commit()
        return payment

    @staticmethod
    def verify_sandbox_payment(
        booking: Booking, 
        simulate_success: bool = True
    ) -> Tuple[bool, str]:
        """
        Simulate sandbox payment verification.
        On success:
          1. Sets Payment status to SUCCESSFUL
          2. Sets Booking status to CONFIRMED
          3. Generates transaction ID
          4. Logs audit event
        On failure:
          1. Sets Payment status to FAILED
          2. Keeps booking unconfirmed or cancels it
        """
        payment = Payment.query.filter_by(booking_id=booking.id).first()
        if not payment:
            payment = PaymentService.create_pending_payment(booking)

        if not simulate_success:
            payment.status = PaymentStatus.FAILED
            booking.status = BookingStatus.CANCELLED
            booking.cancellation_reason = "Payment failed or was cancelled by user"
            db.session.commit()
            
            AuditService.log(
                action="PAYMENT_FAILED",
                target_type="booking",
                target_id=booking.id,
                details={"booking_uid": booking.booking_uid, "amount": str(booking.amount)},
            )
            return False, "Sandbox payment simulated as failed."

        # Mark as successful
        txn_id = f"SANDBOX-TXN-{uuid.uuid4().hex[:12].upper()}"
        payment.status = PaymentStatus.SUCCESSFUL
        payment.provider_txn_id = txn_id
        payment.paid_at = datetime.utcnow()
        
        # Confirm booking and lock the date
        booking.status = BookingStatus.CONFIRMED
        db.session.commit()

        AuditService.log(
            action="PAYMENT_SUCCESS",
            target_type="booking",
            target_id=booking.id,
            details={
                "booking_uid": booking.booking_uid,
                "amount": str(booking.amount),
                "txn_id": txn_id,
                "mode": "SANDBOX",
            },
        )
        return True, "Payment verified successfully in sandbox mode."

    @staticmethod
    def process_refund_record(
        booking: Booking,
        refund_amount: Decimal,
        reason: str,
        requested_by_id: int,
        approved_by_id: int,
    ) -> Tuple[bool, str]:
        """
        Record refund in database without falsely claiming a third-party gateway refund succeeded.
        """
        payment = Payment.query.filter_by(booking_id=booking.id).first()
        if not payment:
            return False, "No payment found for this booking."

        payment.refund_amount = refund_amount
        payment.refund_reason = reason
        payment.refund_requested_by = requested_by_id
        payment.refund_approved_by = approved_by_id
        payment.refunded_at = datetime.utcnow()

        if refund_amount >= payment.amount:
            payment.status = PaymentStatus.REFUNDED
            payment.refund_status = "FULL_REFUND_RECORDED"
        elif refund_amount > 0:
            payment.status = PaymentStatus.PARTIALLY_REFUNDED
            payment.refund_status = "PARTIAL_REFUND_RECORDED"
        else:
            payment.refund_status = "NO_REFUND_APPLICABLE"

        db.session.commit()

        AuditService.log(
            action=AuditAction.REFUND_PROCESSED,
            target_type="booking",
            target_id=booking.id,
            details={
                "refund_amount": str(refund_amount),
                "reason": reason,
                "status": payment.status,
            },
        )
        return True, "Refund recorded successfully."
