from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.extensions import db


class AuditAction:
    BOOKING_CREATED = "BOOKING_CREATED"
    BOOKING_UPDATED = "BOOKING_UPDATED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    BOOKING_RESTORED = "BOOKING_RESTORED"
    DATE_BLOCKED = "DATE_BLOCKED"
    DATE_UNBLOCKED = "DATE_UNBLOCKED"
    PRICE_CHANGED = "PRICE_CHANGED"
    POLICY_CHANGED = "POLICY_CHANGED"
    COMMISSION_CHANGED = "COMMISSION_CHANGED"
    STAFF_CREATED = "STAFF_CREATED"
    STAFF_UPDATED = "STAFF_UPDATED"
    STAFF_DEACTIVATED = "STAFF_DEACTIVATED"
    EQUIPMENT_REPORT = "EQUIPMENT_REPORT"
    CHECKLIST_SUBMITTED = "CHECKLIST_SUBMITTED"
    COMPLAINT_UPDATED = "COMPLAINT_UPDATED"
    REFUND_PROCESSED = "REFUND_PROCESSED"
    SETTINGS_UPDATED = "SETTINGS_UPDATED"
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
    PAYMENT_FAILED = "PAYMENT_FAILED"


class AuditLog(db.Model):
    """
    Immutable audit trail for all business-critical actions.
    Never stores passwords or secret keys.
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    user_role: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    target_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON-formatted string
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by User {self.user_id} at {self.created_at}>"
