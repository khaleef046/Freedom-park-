import re
from datetime import datetime, time, timedelta

from app.models.booking import Booking, BookingStatus
from app.models.feedback import Feedback
from app.services.settings_service import SettingsService


class FeedbackService:
    """Post-visit feedback eligibility and ownership rules."""

    @staticmethod
    def now() -> datetime:
        return datetime.now()

    @classmethod
    def closing_time(cls) -> time:
        hours = str(SettingsService.get("operating_hours", "8:00 AM – 8:00 PM"))
        matches = re.findall(r"(\d{1,2}:\d{2}\s*[AP]M)", hours, flags=re.IGNORECASE)
        if matches:
            return datetime.strptime(matches[-1].upper().replace("  ", " "), "%I:%M %p").time()
        return time(20, 0)

    @classmethod
    def visit_end(cls, booking: Booking) -> datetime:
        return datetime.combine(booking.booking_date, cls.closing_time())

    @classmethod
    def is_eligible(cls, booking: Booking, now: datetime | None = None) -> bool:
        if booking.status not in (BookingStatus.CONFIRMED, BookingStatus.COMPLETED):
            return False
        current_time = now or cls.now()
        ended_at = cls.visit_end(booking)
        return ended_at <= current_time <= ended_at + timedelta(hours=24)

    @staticmethod
    def has_feedback(booking: Booking) -> bool:
        return Feedback.query.filter_by(booking_id=booking.id).first() is not None
