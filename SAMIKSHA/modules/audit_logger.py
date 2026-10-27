"""
Centralized Audit Logging Service for Samiksha
Maintains an immutable audit trail of all security, application, document,
regulatory rule, and compliance evaluation events.
"""

from typing import Optional, Dict, Any
import json
from datetime import datetime, timezone

from modules.database import get_db_session, AuditEvent


def log_audit_event(
    actor_id: Optional[int],
    actor_username: str,
    actor_role: str,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: str = "127.0.0.1",
    db_session=None,
):
    """Write an audit entry to the immutable audit log."""
    db = db_session if db_session else get_db_session()
    try:
        details_str = json.dumps(details, default=str) if details else None
        event = AuditEvent(
            actor_id=actor_id,
            actor_username=actor_username,
            actor_role=actor_role,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            ip_address=ip_address,
            details_json=details_str,
            created_at=datetime.now(timezone.utc),
        )
        db.add(event)
        db.commit()
    except Exception as e:
        print(f"Warning: Failed to log audit event: {e}")
        db.rollback()
    finally:
        if not db_session:
            db.close()


def get_recent_audit_events(limit: int = 100, action_filter: Optional[str] = None) -> list:
    """Retrieve recent audit events for the audit log viewer page."""
    db = get_db_session()
    try:
        query = db.query(AuditEvent).order_by(AuditEvent.created_at.desc())
        if action_filter:
            query = query.filter(AuditEvent.action == action_filter)
        return query.limit(limit).all()
    finally:
        db.close()
