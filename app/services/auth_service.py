import pyotp
from datetime import datetime
from typing import Optional, Tuple
from flask import current_app
from app.extensions import db
from app.models.user import Customer, User
from app.utils.helpers import normalize_phone


class AuthService:
    """Authentication service for Customers (Phone + OTP) and Staff credentials."""

    # Temporary in-memory OTP secret map: phone -> base32_secret
    _otp_secrets = {}

    @classmethod
    def request_customer_otp(cls, phone: str) -> Tuple[bool, str]:
        """
        Generate OTP for customer mobile number.
        In development / mock mode, logs code to console.
        """
        clean_phone = normalize_phone(phone)
        if len(clean_phone) != 10:
            return False, "Please enter a valid 10-digit mobile number."

        # Create or fetch customer record
        customer = Customer.query.filter_by(phone=clean_phone).first()
        if not customer:
            customer = Customer(phone=clean_phone)
            db.session.add(customer)
            db.session.commit()

        # Generate TOTP secret for this phone
        secret = pyotp.random_base32()
        cls._otp_secrets[clean_phone] = secret
        totp = pyotp.TOTP(secret, interval=300)  # 5-minute validity window
        otp_code = totp.now()

        is_mock = current_app.config.get("OTP_MOCK_MODE", True)
        if is_mock:
            mock_code = current_app.config.get("OTP_MOCK_CODE", "123456")
            current_app.logger.info(
                f"[DEV OTP] Mobile: {clean_phone} | Mock OTP: {mock_code} (Active OTP: {otp_code})"
            )
        else:
            # Here we would dispatch SMS/WhatsApp OTP via external provider
            pass

        return True, "OTP has been sent to your mobile number."

    @classmethod
    def verify_customer_otp(cls, phone: str, otp_token: str) -> Tuple[Optional[Customer], str]:
        """
        Verify the OTP entered by customer.
        Supports mock code in development.
        """
        clean_phone = normalize_phone(phone)
        customer = Customer.query.filter_by(phone=clean_phone).first()
        if not customer:
            return None, "Mobile number not found. Please request a new OTP."

        if not customer.is_active:
            return None, "Your account has been deactivated."

        token = str(otp_token).strip()
        is_mock = current_app.config.get("OTP_MOCK_MODE", False)

        # Allow mock bypass in dev/test mode
        if is_mock and token == current_app.config.get("OTP_MOCK_CODE", "123456"):
            return customer, "Verification successful."

        # Verify against TOTP secret
        secret = cls._otp_secrets.get(clean_phone)
        if not secret:
            return None, "OTP has expired. Please request a new code."

        totp = pyotp.TOTP(secret, interval=300)
        if totp.verify(token, valid_window=1):
            cls._otp_secrets.pop(clean_phone, None)
            return customer, "Verification successful."

        return None, "Invalid OTP code. Please try again."

    @staticmethod
    def authenticate_staff(username: str, password: str) -> Tuple[Optional[User], str]:
        """Authenticate staff user with username and password."""
        user = User.query.filter_by(username=username.strip()).first()
        if not user or not user.check_password(password):
            return None, "Invalid username or password."

        if not user.is_active:
            return None, "This staff account has been deactivated."

        return user, "Authentication successful."
