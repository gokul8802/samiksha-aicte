"""
Unit Tests for Database Models and Seeding Integrity
"""

import pytest
from modules.database import get_db_session, User, Institution, Application, RegulatoryRule, MockIssuerRecord, AuditEvent
from config.settings import Roles, APH_DEFAULT_EDITION


def test_seeded_users_exist():
    """Verify standard demo accounts are seeded with proper roles."""
    db = get_db_session()
    try:
        users = db.query(User).all()
        assert len(users) >= 8

        roles_present = {u.role for u in users}
        assert Roles.APPLICANT in roles_present
        assert Roles.SCRUTINY_OFFICER in roles_present
        assert Roles.RULES_ADMIN in roles_present
        assert Roles.DECISION_AUTHORITY in roles_present

        # Verify applicant is linked to an institution
        applicant = db.query(User).filter_by(role=Roles.APPLICANT).first()
        assert applicant.institution_id is not None
        assert applicant.institution is not None
    finally:
        db.close()


def test_verified_regulatory_rules_exist():
    """Verify that all 12 verified APH 2024-27 rules exist in the published registry."""
    db = get_db_session()
    try:
        rules = db.query(RegulatoryRule).filter_by(status="PUBLISHED").all()
        assert len(rules) >= 12

        rule_ids = {r.rule_id for r in rules}
        assert "RULE-APH24-LAND-01" in rule_ids
        assert "RULE-APH24-LAND-02" in rule_ids
        assert "RULE-APH24-BLD-01" in rule_ids
        assert "RULE-APH24-SAFE-01" in rule_ids
        assert "RULE-APH24-FSR-UG-01" in rule_ids
        assert "RULE-APH24-CADRE-01" in rule_ids
        assert "RULE-APH24-COMP-01" in rule_ids
        assert "RULE-APH24-LIB-01" in rule_ids
        assert "RULE-APH24-COMM-01" in rule_ids

        # Ensure all seeded rules are explicitly marked as verified
        for r in rules:
            assert r.is_verified is True
            assert r.aph_edition == APH_DEFAULT_EDITION
            assert len(r.clause_reference) > 0
            assert len(r.page_reference) > 0
    finally:
        db.close()


def test_mock_issuer_registry_seeded():
    """Verify mock issuer registry contains controlled testing cases."""
    db = get_db_session()
    try:
        records = db.query(MockIssuerRecord).all()
        assert len(records) >= 5

        statuses = {rec.status for rec in records}
        assert "ACTIVE" in statuses
        assert "EXPIRED" in statuses
        assert "REVOKED" in statuses

        revoked = db.query(MockIssuerRecord).filter_by(status="REVOKED").first()
        assert revoked.revocation_reason is not None
    finally:
        db.close()


def test_audit_event_logged():
    """Verify that audit events are persisted."""
    db = get_db_session()
    try:
        events = db.query(AuditEvent).all()
        assert len(events) >= 1
    finally:
        db.close()
