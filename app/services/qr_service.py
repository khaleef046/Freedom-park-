import segno
from flask import current_app, url_for


class QRService:
    """Generates clean SVG QR codes for booking passes using segno."""

    @staticmethod
    def generate_booking_qr_svg_uri(booking_uid: str) -> str:
        """
        Generate an inline SVG data URI representing the booking pass verification URL.
        Does not embed sensitive customer PII directly in the QR code.
        """
        try:
            # Generate verification URL or token payload
            # If request context is available, use external URL; otherwise fallback to string
            try:
                verify_payload = url_for("public.verify_ticket", booking_uid=booking_uid, _external=True)
            except Exception:
                verify_payload = f"FP-VERIFY:{booking_uid}"

            qr = segno.make_qr(verify_payload, error="M")
            # Returns 'data:image/svg+xml;utf8,<svg ...'
            return qr.svg_data_uri(scale=5, border=2, dark="#1B4332", light="#FFFFFF")
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error generating QR for {booking_uid}: {e}")
            return ""

    @staticmethod
    def generate_booking_qr_svg_string(booking_uid: str) -> str:
        """Returns raw SVG markup string for direct HTML injection."""
        try:
            verify_payload = f"FP-VERIFY:{booking_uid}"
            qr = segno.make_qr(verify_payload, error="M")
            return qr.svg_inline(scale=4, border=1, dark="#1B4332")
        except Exception:
            return ""
