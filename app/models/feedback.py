from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.extensions import db


class FeedbackCategory:
    POSITIVE = "Positive Feedback"
    SUGGESTION = "Suggestion"
    IMPROVEMENT = "Improvement"
    COMPLAINT = "Complaint"
    FACILITY_ISSUE = "Facility Issue"
    EQUIPMENT_ISSUE = "Equipment Issue"
    OTHER = "Other"

    ALL = [POSITIVE, SUGGESTION, IMPROVEMENT, COMPLAINT, FACILITY_ISSUE, EQUIPMENT_ISSUE, OTHER]


class FeedbackStatus:
    NEW = "NEW"
    REVIEWED = "REVIEWED"
    REVIEWING = "REVIEWING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class ComplaintPriority:
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class Feedback(db.Model):
    """Customer post-visit feedback with ratings and optional photos."""
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="chk_feedback_rating"),
        UniqueConstraint("booking_id", name="uq_feedback_booking"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("customers.id"), nullable=True)
    booking_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("bookings.id"), nullable=True)
    
    category: Mapped[str] = mapped_column(String(50), default=FeedbackCategory.GENERAL if hasattr(FeedbackCategory, 'GENERAL') else FeedbackCategory.POSITIVE)
    rating: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    photo_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    status: Mapped[str] = mapped_column(String(20), default=FeedbackStatus.NEW)
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="feedback_list")
    booking = relationship("Booking", back_populates="feedback")

    def __repr__(self) -> str:
        return f"<Feedback {self.id}: {self.rating} stars [{self.status}]>"


class Complaint(db.Model):
    """Formal customer complaints requiring administrative investigation."""
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("customers.id"), nullable=True)
    booking_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("bookings.id"), nullable=True)
    
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default=ComplaintPriority.NORMAL)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    photo_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    status: Mapped[str] = mapped_column(String(20), default="NEW")  # NEW, IN_PROGRESS, RESOLVED, CLOSED
    assigned_to: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="complaints")
    booking = relationship("Booking", back_populates="complaints")
    assignee = relationship("User", foreign_keys=[assigned_to])

    def __repr__(self) -> str:
        return f"<Complaint {self.id} [{self.priority} - {self.status}]>"


class StaffSupportTicket(db.Model):
    """Internal support request or feedback from Staff Partners."""
    __tablename__ = "staff_support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="NEW")
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    staff_user = relationship("User", foreign_keys=[staff_user_id])

    def __repr__(self) -> str:
        return f"<StaffSupportTicket {self.id} from User {self.staff_user_id}>"
