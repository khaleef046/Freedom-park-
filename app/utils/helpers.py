import re
from datetime import datetime, date
from decimal import Decimal
from urllib.parse import urlparse, urljoin
from flask import request


def format_currency(amount) -> str:
    """Format decimal/float amount into Indian Rupee format, e.g. ₹2,000."""
    try:
        val = float(amount)
        if val.is_integer():
            return f"₹{int(val):,}"
        return f"₹{val:,.2f}"
    except (ValueError, TypeError):
        return f"₹{amount}"


def format_date_long(d) -> str:
    """Format a date or datetime object into '15 October 2026'."""
    if isinstance(d, datetime):
        d = d.date()
    if isinstance(d, date):
        return d.strftime("%d %B %Y")
    return str(d)


def format_time_12hr(dt) -> str:
    """Format datetime into 12-hour AM/PM format."""
    if isinstance(dt, datetime):
        return dt.strftime("%I:%M %p")
    return str(dt)


def generate_booking_uid(year: int, sequence_num: int) -> str:
    """Format sequential booking UID, e.g. FP-2026-0001."""
    return f"FP-{year}-{sequence_num:04d}"


def normalize_phone(phone: str) -> str:
    """Strip spaces, dashes, and country prefixes for clean 10-digit format."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[2:]
    return digits


def is_safe_redirect_url(target: str) -> bool:
    """Verify redirection target points to same host to prevent open redirect vulnerabilities."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc
