from typing import Optional, List
from flask import current_app
from app.extensions import db
from app.models.notification import Notification, NotificationPriority, NotificationType
from app.models.user import User, Role


class NotificationService:
    """Service abstraction for In-App Notifications and future WhatsApp delivery."""

    @staticmethod
    def notify_user(
        user_id: int,
        title: str,
        message: str,
        priority: str = NotificationPriority.NORMAL,
        notification_type: str = NotificationType.SYSTEM,
        reference_type: Optional[str] = None,
        reference_id: Optional[int] = None,
    ) -> Notification:
        """Create an in-app notification for a staff/admin user."""
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            priority=priority,
            type=notification_type,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        db.session.add(notif)
        db.session.commit()
        return notif

    @staticmethod
    def notify_admins(
        title: str,
        message: str,
        priority: str = NotificationPriority.NORMAL,
        notification_type: str = NotificationType.SYSTEM,
        reference_type: Optional[str] = None,
        reference_id: Optional[int] = None,
    ) -> List[Notification]:
        """Broadcast in-app notification to all active Super Admins and Owner/Admins."""
        admins = User.query.filter(
            User.role.in_([Role.SUPER_ADMIN, Role.ADMIN]),
            User.is_active.is_(True),
        ).all()
        created = []
        for admin in admins:
            n = Notification(
                user_id=admin.id,
                title=title,
                message=message,
                priority=priority,
                type=notification_type,
                reference_type=reference_type,
                reference_id=reference_id,
            )
            db.session.add(n)
            created.append(n)
        if created:
            db.session.commit()
        return created

    @staticmethod
    def send_whatsapp_booking_confirmation(
        recipient_phone: str,
        booking_uid: str,
        booking_date: str,
        num_people: int,
        amount: str,
        customer_name: str,
    ) -> bool:
        """
        WhatsApp message delivery abstraction.
        Logs to application logger in development mode; ready for production WhatsApp Cloud API.
        """
        message_body = (
            f"🌿 FREEDOM PARK BOOKING CONFIRMED 🌿\n\n"
            f"Dear {customer_name},\n"
            f"Your private booking at Freedom Park is confirmed!\n\n"
            f"📋 Booking ID: {booking_uid}\n"
            f"📅 Date: {booking_date}\n"
            f"⏰ Hours: 8:00 AM – 8:00 PM\n"
            f"👥 Guests: Up to {num_people}\n"
            f"💰 Amount Paid: ₹{amount}\n\n"
            f"Show your digital QR pass upon entry at Pernambut.\n"
            f"Thank you for choosing Freedom Park!"
        )
        
        # In development / mock mode, log output clearly
        if current_app:
            current_app.logger.info(
                f"[WHATSAPP DISPATCH] To: {recipient_phone}\n{message_body}"
            )
        return True
