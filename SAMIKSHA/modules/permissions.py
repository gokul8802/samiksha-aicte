"""
Role-Based Access Control (RBAC) & Server-Side Authorization Engine for Samiksha
Enforces role permissions, application isolation, separation of duties,
and logs unauthorized access attempts.
"""

from typing import Optional, Dict, Any
import json
from config.settings import Roles, Permissions, ROLE_PERMISSIONS


class PermissionDeniedError(Exception):
    """Raised when an operation violates server-side authorization policies."""
    def __init__(self, message: str, action: str = "", user_id: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.action = action
        self.user_id = user_id


def check_role_permission(role: str, permission: str) -> bool:
    """Check if a role possesses the specified permission."""
    allowed = ROLE_PERMISSIONS.get(role, set())
    return permission in allowed


def can_user(user: Any, permission: str) -> bool:
    """Verify if the authenticated user has the given permission."""
    if not user or not getattr(user, "is_active", False):
        return False
    return check_role_permission(user.role, permission)


def enforce_permission(user: Any, permission: str, action_desc: str = "", db_session: Any = None):
    """
    Enforce permission strictly. If violated, raises PermissionDeniedError
    and logs the security incident to AuditEvent.
    """
    if not can_user(user, permission):
        actor_id = getattr(user, "id", None)
        actor_name = getattr(user, "username", "ANONYMOUS")
        actor_role = getattr(user, "role", "NONE")
        msg = f"Access Denied: User '{actor_name}' ({actor_role}) lacks permission '{permission}' for action: {action_desc or permission}"

        # Record audit log for security breach attempt if db_session is provided
        if db_session:
            try:
                from modules.database import AuditEvent
                audit = AuditEvent(
                    actor_id=actor_id,
                    actor_username=actor_name,
                    actor_role=actor_role,
                    action="UNAUTHORIZED_ACCESS_ATTEMPT",
                    target_type="PERMISSION",
                    target_id=permission,
                    details_json=json.dumps({"attempted_action": action_desc or permission, "error": msg}),
                )
                db_session.add(audit)
                db_session.commit()
            except Exception:
                pass

        raise PermissionDeniedError(msg, action=permission, user_id=actor_id)


def can_access_application(user: Any, application: Any) -> bool:
    """
    Strict Tenant / Institutional Isolation:
    - APPLICANT can ONLY access applications belonging to their own institution.
    - Officers and Admins can access all institutional applications within their review scope.
    """
    if not user or not getattr(user, "is_active", False):
        return False

    if user.role == Roles.APPLICANT:
        # User must belong to the institution owning the application
        if not user.institution_id:
            return False
        return user.institution_id == application.institution_id

    # Internal officers and administrators have platform-wide access
    return True


def enforce_application_access(user: Any, application: Any, db_session: Any = None):
    """Enforce institutional isolation on an application."""
    if not can_access_application(user, application):
        actor_name = getattr(user, "username", "ANONYMOUS")
        actor_role = getattr(user, "role", "NONE")
        app_no = getattr(application, "application_no", str(application.id))
        msg = f"Security Violation: Applicant '{actor_name}' is not authorized to access application '{app_no}'."

        if db_session:
            try:
                from modules.database import AuditEvent
                audit = AuditEvent(
                    actor_id=getattr(user, "id", None),
                    actor_username=actor_name,
                    actor_role=actor_role,
                    action="TENANT_ISOLATION_BREACH_ATTEMPT",
                    target_type="APPLICATION",
                    target_id=app_no,
                    details_json=json.dumps({"app_owner_inst_id": application.institution_id, "user_inst_id": getattr(user, "institution_id", None)}),
                )
                db_session.add(audit)
                db_session.commit()
            except Exception:
                pass

        raise PermissionDeniedError(msg, action="ACCESS_APPLICATION", user_id=getattr(user, "id", None))


def can_approve_rule(user: Any, rule: Any) -> bool:
    """
    Separation of Duties for Regulatory Rules:
    - User must have APPROVE_RULE or PUBLISH_RULE permission.
    - Author cannot approve their own rule proposal (separation of duties).
    """
    if not can_user(user, Permissions.APPROVE_RULE) and not can_user(user, Permissions.PUBLISH_RULE):
        return False
    
    # Self-approval prohibited if user created the draft
    if rule.created_by == user.id:
        return False

    return True


def enforce_rule_approval(user: Any, rule: Any, db_session: Any = None):
    """Enforce separation of duties on rule approvals."""
    if not can_approve_rule(user, rule):
        actor_name = getattr(user, "username", "ANONYMOUS")
        msg = f"Separation of Duties Violation: Rule author '{actor_name}' cannot approve/publish their own proposed rule '{rule.rule_id}'."
        
        if db_session:
            try:
                from modules.database import AuditEvent
                audit = AuditEvent(
                    actor_id=getattr(user, "id", None),
                    actor_username=actor_name,
                    actor_role=getattr(user, "role", "NONE"),
                    action="SEPARATION_OF_DUTIES_VIOLATION",
                    target_type="REGULATORY_RULE",
                    target_id=rule.rule_id,
                    details_json=json.dumps({"rule_creator_id": rule.created_by, "approver_id": getattr(user, "id", None)}),
                )
                db_session.add(audit)
                db_session.commit()
            except Exception:
                pass

        raise PermissionDeniedError(msg, action="APPROVE_RULE", user_id=getattr(user, "id", None))
