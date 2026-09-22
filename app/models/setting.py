import json
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.extensions import db


class SettingCategory:
    GENERAL = "general"
    PRICING = "pricing"
    BOOKING = "booking"
    CANCELLATION = "cancellation"
    COMMISSION = "commission"
    CONTACT = "contact"
    RULES = "rules"
    SYSTEM = "system"


class Setting(db.Model):
    """
    Centralized key-value system and business settings store.
    Enables owner/admin to change business rules without code changes.
    """
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), default="string")  # string, int, decimal, bool, json, text
    category: Mapped[str] = mapped_column(String(50), default=SettingCategory.GENERAL, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)  # Super-admin only if True
    
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    updater = relationship("User", foreign_keys=[updated_by])

    def get_typed_value(self) -> Any:
        """Parse string value into its native Python type."""
        v = self.value
        t = self.value_type.lower()
        if t == "int":
            try:
                return int(v)
            except (ValueError, TypeError):
                return 0
        elif t == "decimal":
            try:
                return Decimal(str(v))
            except Exception:
                return Decimal("0.00")
        elif t == "bool":
            return str(v).strip().lower() in ("true", "1", "yes", "on")
        elif t == "json":
            try:
                return json.loads(v)
            except Exception:
                return {}
        return str(v)

    def set_typed_value(self, val: Any) -> None:
        """Serialize native value to string according to value_type."""
        t = self.value_type.lower()
        if t == "json":
            self.value = json.dumps(val)
        elif t == "bool":
            self.value = "true" if val else "false"
        else:
            self.value = str(val)

    def __repr__(self) -> str:
        return f"<Setting {self.key}={self.value[:30]}>"
