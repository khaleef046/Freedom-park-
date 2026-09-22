from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.extensions import db


class CommissionStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PAID = "PAID"
    CANCELLED = "CANCELLED"

    ALL = [PENDING, APPROVED, PAID, CANCELLED]


class CommissionRecord(db.Model):
    """Tracks fixed per-booking commission earned by Staff Partners."""
    __tablename__ = "commission_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("bookings.id"), nullable=False, unique=True)
    staff_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=CommissionStatus.PENDING, index=True)
    
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    booking = relationship("Booking", back_populates="commission")
    staff_user = relationship("User", foreign_keys=[staff_user_id], back_populates="commissions")
    approver = relationship("User", foreign_keys=[approved_by])

    def __repr__(self) -> str:
        return f"<CommissionRecord ₹{self.amount} for User {self.staff_user_id} [{self.status}]>"
