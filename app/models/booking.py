from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    String, Integer, Numeric, Date, DateTime, Text, ForeignKey, 
    Index, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.extensions import db


class BookingStatus:
    """Booking state machine statuses."""
    PENDING_PAYMENT = "PENDING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    
    ALL = [PENDING_PAYMENT, CONFIRMED, CANCELLED, COMPLETED]
    ACTIVE_STATUSES = [PENDING_PAYMENT, CONFIRMED]


class BookingSource:
    """Sources where bookings originate."""
    WEBSITE = "WEBSITE"
    PHONE = "PHONE"
    WHATSAPP = "WHATSAPP"
    STAFF_PARTNER = "STAFF_PARTNER"
    ADMIN = "ADMIN"

    ALL = [WEBSITE, PHONE, WHATSAPP, STAFF_PARTNER, ADMIN]


class Booking(db.Model):
    """
    Central Booking model — Single Source of Truth for park dates.
    Enforces one booking per date across all channels.
    """
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("num_people >= 1 AND num_people <= 100", name="chk_booking_capacity"),
        # Partial unique index prevents double booking on active dates at database level
        Index(
            "uq_active_booking_date",
            "booking_date",
            unique=True,
            sqlite_where=(
                (db.column("status") == BookingStatus.CONFIRMED) | 
                (db.column("status") == BookingStatus.PENDING_PAYMENT)
            ),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_uid: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("customers.id"), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    num_people: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Financials (Server-validated; never trusted from client)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    
    status: Mapped[str] = mapped_column(
        String(25), nullable=False, default=BookingStatus.PENDING_PAYMENT, index=True
    )
    source: Mapped[str] = mapped_column(
        String(25), nullable=False, default=BookingSource.WEBSITE
    )
    
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    special_requests: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    staff_partner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Cancellation Details
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow, nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="bookings")
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_bookings")
    staff_partner = relationship("User", foreign_keys=[staff_partner_id], back_populates="partner_bookings")
    payment = relationship("Payment", back_populates="booking", uselist=False, cascade="all, delete-orphan")
    cancellation_requests = relationship("CancellationRequest", back_populates="booking", cascade="all, delete-orphan")
    checklists = relationship("EquipmentChecklist", back_populates="booking", cascade="all, delete-orphan")
    equipment_reports = relationship("EquipmentReport", back_populates="booking", cascade="all, delete-orphan")
    commission = relationship("CommissionRecord", back_populates="booking", uselist=False, cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="booking", uselist=False)
    complaints = relationship("Complaint", back_populates="booking")

    @property
    def is_active(self) -> bool:
        return self.status in BookingStatus.ACTIVE_STATUSES

    @property
    def is_confirmed(self) -> bool:
        return self.status == BookingStatus.CONFIRMED

    @property
    def is_cancelled(self) -> bool:
        return self.status == BookingStatus.CANCELLED

    @property
    def is_past(self) -> bool:
        return self.booking_date < date.today()

    @property
    def is_today(self) -> bool:
        return self.booking_date == date.today()

    def __repr__(self) -> str:
        return f"<Booking {self.booking_uid} on {self.booking_date} [{self.status}]>"


class BlockedDate(db.Model):
    """
    Emergency / Maintenance dates manually blocked by Admin / Super Admin.
    Kept separate from bookings table to avoid schema confusion.
    """
    __tablename__ = "blocked_dates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blocked_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    blocked_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    blocker = relationship("User", foreign_keys=[blocked_by])

    def __repr__(self) -> str:
        return f"<BlockedDate {self.blocked_date}: {self.reason[:20]}>"
