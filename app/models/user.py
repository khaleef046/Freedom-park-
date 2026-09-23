from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db


class Role:
    """System role constants."""
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"  # Owner / Admin (Mama)
    STAFF_PARTNER = "STAFF_PARTNER"
    SECURITY = "SECURITY"
    
    ALL = [SUPER_ADMIN, ADMIN, STAFF_PARTNER, SECURITY]
    STAFF_ROLES = [SUPER_ADMIN, ADMIN, STAFF_PARTNER, SECURITY]


class User(UserMixin, db.Model):
    """Staff & Administrator user accounts."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default=Role.STAFF_PARTNER)
    staff_id: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # JSON array of optional task permissions; kept in a text column for SQLite compatibility.
    permissions: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="[]")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    created_bookings = relationship("Booking", foreign_keys="Booking.created_by", back_populates="creator")
    partner_bookings = relationship("Booking", foreign_keys="Booking.staff_partner_id", back_populates="staff_partner")
    commissions = relationship("CommissionRecord", foreign_keys="CommissionRecord.staff_user_id", back_populates="staff_user")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    @property
    def formatted_staff_id(self) -> str:
        if self.staff_id:
            return self.staff_id
        prefix_map = {
            Role.SUPER_ADMIN: "FP-ADMIN",
            Role.ADMIN: "FP-OWNER",
            Role.STAFF_PARTNER: "FP-PARTNER",
            Role.SECURITY: "FP-SEC",
        }
        prefix = prefix_map.get(self.role, "FP-STAFF")
        return f"{prefix}-{self.id:03d}" if self.id is not None else f"{prefix}-NEW"

    def set_password(self, password: str) -> None:
        """Hash and store password using werkzeug default (scrypt)."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify given password against hash."""
        return check_password_hash(self.password_hash, password)

    def has_permission(self, permission: str) -> bool:
        """Return whether this account has an explicit task permission. System Administrator always has access."""
        if self.role == Role.SUPER_ADMIN:
            return True
        import json
        try:
            values = json.loads(self.permissions or "[]")
            return permission in values
        except Exception:
            return False

    def set_permissions(self, values) -> None:
        import json
        self.permissions = json.dumps(sorted(set(values or [])))

    def has_role(self, *roles: str) -> bool:
        """Check if user possesses any of the specified roles."""
        return self.role in roles

    @property
    def is_super_admin(self) -> bool:
        return self.role == Role.SUPER_ADMIN

    @property
    def is_admin_or_higher(self) -> bool:
        return self.role in (Role.SUPER_ADMIN, Role.ADMIN)

    @property
    def is_staff_partner(self) -> bool:
        return self.role == Role.STAFF_PARTNER

    @property
    def is_security(self) -> bool:
        return self.role == Role.SECURITY

    def get_id(self) -> str:
        """Return prefixed ID for Flask-Login session management."""
        return f"staff_{self.id}"

    @property
    def role_label(self) -> str:
        return {Role.SUPER_ADMIN: "System Administrator", Role.ADMIN: "Owner / Admin", Role.STAFF_PARTNER: "Staff Partner", Role.SECURITY: "Security"}.get(self.role, self.role)

    def __repr__(self) -> str:
        return f"<User {self.username} [{self.role}]>"


class Customer(UserMixin, db.Model):
    """Customer accounts authenticated via Phone + OTP."""
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    whatsapp: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow, nullable=True)

    # Relationships
    bookings = relationship("Booking", back_populates="customer", cascade="all, delete-orphan")
    feedback_list = relationship("Feedback", back_populates="customer", cascade="all, delete-orphan")
    complaints = relationship("Complaint", back_populates="customer", cascade="all, delete-orphan")
    identities = relationship("CustomerIdentity", back_populates="customer", cascade="all, delete-orphan")

    def get_id(self) -> str:
        """Return prefixed ID for Flask-Login session management."""
        return f"cust_{self.id}"

    @property
    def role(self) -> str:
        return "CUSTOMER"

    def has_role(self, *roles: str) -> bool:
        return "CUSTOMER" in roles

    def __repr__(self) -> str:
        return f"<Customer {self.phone} ({self.name})>"


class CustomerIdentity(db.Model):
    """External identity linked to a customer account."""
    __tablename__ = "customer_identities"
    __table_args__ = (
        db.UniqueConstraint("provider", "provider_subject", name="uq_customer_identity_provider_subject"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow, nullable=True)

    customer = relationship("Customer", back_populates="identities")

    def __repr__(self) -> str:
        return f"<CustomerIdentity {self.provider}:{self.provider_subject}>"
