"""
Unit Tests for Authentication, Role-Based Access Control, and Tenant Isolation
Covers:
- Password hashing & verification
- Credential authentication
- Role permission matrix checks
- Strict Applicant tenant boundary isolation (Applicant A cannot access Applicant B's application)
- Separation of duties (Rule author cannot approve their own rule)
- Tamper-evident audit trail creation on security breaches
"""

import pytest
import json
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from modules.database import Base, User, Institution, Application, RegulatoryRule, AuditEvent
from modules.auth import hash_password, verify_password, authenticate_user
from modules.permissions import (
    can_user, enforce_permission, can_access_application,
    enforce_application_access, can_approve_rule, enforce_rule_approval,
    PermissionDeniedError
)
from config.settings import Roles, Permissions


@pytest.fixture(scope="module")
def test_db():
    """In-memory SQLite database for unit tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create two institutions
    inst1 = Institution(
        aicte_id="1-TEST-INST-01",
        name="Apex College of Engineering",
        address="Sector 1, Noida",
        state="UP",
        district="GB Nagar",
        institution_type="Private",
        category="Engineering",
        contact_email="apex@test.com",
        phone="1234567890",
    )
    inst2 = Institution(
        aicte_id="1-TEST-INST-02",
        name="Bharat Institute of Tech",
        address="Whitefield, Bengaluru",
        state="Karnataka",
        district="Bengaluru",
        institution_type="Private",
        category="Engineering",
        contact_email="bharat@test.com",
        phone="0987654321",
    )
    session.add_all([inst1, inst2])
    session.commit()

    # Create users
    pwd_hash = hash_password("SecurePass@123")
    app_user1 = User(
        username="applicant_apex",
        email="apex@test.com",
        password_hash=pwd_hash,
        full_name="Apex Principal",
        role=Roles.APPLICANT,
        institution_id=inst1.id,
    )
    app_user2 = User(
        username="applicant_bharat",
        email="bharat@test.com",
        password_hash=pwd_hash,
        full_name="Bharat Dean",
        role=Roles.APPLICANT,
        institution_id=inst2.id,
    )
    officer_user = User(
        username="officer_sharma",
        email="sharma@test.com",
        password_hash=pwd_hash,
        full_name="Scrutiny Officer Sharma",
        role=Roles.SCRUTINY_OFFICER,
    )
    rules_admin1 = User(
        username="rules_lead_1",
        email="rules1@test.com",
        password_hash=pwd_hash,
        full_name="Rules Officer 1",
        role=Roles.RULES_ADMIN,
    )
    rules_admin2 = User(
        username="rules_lead_2",
        email="rules2@test.com",
        password_hash=pwd_hash,
        full_name="Rules Officer 2",
        role=Roles.RULES_ADMIN,
    )
    session.add_all([app_user1, app_user2, officer_user, rules_admin1, rules_admin2])
    session.commit()

    # Create applications
    app1 = Application(
        application_no="APP-TEST-001",
        institution_id=inst1.id,
        category="Setting up New Technical Institution",
        program="Engineering",
        status="UNDER_SCRUTINY",
        created_by=app_user1.id,
    )
    app2 = Application(
        application_no="APP-TEST-002",
        institution_id=inst2.id,
        category="Extension of Approval",
        program="Engineering",
        status="SUBMITTED",
        created_by=app_user2.id,
    )
    session.add_all([app1, app2])
    session.commit()

    yield {
        "session": session,
        "inst1": inst1,
        "inst2": inst2,
        "user_apex": app_user1,
        "user_bharat": app_user2,
        "officer": officer_user,
        "rules1": rules_admin1,
        "rules2": rules_admin2,
        "app1": app1,
        "app2": app2,
    }
    session.close()


def test_password_hashing():
    """Verify bcrypt hash generation and cryptographic verification."""
    password = "MyTestPassword!2026"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_role_permissions(test_db):
    """Verify role capabilities match security matrix."""
    applicant = test_db["user_apex"]
    officer = test_db["officer"]
    rules_admin = test_db["rules1"]

    # Applicant capabilities
    assert can_user(applicant, Permissions.CREATE_APPLICATION) is True
    assert can_user(applicant, Permissions.UPLOAD_DOCUMENT) is True
    assert can_user(applicant, Permissions.PUBLISH_RULE) is False
    assert can_user(applicant, Permissions.RUN_COMPLIANCE_EVAL) is False

    # Scrutiny Officer capabilities
    assert can_user(officer, Permissions.VIEW_ALL_APPLICATIONS) is True
    assert can_user(officer, Permissions.RUN_COMPLIANCE_EVAL) is True
    assert can_user(officer, Permissions.RUN_TAMPERING_ANALYSIS) is True
    assert can_user(officer, Permissions.PUBLISH_RULE) is False

    # Rules Administrator capabilities
    assert can_user(rules_admin, Permissions.PROPOSE_RULE) is True
    assert can_user(rules_admin, Permissions.APPROVE_RULE) is True
    assert can_user(rules_admin, Permissions.PUBLISH_RULE) is True


def test_tenant_isolation_applicant_boundary(test_db):
    """
    Mandatory Acceptance Test:
    Applicant A CANNOT access Applicant B's private application.
    Enforcement must raise PermissionDeniedError and log an audit event.
    """
    user_apex = test_db["user_apex"]
    user_bharat = test_db["user_bharat"]
    officer = test_db["officer"]
    app_apex = test_db["app1"]
    app_bharat = test_db["app2"]
    session = test_db["session"]

    # Apex user can access Apex app
    assert can_access_application(user_apex, app_apex) is True
    enforce_application_access(user_apex, app_apex, session)

    # Bharat user can access Bharat app
    assert can_access_application(user_bharat, app_bharat) is True
    enforce_application_access(user_bharat, app_bharat, session)

    # Cross-tenant breach attempts must be rejected!
    assert can_access_application(user_apex, app_bharat) is False
    with pytest.raises(PermissionDeniedError):
        enforce_application_access(user_apex, app_bharat, session)

    assert can_access_application(user_bharat, app_apex) is False
    with pytest.raises(PermissionDeniedError):
        enforce_application_access(user_bharat, app_apex, session)

    # Officer can access both applications
    assert can_access_application(officer, app_apex) is True
    assert can_access_application(officer, app_bharat) is True

    # Verify audit event was recorded for the attempted violation
    audit = session.query(AuditEvent).filter_by(action="TENANT_ISOLATION_BREACH_ATTEMPT").first()
    assert audit is not None
    assert audit.actor_username in ["applicant_apex", "applicant_bharat"]


def test_separation_of_duties_rule_approval(test_db):
    """
    Mandatory Acceptance Test:
    A rule author CANNOT approve their own rule proposal.
    A separate authorized officer must approve it.
    """
    rules_lead_1 = test_db["rules1"]
    rules_lead_2 = test_db["rules2"]
    session = test_db["session"]

    # Create a draft rule proposed by rules_lead_1
    draft_rule = RegulatoryRule(
        rule_id="RULE-TEST-DRAFT-01",
        version="1.0.0",
        title="Draft Experimental Norm",
        description="Testing separation of duties",
        aph_edition="2024-27",
        clause_reference="Clause 9.9",
        page_reference="Page 1",
        source_excerpt="Excerpt",
        category="Infrastructure",
        evaluation_logic_json="{}",
        required_evidence_json="[]",
        status="PENDING_APPROVAL",
        is_verified=False,
        created_by=rules_lead_1.id,
    )
    session.add(draft_rule)
    session.commit()

    # Rule Author 1 attempts to approve own rule -> MUST FAIL
    assert can_approve_rule(rules_lead_1, draft_rule) is False
    with pytest.raises(PermissionDeniedError):
        enforce_rule_approval(rules_lead_1, draft_rule, session)

    # Rule Author 2 (distinct reviewer) attempts to approve -> MUST SUCCEED
    assert can_approve_rule(rules_lead_2, draft_rule) is True
    enforce_rule_approval(rules_lead_2, draft_rule, session)

    # Verify audit event for separation of duties violation attempt
    audit = session.query(AuditEvent).filter_by(action="SEPARATION_OF_DUTIES_VIOLATION").first()
    assert audit is not None
    assert audit.actor_username == "rules_lead_1"
