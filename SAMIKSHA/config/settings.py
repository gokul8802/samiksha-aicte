"""
Samiksha Configuration & Settings
AICTE Approval Process Handbook (2024-25 to 2026-27) Compliance Verification
Smart India Hackathon (SIH) 2026 - Problem Statement 26261
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"
UPLOADS_DIR = BASE_DIR / "uploads"
REPORTS_DIR = BASE_DIR / "reports_generated"
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
CHECKPOINTS_DIR = MODELS_DIR / "checkpoints"

# Ensure directories exist
for d in [UPLOADS_DIR, REPORTS_DIR, DATA_DIR, CHECKPOINTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# System Information
APP_NAME = "Samiksha"
APP_SUBTITLE = "AICTE Institutional Validation & Compliance Verification Platform"
AICTE_BUREAU = "Regulation Bureau"
SIH_PROBLEM_ID = "26261"
APH_DEFAULT_EDITION = "Approval Process Handbook 2024-25 to 2026-27"
APH_PDF_PATH = DOCS_DIR / "AICTE_APH_2024-25_to_2026-27.pdf"

# Database Configuration (SQLite default with PostgreSQL URL migration support)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'samiksha.db'}")

# Security & Upload Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "samiksha-sih2026-secure-regulatory-salt-token")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "25"))
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
}

# Role Definitions
class Roles:
    APPLICANT = "APPLICANT"
    SCRUTINY_OFFICER = "SCRUTINY_OFFICER"
    INSPECTION_OFFICER = "INSPECTION_OFFICER"
    CASE_COORDINATOR = "CASE_COORDINATOR"
    COMMITTEE_REVIEWER = "COMMITTEE_REVIEWER"
    DECISION_AUTHORITY = "DECISION_AUTHORITY"
    RULES_ADMIN = "RULES_ADMIN"
    TECH_ADMIN = "TECH_ADMIN"

    ALL = [
        APPLICANT,
        SCRUTINY_OFFICER,
        INSPECTION_OFFICER,
        CASE_COORDINATOR,
        COMMITTEE_REVIEWER,
        DECISION_AUTHORITY,
        RULES_ADMIN,
        TECH_ADMIN,
    ]

    LABELS = {
        APPLICANT: "Institution Applicant",
        SCRUTINY_OFFICER: "Scrutiny Officer",
        INSPECTION_OFFICER: "Inspection Officer",
        CASE_COORDINATOR: "Regulation Bureau Coordinator",
        COMMITTEE_REVIEWER: "Committee Reviewer",
        DECISION_AUTHORITY: "Authorized Decision Authority",
        RULES_ADMIN: "Rules Administrator",
        TECH_ADMIN: "Technical Administrator",
    }

# Fine-grained Permissions
class Permissions:
    # Applications
    CREATE_APPLICATION = "create_application"
    VIEW_OWN_APPLICATION = "view_own_application"
    VIEW_ALL_APPLICATIONS = "view_all_applications"
    ASSIGN_APPLICATION = "assign_application"
    SUBMIT_APPLICATION = "submit_application"
    CHANGE_APP_STATUS = "change_app_status"
    RECORD_DECISION = "record_decision"

    # Documents
    UPLOAD_DOCUMENT = "upload_document"
    VIEW_DOCUMENT = "view_document"
    DELETE_DOCUMENT = "delete_document"

    # Verifications & Analysis
    RUN_TAMPERING_ANALYSIS = "run_tampering_analysis"
    RUN_CERTIFICATE_VERIFY = "run_certificate_verify"
    RUN_RESOURCE_INTELLIGENCE = "run_resource_intelligence"
    RUN_COMPLIANCE_EVAL = "run_compliance_eval"

    # Scrutiny & Comments
    ADD_SCRUTINY_FINDING = "add_scrutiny_finding"
    REQUEST_CLARIFICATION = "request_clarification"
    RESPOND_CLARIFICATION = "respond_clarification"
    ADD_COMMITTEE_NOTE = "add_committee_note"

    # Regulatory Rules
    PROPOSE_RULE = "propose_rule"
    EDIT_DRAFT_RULE = "edit_draft_rule"
    APPROVE_RULE = "approve_rule"
    PUBLISH_RULE = "publish_rule"
    RUN_RULE_REPLAY = "run_rule_replay"

    # Reports & Audit
    GENERATE_REPORT = "generate_report"
    DOWNLOAD_REPORT = "download_report"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    ADMIN_SETTINGS = "admin_settings"

# Mapping Roles to Allowed Permissions
ROLE_PERMISSIONS = {
    Roles.APPLICANT: {
        Permissions.CREATE_APPLICATION,
        Permissions.VIEW_OWN_APPLICATION,
        Permissions.SUBMIT_APPLICATION,
        Permissions.UPLOAD_DOCUMENT,
        Permissions.VIEW_DOCUMENT,
        Permissions.RESPOND_CLARIFICATION,
        Permissions.DOWNLOAD_REPORT,
    },
    Roles.SCRUTINY_OFFICER: {
        Permissions.VIEW_ALL_APPLICATIONS,
        Permissions.VIEW_DOCUMENT,
        Permissions.RUN_TAMPERING_ANALYSIS,
        Permissions.RUN_CERTIFICATE_VERIFY,
        Permissions.RUN_RESOURCE_INTELLIGENCE,
        Permissions.RUN_COMPLIANCE_EVAL,
        Permissions.ADD_SCRUTINY_FINDING,
        Permissions.REQUEST_CLARIFICATION,
        Permissions.GENERATE_REPORT,
        Permissions.DOWNLOAD_REPORT,
    },
    Roles.INSPECTION_OFFICER: {
        Permissions.VIEW_ALL_APPLICATIONS,
        Permissions.VIEW_DOCUMENT,
        Permissions.ADD_SCRUTINY_FINDING,
        Permissions.GENERATE_REPORT,
        Permissions.DOWNLOAD_REPORT,
    },
    Roles.CASE_COORDINATOR: {
        Permissions.VIEW_ALL_APPLICATIONS,
        Permissions.ASSIGN_APPLICATION,
        Permissions.VIEW_DOCUMENT,
        Permissions.CHANGE_APP_STATUS,
        Permissions.REQUEST_CLARIFICATION,
        Permissions.GENERATE_REPORT,
        Permissions.DOWNLOAD_REPORT,
        Permissions.VIEW_AUDIT_LOGS,
    },
    Roles.COMMITTEE_REVIEWER: {
        Permissions.VIEW_ALL_APPLICATIONS,
        Permissions.VIEW_DOCUMENT,
        Permissions.ADD_COMMITTEE_NOTE,
        Permissions.DOWNLOAD_REPORT,
    },
    Roles.DECISION_AUTHORITY: {
        Permissions.VIEW_ALL_APPLICATIONS,
        Permissions.VIEW_DOCUMENT,
        Permissions.RECORD_DECISION,
        Permissions.CHANGE_APP_STATUS,
        Permissions.DOWNLOAD_REPORT,
        Permissions.VIEW_AUDIT_LOGS,
    },
    Roles.RULES_ADMIN: {
        Permissions.VIEW_ALL_APPLICATIONS,
        Permissions.PROPOSE_RULE,
        Permissions.EDIT_DRAFT_RULE,
        Permissions.APPROVE_RULE,
        Permissions.PUBLISH_RULE,
        Permissions.RUN_RULE_REPLAY,
        Permissions.VIEW_AUDIT_LOGS,
    },
    Roles.TECH_ADMIN: {
        Permissions.VIEW_ALL_APPLICATIONS,
        Permissions.VIEW_DOCUMENT,
        Permissions.ADMIN_SETTINGS,
        Permissions.VIEW_AUDIT_LOGS,
        Permissions.DOWNLOAD_REPORT,
    },
}

# Application Categories
APPLICATION_CATEGORIES = [
    "Setting up New Technical Institution",
    "Extension of Approval (EoA)",
    "Increase in Intake / Additional Course(s)",
    "Closure of Course / Institution",
    "Change of Site / Location",
    "Conversion of Diploma to Degree / Vice Versa",
    "Collaboration & Twinning Programme",
]

# Evaluation Statuses (Strictly non-autonomous decision support)
class EvaluationStatus:
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    EVIDENCE_MISMATCH = "EVIDENCE_MISMATCH"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
