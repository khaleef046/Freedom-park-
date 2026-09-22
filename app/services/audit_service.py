import json
from typing import Optional, Any
from flask import has_request_context, request
from flask_login import current_user
from app.extensions import db
from app.models.audit_log import AuditLog


class AuditService:
    """Service to record immutable audit entries for all business operations."""

    @staticmethod
    def log(
        action: str,
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
        details: Optional[Any] = None,
        user_id: Optional[int] = None,
        user_role: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Create and commit an audit log entry."""
        if has_request_context():
            if ip_address is None:
                ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            if user_id is None and current_user and current_user.is_authenticated:
                user_id = getattr(current_user, "id", None)
                user_role = getattr(current_user, "role", None)

        details_str = None
        if details is not None:
            if isinstance(details, (dict, list)):
                details_str = json.dumps(details, default=str)
            else:
                details_str = str(details)

        entry = AuditLog(
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details_str,
            user_id=user_id,
            user_role=user_role,
            ip_address=ip_address,
        )
        try:
            db.session.add(entry)
            db.session.commit()
        except Exception:
            db.session.rollback()
            # In case audit log table isn't created yet during migrations
            pass
        return entry
