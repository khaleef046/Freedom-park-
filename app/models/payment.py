from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Integer, Numeric, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.extensions import db


class PaymentStatus:
    """Payment transaction states (kept separate from booking status)."""
    PENDING = "PENDING"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"
    REFUND_PENDING = "REFUND_PENDING"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"

    ALL = [PENDING, SUCCESSFUL, FAILED, REFUND_PENDING, REFUNDED, PARTIALLY_REFUNDED]


class PaymentMode:
    """Mode of payment processing."""
    SANDBOX = "SANDBOX"
    LIVE = "LIVE"
    CASH = "CASH"  # Admin manual collection


class Payment(db.Model):
    """Payment record linked to a single booking."""
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("bookings.id"), nullable=False, unique=True)
    
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(25), nullable=False, default=PaymentStatus.PENDING, index=True
    )
    
    provider: Mapped[str] = mapped_column(String(50), default="SANDBOX_MOCK")
    provider_txn_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_mode: Mapped[str] = mapped_column(String(20), default=PaymentMode.SANDBOX)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Refund tracking (built for business logic & future real provider integration)
    refund_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    refund_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refund_requested_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    refund_approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    refund_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    refunded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow, nullable=True)

    # Relationships
    booking = relationship("Booking", back_populates="payment")
    refund_requester = relationship("User", foreign_keys=[refund_requested_by])
    refund_approver = relationship("User", foreign_keys=[refund_approved_by])

    @property
    def is_successful(self) -> bool:
        return self.status == PaymentStatus.SUCCESSFUL

    def __repr__(self) -> str:
        return f"<Payment {self.id} for Booking {self.booking_id} [{self.status}] ₹{self.amount}>"
