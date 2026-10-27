"""
Database Layer & Relational Schema for Samiksha
SQLAlchemy ORM with SQLite backend and PostgreSQL migration readiness.
Tracks institutions, applications, versioned documents, extracted fields,
tampering runs, certificate verification, cross-application claims,
verified APH regulatory rules, compliance findings, and audit logs.
"""

from datetime import datetime, timezone
import json
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Float, Boolean,
    DateTime, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
import bcrypt

from config.settings import DATABASE_URL, Roles, EvaluationStatus, APH_DEFAULT_EDITION

Base = declarative_base()

# ---------------------------------------------------------
# Database Models
# ---------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(120), nullable=False)
    role = Column(String(40), nullable=False, default=Roles.APPLICANT, index=True)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    institution = relationship("Institution", back_populates="users", lazy="joined")


class Institution(Base):
    __tablename__ = "institutions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    aicte_id = Column(String(40), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    address = Column(String(300), nullable=False)
    state = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False)
    institution_type = Column(String(80), nullable=False) # Govt, Govt-Aided, Private-Self Financed, University Dept
    category = Column(String(100), nullable=False) # Engineering, Management, MCA, Pharmacy, Architecture
    minority_status = Column(String(50), default="Non-Minority")
    contact_email = Column(String(120), nullable=False)
    phone = Column(String(30), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    users = relationship("User", back_populates="institution")
    applications = relationship("Application", back_populates="institution")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_no = Column(String(50), unique=True, nullable=False, index=True)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False, index=True)
    academic_year = Column(String(20), nullable=False, default="2025-26")
    category = Column(String(100), nullable=False) # Setting up New Technical Institution, EoA, etc.
    program = Column(String(100), nullable=False) # Engineering & Technology, Management, etc.
    status = Column(String(40), nullable=False, default="DRAFT", index=True) 
    # DRAFT, SUBMITTED, UNDER_SCRUTINY, CLARIFICATION_REQUESTED, RESUBMITTED, COMMITTEE_REVIEW, APPROVED, REJECTED
    current_stage = Column(String(60), default="Document Upload")
    approved_intake = Column(Integer, default=300)
    total_land_acres = Column(Float, default=5.0)
    built_up_area_sqm = Column(Float, default=4500.0)
    submission_date = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    institution = relationship("Institution", back_populates="applications")
    documents = relationship("Document", back_populates="application", cascade="all, delete-orphan")
    evaluations = relationship("ComplianceEvaluation", back_populates="application")
    comments = relationship("ReviewComment", back_populates="application")
    versions = relationship("ApplicationVersion", back_populates="application")


