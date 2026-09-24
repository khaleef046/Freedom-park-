from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class ExpenditureCategory:
    ELECTRICITY = "Electricity"
    WATER = "Water"
    MAINTENANCE = "Maintenance"
    CLEANING = "Cleaning"
    STAFF_PAYMENTS = "Staff payments"
    EQUIPMENT = "Equipment"
    SUPPLIES = "Supplies"
    OTHER = "Other"

    ALL = [
        ELECTRICITY,
        WATER,
        MAINTENANCE,
        CLEANING,
        STAFF_PAYMENTS,
        EQUIPMENT,
        SUPPLIES,
        OTHER,
    ]


class Expenditure(db.Model):
    """Owner-entered business expenditure record."""
    __tablename__ = "expenditures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow, nullable=True)

    creator = relationship("User", foreign_keys=[created_by])
