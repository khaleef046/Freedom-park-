from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.extensions import db


class NotificationPriority:
    NORMAL = "NORMAL"
    IMPORTANT = "IMPORTANT"
    URGENT = "URGENT"


class NotificationType:
    BOOKING = "BOOKING"
    CANCELLATION = "CANCELLATION"
    COMPLAINT = "COMPLAINT"
    FEEDBACK = "FEEDBACK"
    EQUIPMENT = "EQUIPMENT"
    SUPPORT = "SUPPORT"
    SYSTEM = "SYSTEM"


class Notification(db.Model):
    """Internal notifications for Admin and Staff with read/unread tracking."""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default=NotificationPriority.NORMAL)
    type: Mapped[str] = mapped_column(String(30), default=NotificationType.SYSTEM)
    
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="notifications")

    def __repr__(self) -> str:
        return f"<Notification {self.id}: {self.title[:30]} [{self.priority}]>"