class ApplicationVersion(Base):
    __tablename__ = "application_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    version_num = Column(Integer, nullable=False)
    snapshot_json = Column(Text, nullable=False) # Serialized state
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    application = relationship("Application", back_populates="versions")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    document_type = Column(String(80), nullable=False, index=True) # FIRE_SAFETY, LAND_DEED, BUILDING_PLAN, etc.
    filename = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)
    mime_type = Column(String(100), nullable=False)
    status = Column(String(40), default="UPLOADED") # UPLOADED, PROCESSING, EXTRACTED, FAILED
    version = Column(Integer, default=1, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    application = relationship("Application", back_populates="documents")
    extracted_fields = relationship("ExtractedField", back_populates="document", cascade="all, delete-orphan")
    tampering_runs = relationship("TamperingRun", back_populates="document", cascade="all, delete-orphan")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    version_num = Column(Integer, nullable=False)
    filename = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    sha256_hash = Column(String(64), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    document = relationship("Document", back_populates="versions")


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False, index=True)
    field_value = Column(Text, nullable=True)
    normalized_value = Column(String(255), nullable=True)
    confidence = Column(Float, default=1.0)
    page_number = Column(Integer, default=1)
    bounding_box = Column(String(100), nullable=True) # JSON coordinates
    is_verified = Column(Boolean, default=False)
    verification_source = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    document = relationship("Document", back_populates="extracted_fields")


class TamperingRun(Base):
    __tablename__ = "tampering_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    model_version = Column(String(60), nullable=False, default="BASELINE-ELA-V1.0")
    risk_score = Column(Float, nullable=False) # 0.0 to 1.0
    decision_threshold = Column(Float, nullable=False, default=0.65)
    status = Column(String(40), default="COMPLETED")
    indicators_json = Column(Text, nullable=True) # Details of ELA, metadata, noise variance
    is_flagged = Column(Boolean, default=False)
    uncertainty_statement = Column(String(255), default="Visual anomaly score; not definitive proof of fraud.")
    notes = Column(Text, nullable=True)
    run_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    document = relationship("Document", back_populates="tampering_runs")


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    certificate_number = Column(String(100), nullable=False, index=True)
    holder_name = Column(String(200), nullable=False)
    issuing_authority = Column(String(200), nullable=False)
    issue_date = Column(String(30), nullable=True)
    expiry_date = Column(String(30), nullable=True)
    certificate_type = Column(String(80), nullable=False) # FIRE_SAFETY, OCCUPANCY, LAND_TITLE, UNIVERSITY_NOC
    digital_sig_valid = Column(Boolean, default=False)
    verification_status = Column(String(50), nullable=False, default="PENDING")
    # ISSUER_CONFIRMED, DETAILS_MISMATCH, EXPIRED, REVOKED, SOURCE_PENDING, MOCK_SIMULATED, ISSUER_UNAVAILABLE
    verification_source = Column(String(100), default="MOCK_REGISTRY_SIMULATED")
    verification_notes = Column(Text, nullable=True)
    verified_at = Column(DateTime, nullable=True)


class MockIssuerRecord(Base):
    __tablename__ = "mock_issuer_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    certificate_number = Column(String(100), unique=True, nullable=False, index=True)
    holder_name = Column(String(200), nullable=False)
    issuing_authority = Column(String(200), nullable=False)
    issue_date = Column(String(30), nullable=False)
    expiry_date = Column(String(30), nullable=True)
    certificate_type = Column(String(80), nullable=False)
    status = Column(String(40), nullable=False, default="ACTIVE") # ACTIVE, REVOKED, EXPIRED, SUSPENDED
    revocation_reason = Column(String(255), nullable=True)
    is_simulation = Column(Boolean, default=True)


class ResourceClaim(Base):
    __tablename__ = "resource_claims"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    resource_type = Column(String(60), nullable=False, index=True) # FACULTY, LAND_PARCEL, LAB_EQUIPMENT, BUILDING
    entity_identifier = Column(String(100), nullable=False, index=True) # PAN, Aadhaar Hash, Survey No, Machine Serial
    entity_name = Column(String(200), nullable=False)
    details_json = Column(Text, nullable=True)
    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ResourceConflict(Base):
    __tablename__ = "resource_conflicts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    primary_claim_id = Column(Integer, ForeignKey("resource_claims.id"), nullable=False)
    conflicting_claim_id = Column(Integer, ForeignKey("resource_claims.id"), nullable=False)
    primary_app_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    conflicting_app_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    resource_type = Column(String(60), nullable=False)
    match_score = Column(Float, nullable=False) # 0 to 100
    match_method = Column(String(50), nullable=False) # EXACT_ID, FUZZY_NAME_AND_PAN
    explanation = Column(Text, nullable=False)
    status = Column(String(40), default="UNREVIEWED") # UNREVIEWED, CONFIRMED_CONFLICT, DISMISSED_LEGITIMATE
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class RegulatoryRule(Base):
    __tablename__ = "regulatory_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(80), nullable=False, index=True) # e.g. RULE-APH24-LAND-01
    version = Column(String(30), nullable=False, default="1.0.0")
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    aph_edition = Column(String(100), nullable=False, default=APH_DEFAULT_EDITION)
    clause_reference = Column(String(100), nullable=False) # e.g. Chapter VI Clause 6.1
    page_reference = Column(String(50), nullable=False) # e.g. Book p. 86 (PDF p. 102)
    source_excerpt = Column(Text, nullable=False)
    category = Column(String(60), nullable=False) # Infrastructure, Safety, Faculty, Computer, Library
    applicability_json = Column(Text, nullable=True) # Dict of applicable programs, years
    evaluation_logic_json = Column(Text, nullable=False) # DSL / structure for condition
    required_evidence_json = Column(Text, nullable=False) # List of required docs/fields
    effective_from = Column(String(30), default="2024-04-01")
    effective_to = Column(String(30), default="2027-03-31")
    status = Column(String(40), nullable=False, default="PUBLISHED") # DRAFT, PENDING_APPROVAL, PUBLISHED, SUPERSEDED
    is_verified = Column(Boolean, default=True) # True only if grounded in official text
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ComplianceEvaluation(Base):
    __tablename__ = "compliance_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    rule_set_version = Column(String(50), nullable=False, default="1.0.0-APH2024-27")
    evaluation_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    consolidated_score = Column(Float, nullable=False, default=0.0) # Transparent index
    total_rules_evaluated = Column(Integer, default=0)
    passed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    missing_evidence_count = Column(Integer, default=0)
    unresolved_count = Column(Integer, default=0)
    evaluated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    application = relationship("Application", back_populates="evaluations")
    findings = relationship("ComplianceFinding", back_populates="evaluation", cascade="all, delete-orphan")


class ComplianceFinding(Base):
    __tablename__ = "compliance_findings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    evaluation_id = Column(Integer, ForeignKey("compliance_evaluations.id"), nullable=False, index=True)
    rule_id = Column(String(80), nullable=False, index=True)
    rule_version = Column(String(30), nullable=False)
    status = Column(String(40), nullable=False) # COMPLIANT, NON_COMPLIANT, MISSING_EVIDENCE, UNRESOLVED, etc.
    aph_clause = Column(String(100), nullable=False)
    source_passage = Column(Text, nullable=True)
    evidence_doc_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    evidence_page = Column(Integer, nullable=True)
    extracted_value = Column(String(255), nullable=True)
    validation_method = Column(String(100), nullable=False)
    explanation = Column(Text, nullable=False)
    reviewer_override_status = Column(String(40), nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    evaluation = relationship("ComplianceEvaluation", back_populates="findings")


class RuleChangeReplayRun(Base):
    __tablename__ = "rule_change_replay_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_rule_version = Column(String(40), nullable=False)
    target_rule_version = Column(String(40), nullable=False)
    total_applications_replayed = Column(Integer, default=0)
    changed_outcomes_count = Column(Integer, default=0)
    details_json = Column(Text, nullable=True)
    run_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ReviewComment(Base):
    __tablename__ = "review_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    finding_id = Column(Integer, ForeignKey("compliance_findings.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_role = Column(String(40), nullable=False)
    comment_type = Column(String(50), nullable=False) # CLARIFICATION_REQUEST, SCRUTINY_NOTE, COMMITTEE_REMARKS
    comment_text = Column(Text, nullable=False)
    is_clarification_request = Column(Boolean, default=False)
    applicant_response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

    application = relationship("Application", back_populates="comments")


class GeneratedReport(Base):
    __tablename__ = "generated_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    report_type = Column(String(60), nullable=False, default="FULL_SCRUTINY_AUDIT_REPORT")
    file_path = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=False)
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_id = Column(Integer, nullable=True, index=True)
    actor_username = Column(String(80), nullable=False, index=True)
    actor_role = Column(String(40), nullable=False)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(80), nullable=True)
    target_id = Column(String(80), nullable=True)
    ip_address = Column(String(50), default="127.0.0.1")
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


