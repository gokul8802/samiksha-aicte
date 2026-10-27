"""
Authentication, Session Management & Demo Credential Gateway for Samiksha
Uses bcrypt password hashing and manages Streamlit user session states.
"""

from typing import Optional, Dict, Any
import bcrypt
import streamlit as st

from modules.database import get_db_session, User, AuditEvent
from config.settings import Roles
from sqlalchemy.orm import joinedload
import json


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def hash_password(plain_password: str) -> str:
    """Hash a password securely using bcrypt with salt."""
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate credentials against the database."""
    db = get_db_session()
    try:
        user = db.query(User).filter_by(username=username).first()
        if not user or not user.is_active:
            return None
        if verify_password(password, user.password_hash):
            return user
        return None
    finally:
        db.close()


def set_user_session(user: User):
    """Store authenticated user in Streamlit session state."""
    st.session_state["user_id"] = user.id
    st.session_state["username"] = user.username
    st.session_state["role"] = user.role
    st.session_state["full_name"] = user.full_name
    st.session_state["institution_id"] = user.institution_id
    st.session_state["is_authenticated"] = True

    # Record login audit
    db = get_db_session()
    try:
        audit = AuditEvent(
            actor_id=user.id,
            actor_username=user.username,
            actor_role=user.role,
            action="LOGIN_SUCCESS",
            target_type="SESSION",
            target_id=str(user.id),
            details_json=json.dumps({"ip": "127.0.0.1", "role": user.role}),
        )
        db.add(audit)
        db.commit()
    except Exception:
        pass
    finally:
        db.close()


def clear_user_session():
    """Clear active user session and record logout."""
    user_id = st.session_state.get("user_id")
    username = st.session_state.get("username", "ANONYMOUS")
    role = st.session_state.get("role", "NONE")

    if user_id:
        db = get_db_session()
        try:
            audit = AuditEvent(
                actor_id=user_id,
                actor_username=username,
                actor_role=role,
                action="LOGOUT",
                target_type="SESSION",
                target_id=str(user_id),
            )
            db.add(audit)
            db.commit()
        except Exception:
            pass
        finally:
            db.close()

    for key in ["user_id", "username", "role", "full_name", "institution_id", "is_authenticated"]:
        if key in st.session_state:
            del st.session_state[key]


def get_current_user(db_session=None) -> Optional[User]:
    """Retrieve the active User database object from session state with eager relationships."""
    if not st.session_state.get("is_authenticated"):
        return None
    user_id = st.session_state.get("user_id")
    if not user_id:
        return None

    db = db_session if db_session else get_db_session()
    try:
        user = db.query(User).options(joinedload(User.institution)).filter_by(id=user_id, is_active=True).first()
        if user:
            # Force load institution attribute while session is open
            if user.institution:
                _ = user.institution.name
                _ = user.institution.aicte_id
            db.expunge_all()
        return user
    finally:
        if not db_session:
            db.close()


def is_authenticated() -> bool:
    """Return whether current session is logged in."""
    return bool(st.session_state.get("is_authenticated", False))


def switch_demo_user(username: str) -> bool:
    """Convenience helper to switch to a seeded demo user during hackathon demonstration."""
    db = get_db_session()
    try:
        user = db.query(User).filter_by(username=username, is_active=True).first()
        if user:
            set_user_session(user)
            return True
        return False
    finally:
        db.close()


def get_demo_accounts() -> list:
    """Return list of seeded demo accounts for the quick-switcher."""
    return [
        {"username": "applicant_apex", "label": "Applicant: Apex Tech Principal", "role": Roles.APPLICANT},
        {"username": "applicant_bharat", "label": "Applicant: Bharat Tech Dean", "role": Roles.APPLICANT},
        {"username": "scrutiny_sharma", "label": "Scrutiny Officer: Er. Suresh Sharma", "role": Roles.SCRUTINY_OFFICER},
        {"username": "inspection_verma", "label": "Inspection Officer: Prof. Anita Verma", "role": Roles.INSPECTION_OFFICER},
        {"username": "coord_aicte", "label": "Regulation Bureau: Dr. Manoj Deshmukh", "role": Roles.CASE_COORDINATOR},
        {"username": "reviewer_comm", "label": "Approval Committee: Prof. A. Swaminathan", "role": Roles.COMMITTEE_REVIEWER},
        {"username": "director_reg", "label": "Decision Authority: Advisor (Regulation)", "role": Roles.DECISION_AUTHORITY},
        {"username": "rules_officer", "label": "Rules Administrator: Shri K. Ramanathan", "role": Roles.RULES_ADMIN},
        {"username": "admin_tech", "label": "Technical Administrator: Systems Lead", "role": Roles.TECH_ADMIN},
    ]
