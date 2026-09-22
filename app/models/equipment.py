from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.extensions import db


class ChecklistType:
    CHECK_IN = "CHECK_IN"
    CHECK_OUT = "CHECK_OUT"


class EquipmentItemStatus:
    PRESENT = "PRESENT"
    RETURNED = "RETURNED"
    MISSING = "MISSING"
    DAMAGED = "DAMAGED"


class Equipment(db.Model):
    """Configurable equipment items provided to guests (Cricket bats, Carrom, etc.)."""
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    checklist_items = relationship("EquipmentChecklistItem", back_populates="equipment")
    reports = relationship("EquipmentReport", back_populates="equipment")

    def __repr__(self) -> str:
        return f"<Equipment {self.name} (x{self.quantity})>"


class EquipmentChecklist(db.Model):
    """Check-in or Check-out checklist submitted by Security for a booking."""
    __tablename__ = "equipment_checklists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("bookings.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # CHECK_IN or CHECK_OUT
    completed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    booking = relationship("Booking", back_populates="checklists")
    staff = relationship("User", foreign_keys=[completed_by])
    items = relationship("EquipmentChecklistItem", back_populates="checklist", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<EquipmentChecklist {self.type} for Booking {self.booking_id}>"


class EquipmentChecklistItem(db.Model):
    """Specific line item within an equipment checklist."""
    __tablename__ = "equipment_checklist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    checklist_id: Mapped[int] = mapped_column(Integer, ForeignKey("equipment_checklists.id"), nullable=False)
    equipment_id: Mapped[int] = mapped_column(Integer, ForeignKey("equipment.id"), nullable=False)
    expected_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    actual_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), default=EquipmentItemStatus.PRESENT)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    checklist = relationship("EquipmentChecklist", back_populates="items")
    equipment = relationship("Equipment", back_populates="checklist_items")


class EquipmentReport(db.Model):
    """Discrepancy report filed for missing or damaged equipment items."""
    __tablename__ = "equipment_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("bookings.id"), nullable=False)
    equipment_id: Mapped[int] = mapped_column(Integer, ForeignKey("equipment.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # MISSING or DAMAGED
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reported_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    booking = relationship("Booking", back_populates="equipment_reports")
    equipment = relationship("Equipment", back_populates="reports")
    reporter = relationship("User", foreign_keys=[reported_by])

    def __repr__(self) -> str:
        return f"<EquipmentReport {self.status} x{self.quantity} for Booking {self.booking_id}>"