# ---------------------------------------------------------
# Engine & Session Management
# ---------------------------------------------------------

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

def get_db_session() -> Session:
    """Yield a database session context."""
    db = SessionLocal()
    try:
        return db
    finally:
        pass


def init_db(seed_data: bool = True):
    """Create all tables and seed standard demo data."""
    Base.metadata.create_all(bind=engine)
    if seed_data:
        seed_database()


def hash_pwd(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed_database():
    """Seed initial demo accounts, institutions, rules, and mock registry."""
    db = SessionLocal()
    try:
        # Check if users already seeded
        if db.query(User).first() is not None:
            return

        print("Seeding database with initial users, institutions, rules and mock registry...")

        # 1. Institutions
        inst_apex = Institution(
            aicte_id="1-3329104811",
            name="Apex Institute of Technology & Engineering",
            address="Plot No. 12-14, Knowledge Corridor, Sector 62",
            state="Uttar Pradesh",
            district="Gautam Buddha Nagar",
            institution_type="Private-Self Financed",
            category="Engineering & Technology",
            minority_status="Non-Minority",
            contact_email="principal@apex-tech.edu.in",
            phone="+91-120-4567890",
        )
        inst_bharat = Institution(
            aicte_id="1-4829103219",
            name="Bharat Institute of Science & Technology",
            address="Survey No. 45/2, Ring Road, Marathahalli",
            state="Karnataka",
            district="Bengaluru Urban",
            institution_type="Private-Self Financed",
            category="Engineering & Technology",
            minority_status="Non-Minority",
            contact_email="admin@bharat-tech.ac.in",
            phone="+91-80-23456789",
        )
        inst_poly = Institution(
            aicte_id="1-1928374650",
            name="Greenfield Polytechnic College",
            address="Near NH-44, Industrial Area",
            state="Haryana",
            district="Sonipat",
            institution_type="Govt-Aided",
            category="Engineering & Technology",
            minority_status="Non-Minority",
            contact_email="principal@greenfieldpoly.edu.in",
            phone="+91-130-2233445",
        )
        db.add_all([inst_apex, inst_bharat, inst_poly])
        db.commit()

        # 2. Seed Users across all 8 Prototype Roles
        demo_password_hash = hash_pwd("Samiksha@2026")

        users = [
            User(
                username="applicant_apex",
                email="applicant.apex@demo.aicte.gov.in",
                password_hash=demo_password_hash,
                full_name="Dr. Rajesh Kumar (Apex Tech Principal)",
                role=Roles.APPLICANT,
                institution_id=inst_apex.id,
            ),
            User(
                username="applicant_bharat",
                email="applicant.bharat@demo.aicte.gov.in",
                password_hash=demo_password_hash,
                full_name="Prof. Sunita Rao (Bharat Tech Dean)",
                role=Roles.APPLICANT,
                institution_id=inst_bharat.id,
            ),
            User(
                username="scrutiny_sharma",
                email="s.sharma@demo.aicte.gov.in",
                password_hash=demo_password_hash,
                full_name="Er. Suresh Sharma",
                role=Roles.SCRUTINY_OFFICER,
            ),
            User(
                username="inspection_verma",
                email="a.verma@demo.aicte.gov.in",
                password_hash=demo_password_hash,
                full_name="Prof. Anita Verma",
                role=Roles.INSPECTION_OFFICER,
            ),
            User(
                username="coord_aicte",
                email="coord.reg@demo.aicte.gov.in",
                password_hash=demo_password_hash,
                full_name="Dr. Manoj Deshmukh (Case Coordinator)",
                role=Roles.CASE_COORDINATOR,
            ),
            User(
                username="reviewer_comm",
                email="reviewer.comm@demo.aicte.gov.in",
                password_hash=demo_password_hash,
                full_name="Prof. Arvind Swaminathan (Committee Member)",
                role=Roles.COMMITTEE_REVIEWER,
            ),
            User(
                username="director_reg",
                email="director.regulation@demo.aicte.gov.in",
                password_hash=demo_password_hash,
                full_name="Advisor & Bureau Head (Regulation)",
                role=Roles.DECISION_AUTHORITY,
            ),
            User(
                username="rules_officer",
                email="rules.admin@demo.aicte.gov.in",
                password_hash=demo_password_hash,
                full_name="Shri K. Ramanathan (Rules Administrator)",
                role=Roles.RULES_ADMIN,
            ),
            User(
                username="admin_tech",
                email="tech.admin@demo.aicte.gov.in",
                password_hash=demo_password_hash,
                full_name="Systems Engineer (Technical Admin)",
                role=Roles.TECH_ADMIN,
            ),
        ]
        db.add_all(users)
        db.commit()

        # 3. Seed Mock Issuer Records (Simulated Registry with 7 Controlled Test Cases)
        mock_records = [
            MockIssuerRecord(
                certificate_number="FS-UP-2024-88392",
                holder_name="Apex Institute of Technology & Engineering",
                issuing_authority="Directorate of Fire & Emergency Services, Uttar Pradesh",
                issue_date="2024-02-15",
                expiry_date="2027-02-14",
                certificate_type="FIRE_SAFETY",
                status="ACTIVE",
                is_simulation=True,
            ),
            MockIssuerRecord(
                certificate_number="OC-NOIDA-2023-1102",
                holder_name="Apex Institute of Technology & Engineering",
                issuing_authority="New Okhla Industrial Development Authority (NOIDA)",
                issue_date="2023-11-20",
                expiry_date=None,
                certificate_type="OCCUPANCY",
                status="ACTIVE",
                is_simulation=True,
            ),
            MockIssuerRecord(
                certificate_number="FS-KA-2022-00412",
                holder_name="Bharat Institute of Science & Technology",
                issuing_authority="Karnataka State Fire and Emergency Services",
                issue_date="2022-01-10",
                expiry_date="2023-01-09", # EXPIRED
                certificate_type="FIRE_SAFETY",
                status="EXPIRED",
                is_simulation=True,
            ),
            MockIssuerRecord(
                certificate_number="FS-DL-REVOKED-991",
                holder_name="Capital City Institute of Engineering",
                issuing_authority="Delhi Fire Services",
                issue_date="2023-05-10",
                expiry_date="2026-05-09",
                certificate_type="FIRE_SAFETY",
                status="REVOKED",
                revocation_reason="Structural fire egress deficiency found during surprise physical audit",
                is_simulation=True,
            ),
            MockIssuerRecord(
                certificate_number="LU-HR-2021-MISMATCH",
                holder_name="Greenfield Agro Industries Ltd", # HOLDER MISMATCH
                issuing_authority="Town and Country Planning Department, Haryana",
                issue_date="2021-08-15",
                expiry_date=None,
                certificate_type="LAND_USE",
                status="ACTIVE",
                is_simulation=True,
            ),
        ]
        db.add_all(mock_records)
        db.commit()

        # 4. Seed 12 Verified AICTE APH 2024-27 Regulatory Rules
        rules_officer_user = db.query(User).filter_by(username="rules_officer").first()
        admin_id = rules_officer_user.id if rules_officer_user else 1

        verified_rules = [
            RegulatoryRule(
                rule_id="RULE-APH24-LAND-01",
                version="1.0.0",
                title="Maximum Number of Land Plots and Contiguity Norm",
                description="Land area required shall be in a maximum of THREE plots, contiguous with no barriers or public roads separating the parcels.",
                aph_edition=APH_DEFAULT_EDITION,
                clause_reference="Chapter VI Cl. 6.1 & Annexure 3 Cl. 3.1.g",
                page_reference="Book p. 86 (PDF p. 102)",
                source_excerpt="The Land area required shall be in a maximum of THREE plots. The Academic, Instructional, Administrative and Amenities area shall be contiguous and have no public road/railway track/canal or any other barrier separating them.",
                category="Infrastructure",
                applicability_json=json.dumps({"programs": ["All"], "categories": ["Setting up New Technical Institution", "Change of Site / Location"]}),
                evaluation_logic_json=json.dumps({"type": "max_plots_contiguity", "max_plots": 3, "require_contiguous": True, "no_barriers": True}),
                required_evidence_json=json.dumps(["Land Deed / Registry", "Architect Land Certificate (Certificate 1)", "Site Master Plan"]),
                status="PUBLISHED",
                is_verified=True,
                created_by=admin_id,
                approved_by=admin_id,
            ),
            RegulatoryRule(
                rule_id="RULE-APH24-LAND-02",
                version="1.0.0",
                title="Land Ownership Title and Educational Land Use Conversion",
                description="Institution must possess clear land ownership or irrevocable registered lease of >=30 years and Land Conversion Certificate (CLU) for Educational Purpose.",
                aph_edition=APH_DEFAULT_EDITION,
                clause_reference="Annexure 1 Cl. 1.1.xii & Annexure 3 Cl. 3.1.c",
                page_reference="Book p. 77, 86 (PDF p. 93, 102)",
                source_excerpt="Documents showing ownership of Land/ Building as per provisions of Section 8 of Transfer of Property Act or registered lease deed for a minimum period of 30 years... Land Use Certificate permitting the Land to be used for Educational purpose from Competent Authority.",
                category="Infrastructure",
                applicability_json=json.dumps({"programs": ["All"], "categories": ["Setting up New Technical Institution"]}),
                evaluation_logic_json=json.dumps({"type": "land_title_clu", "valid_ownership_types": ["OWNED", "GOVT_ALLOTMENT", "REGISTERED_LEASE_30_PLUS"], "require_educational_clu": True}),
                required_evidence_json=json.dumps(["Registered Sale / Lease Deed", "Land Conversion Certificate (CLU)", "Non-Encumbrance Certificate"]),
                status="PUBLISHED",
                is_verified=True,
                created_by=admin_id,
                approved_by=admin_id,
            ),
            RegulatoryRule(
                rule_id="RULE-APH24-BLD-01",
                version="1.0.0",
                title="Approved Building Plan & Occupancy / Completion Certificate",
                description="Valid Occupancy or Completion Certificate issued by the Competent State / Municipal Authority must be provided.",
                aph_edition=APH_DEFAULT_EDITION,
                clause_reference="Chapter VI Cl. 6.1 & Annexure 1 Cl. 1.1.iv",
                page_reference="Book p. 53, 77 (PDF p. 69, 93)",
                source_excerpt="Copy of the approved Plan along with the Completion Certificate/ Occupancy certificate issued by the concerned State Government authority needs to be provided. In case of partial/ provisional Occupancy Certificate, the same shall be considered only for 2 consecutive Academic Years.",
                category="Infrastructure",
                applicability_json=json.dumps({"programs": ["All"], "categories": ["All"]}),
                evaluation_logic_json=json.dumps({"type": "occupancy_certificate_validity", "require_competent_authority": True, "allow_provisional_max_years": 2}),
                required_evidence_json=json.dumps(["Building Plan Approved by Competent Authority", "Occupancy / Completion Certificate"]),
                status="PUBLISHED",
                is_verified=True,
                created_by=admin_id,
                approved_by=admin_id,
            ),
            RegulatoryRule(
                rule_id="RULE-APH24-SAFE-01",
                version="1.0.0",
                title="Mandatory Fire & Life Safety Certificate",
                description="Fire and life Safety Certificate from Fire Department of concerned State Government authority must be obtained prior to application submission.",
                aph_edition=APH_DEFAULT_EDITION,
                clause_reference="Chapter VI Cl. 6.2.b & Annexure 1 Cl. 1.1.v",
                page_reference="Book p. 53, 77 (PDF p. 69, 93)",
                source_excerpt="Fire and life Safety Certificate from Fire Department of the concerned State Government authority is to be taken before submitting the application at AICTE.",
                category="Safety",
                applicability_json=json.dumps({"programs": ["All"], "categories": ["All"]}),
                evaluation_logic_json=json.dumps({"type": "fire_safety_validity", "require_active_date": True, "require_prior_issue": True}),
                required_evidence_json=json.dumps(["Fire Safety Certificate"]),
                status="PUBLISHED",
                is_verified=True,
                created_by=admin_id,
                approved_by=admin_id,
            ),
            RegulatoryRule(
                rule_id="RULE-APH24-SAFE-02",
                version="1.0.0",
                title="Barrier-Free Built Environment for Persons with Disabilities (PwD)",
                description="All academic and instructional buildings must have wheelchair ramps, lifts, and accessible PwD-friendly toilets.",
                aph_edition=APH_DEFAULT_EDITION,
                clause_reference="Chapter VI Cl. 6.2.d & Annexure 3 Cl. 3.2.f",
                page_reference="Book p. 53, 87 (PDF p. 69, 103)",
                source_excerpt="Institutions shall have Barrier free environment and Sports facilities as specified in Chapter VI... Ramps, lifts, and accessible toilets for Persons with Disabilities.",
                category="Accessibility",
                applicability_json=json.dumps({"programs": ["All"], "categories": ["All"]}),
                evaluation_logic_json=json.dumps({"type": "pwd_barrier_free", "require_ramps": True, "require_disabled_toilets": True, "require_lifts_multistory": True}),
                required_evidence_json=json.dumps(["Architect Barrier-Free Certificate (Certificate 2)", "Floor Plans Showing Accessible Toilets & Ramps"]),
                status="PUBLISHED",
                is_verified=True,
                created_by=admin_id,
                approved_by=admin_id,
            ),
            RegulatoryRule(
                rule_id="RULE-APH24-FSR-UG-01",
                version="1.0.0",
                title="Faculty-to-Student Ratio (1:20) for UG Engineering & Technology",
                description="Total full-time regular faculty must be at least Approved Intake x Duration / 20.0.",
                aph_edition=APH_DEFAULT_EDITION,
                clause_reference="Annexure 5 Cl. 5.2",
                page_reference="Book p. 95 (PDF p. 111)",
                source_excerpt="Engineering and Technology Under Graduate Degree Programme Faculty:Student Ratio based on Approved Intake = 1:20. Total Faculty = S / 20.",
                category="Faculty",
                applicability_json=json.dumps({"programs": ["Engineering & Technology"], "levels": ["Under Graduate Degree"]}),
                evaluation_logic_json=json.dumps({"type": "faculty_student_ratio", "ratio_target": 20.0, "program": "Engineering"}),
                required_evidence_json=json.dumps(["Faculty Master Register", "Appointment Letters", "Form 16 / Salary Bank Statement"]),
                status="PUBLISHED",
                is_verified=True,
                created_by=admin_id,
                approved_by=admin_id,
            ),
            RegulatoryRule(
                rule_id="RULE-APH24-CADRE-01",
                version="1.0.0",
                title="Faculty Cadre Ratio (1:2:6) for UG Engineering Degree",
                description="Faculty cadre ratio must satisfy Professor : Associate Professor : Assistant Professor = 1 : 2 : 6, with R = 9.",
                aph_edition=APH_DEFAULT_EDITION,
                clause_reference="Annexure 5 Cl. 5.2",
                page_reference="Book p. 95 (PDF p. 111)",
                source_excerpt="S - Sum of the number of students as per Approved Intake for all years, R = (1+2+6)=9. Professor = (S / (20xR)) x 1; Associate Professor = (S / (20xR)) x 2; Assistant Professor = (S / (20xR)) x 6.",
                category="Faculty",
                applicability_json=json.dumps({"programs": ["Engineering & Technology"], "levels": ["Under Graduate Degree"]}),
                evaluation_logic_json=json.dumps({"type": "cadre_ratio", "cadre_ratio_str": "1:2:6", "r_divisor": 9}),
                required_evidence_json=json.dumps(["Faculty Designation List", "Ph.D. & Experience Credentials"]),
                status="PUBLISHED",
                is_verified=True,
                created_by=admin_id,
                approved_by=admin_id,
            ),
            RegulatoryRule(
                rule_id="RULE-APH24-PRIN-01",
                version="1.0.0",
                title="Mandatory Appointment of Regular Qualified Principal / Director",
                description="Institution shall not commence courses without appointment of a full-time regular Principal/Director with AICTE-prescribed qualifications.",
                aph_edition=APH_DEFAULT_EDITION,
                clause_reference="Annexure 5 Cl. 5.2 & Chapter I Cl. 1.4.3.d",
                page_reference="Book p. 7, 95 (PDF p. 23, 111)",
                source_excerpt="An Institution shall not commence the Courses without the appointment of a regular Principal/Director and Faculty members as per AICTE norms.",
                category="Faculty",
                applicability_json=json.dumps({"programs": ["All"], "categories": ["All"]}),
                evaluation_logic_json=json.dumps({"type": "principal_appointed", "require_full_time": True, "require_phd": True}),
                required_evidence_json=json.dumps(["Principal Appointment Order", "Joining Report", "Ph.D. Degree Certificate"]),
                status="PUBLISHED",
                is_verified=True,
                created_by=admin_id,
                approved_by=admin_id,
            ),
            RegulatoryRule(
                rule_id="RULE-APH24-COMP-01",
                version="1.0.0",
                title="Computer-to-Student Ratio (UG 1:10) and Minimum 20 PCs Norm",
                description="Engineering UG requires 1 PC per 10 students with minimum 20 PCs, printers up to 5% of PCs, and all machines connected on LAN/Wi-Fi.",
                aph_edition=APH_DEFAULT_EDITION,
                clause_reference="Annexure 4 Cl. 4.1",
                page_reference="Book p. 92 (PDF p. 108)",
                source_excerpt="Engineering and Technology Under Graduate: Number of PCs/Laptop to student ratio = 1:10 (Minimum 20 PCs). The institutions shall possess printers up to a minimum 5% of total number of PCs/Laptops. All PCs/Laptops connected through LAN/Wi-Fi.",
                category="IT Infrastructure",
                applicability_json=json.dumps({"programs": ["Engineering & Technology"], "levels": ["Under Graduate Degree"]}),
                evaluation_logic_json=json.dumps({"type": "computer_ratio", "ratio_target": 10.0, "min_pcs": 20, "printer_percentage": 5.0, "networked": True}),
                required_evidence_json=json.dumps(["Computer Stock Register", "Purchase Invoices", "Network Layout & Bandwidth Receipt"]),
                status="PUBLISHED",
                is_verified=True,
                created_by=admin_id,
                approved_by=admin_id,
            ),
            RegulatoryRule(
                rule_id="RULE-APH24-LIB-01",
                version="1.0.0",
                title="Norms for Library Volumes, Titles, and Reading Room Seating Capacity",
                description="Prescribed minimum book titles and volumes per division; reading room seating capacity at least 15% of total students (max 150).",
                aph_edition=APH_DEFAULT_EDITION,
                clause_reference="Annexure 4 Cl. 4.3",
                page_reference="Book p. 93 (PDF p. 109)",
                source_excerpt="Reading Room Seating Capacity = 15% of Total Students (Maximum 150). Prescribed titles and volumes per division.",
                category="Library",
                applicability_json=json.dumps({"programs": ["All"], "categories": ["All"]}),
                evaluation_logic_json=json.dumps({"type": "library_capacity", "min_seating_pct": 0.15, "max_seating_cap": 150}),
                required_evidence_json=json.dumps(["Library Accession Register", "Reading Room Layout Plan", "Book Invoices"]),
                status="PUBLISHED",
                is_verified=True,
                created_by=admin_id,
                approved_by=admin_id,
            ),
            RegulatoryRule(
                rule_id="RULE-APH24-COMM-01",
                version="1.0.0",
                title="Mandatory Statutory Grievance, Anti-Ragging, and POSH Committees",
                description="Conception and active notification of Anti-Ragging Committee & Squad (Regulations 2009), Internal Complaints Committee (POSH 2013), and Student Grievance Redressal Committee (Regulations 2019).",
                aph_edition=APH_DEFAULT_EDITION,
                clause_reference="Chapter VI Cl. 6.2.g, 6.2.h, 6.2.i",
                page_reference="Book p. 54 (PDF p. 70)",
                source_excerpt="Establishment of Anti-Ragging Committee (Clause 6.2.g), Establishment of Grievance Redressal Committee in the Technical Institution and Appointment of OMBUDSPERSON (Clause 6.2.h), Establishment of Internal Committee (IC) as per Section 4 of POSH Act 2013 (Clause 6.2.i).",
                category="Governance",
                applicability_json=json.dumps({"programs": ["All"], "categories": ["All"]}),
                evaluation_logic_json=json.dumps({"type": "statutory_committees", "committees_required": ["ANTI_RAGGING", "INTERNAL_COMPLAINTS_ICC", "GRIEVANCE_REDRESSAL_SGRC"]}),
                required_evidence_json=json.dumps(["Committee Office Notification Orders", "Membership Rosters", "Website URL Disclosures"]),
                status="PUBLISHED",
                is_verified=True,
                created_by=admin_id,
                approved_by=admin_id,
            ),
            RegulatoryRule(
                rule_id="RULE-APH24-DOCS-01",
                version="1.0.0",
                title="Mandatory Scrutiny Document Checklist Completeness",
                description="All mandatory Annexure 1 / Annexure 2 documents must be submitted (Affidavits 1, 2, 4, Bank Certificate 3, Architect Certificate 2, Resolution Format 3).",
                aph_edition=APH_DEFAULT_EDITION,
                clause_reference="Annexure 1 Cl. 1.1 & Annexure 2 Cl. 2.1",
                page_reference="Book p. 77, 81 (PDF p. 93, 97)",
                source_excerpt="Documents to be uploaded/submitted/shown at the time of the Scrutiny/Re-Scrutiny: Building Plan, Affidavit 2, Resolution Format 3, Occupancy Certificate, Fire Safety Certificate, Bank Certificate 3, Registration Document, Land Ownership Documents.",
                category="Documentation",
                applicability_json=json.dumps({"programs": ["All"], "categories": ["All"]}),
                evaluation_logic_json=json.dumps({"type": "mandatory_doc_checklist", "mandatory_keys": ["FIRE_SAFETY", "OCCUPANCY_CERT", "LAND_TITLE_DEED", "AFFIDAVIT_2", "BANK_CERT_3"]}),
                required_evidence_json=json.dumps(["Document Inventory Submissions"]),
                status="PUBLISHED",
                is_verified=True,
                created_by=admin_id,
                approved_by=admin_id,
            ),
        ]
        db.add_all(verified_rules)
        db.commit()

        # 5. Seed Demo Applications
        app_apex = Application(
            application_no="AICTE-2025-APP-0091",
            institution_id=inst_apex.id,
            academic_year="2025-26",
            category="Setting up New Technical Institution",
            program="Engineering & Technology",
            status="UNDER_SCRUTINY",
            current_stage="Scrutiny Committee Review",
            approved_intake=360,
            total_land_acres=7.5,
            built_up_area_sqm=5800.0,
            submission_date=datetime.now(timezone.utc),
            created_by=users[0].id, # applicant_apex
            assigned_to=users[2].id, # scrutiny_sharma
            version=1,
        )
        app_bharat = Application(
            application_no="AICTE-2025-APP-0092",
            institution_id=inst_bharat.id,
            academic_year="2025-26",
            category="Extension of Approval (EoA)",
            program="Engineering & Technology",
            status="SUBMITTED",
            current_stage="Document Integrity & Certificate Verification",
            approved_intake=480,
            total_land_acres=5.2,
            built_up_area_sqm=6200.0,
            submission_date=datetime.now(timezone.utc),
            created_by=users[1].id, # applicant_bharat
            version=1,
        )
        db.add_all([app_apex, app_bharat])
        db.commit()

        # 6. Audit Event for System Initialization
        audit = AuditEvent(
            actor_id=admin_id,
            actor_username="SYSTEM_INIT",
            actor_role="SYSTEM",
            action="DATABASE_SEEDED",
            target_type="SYSTEM",
            target_id="samiksha.db",
            details_json=json.dumps({
                "message": "Initialized schema and seeded verified AICTE APH 2024-27 rules and accounts",
                "rules_count": len(verified_rules),
                "demo_users_count": len(users),
            }),
        )
        db.add(audit)
        db.commit()

        print("Database successfully seeded with verified regulatory baseline!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    init_db(seed_data=True)
