"""
Executive Regulatory Scrutiny Report Generator for Samiksha
Generates high-fidelity PDF Dossiers using ReportLab with full regulation-to-evidence traceability.
"""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from config.settings import REPORTS_DIR, APH_DEFAULT_EDITION
from modules.database import (
    get_db_session, Application, Document, Certificate, ComplianceEvaluation,
    ComplianceFinding, ResourceConflict, ReviewComment, GeneratedReport
)
from modules.audit_logger import log_audit_event


def generate_application_pdf_report(application_id: int, generated_by_user) -> str:
    """Generate comprehensive PDF report for an application and return file path."""
    db = get_db_session()
    try:
        app = db.query(Application).filter_by(id=application_id).first()
        if not app:
            raise ValueError(f"Application {application_id} not found.")

        filename = f"SAMIKSHA_REPORT_{app.application_no}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = REPORTS_DIR / filename

        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#0f172a"),
            alignment=1, # Center
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#0284c7"),
            alignment=1,
        )
        section_style = ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading2"],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=10,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "BodyDark",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#1e293b"),
        )
        badge_style = ParagraphStyle(
            "Badge",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#475569"),
            alignment=1,
        )

        elements = []

        # 1. Header
        elements.append(Paragraph("ALL INDIA COUNCIL FOR TECHNICAL EDUCATION", title_style))
        elements.append(Paragraph("REGULATION BUREAU • SAMIKSHA INSTITUTIONAL VALIDATION PLATFORM", subtitle_style))
        elements.append(Paragraph(f"<b>Statutory Dossier:</b> {app.category} | Academic Year: {app.academic_year}", subtitle_style))
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceAfter=12))

        # 2. Executive Metadata Box
        inst_name = app.institution.name if app.institution else "N/A"
        aicte_id = app.institution.aicte_id if app.institution else "N/A"
        eval_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        app_info = [
            [Paragraph("<b>Application Number:</b>", body_style), Paragraph(app.application_no, body_style),
             Paragraph("<b>AICTE Permanent ID:</b>", body_style), Paragraph(aicte_id, body_style)],
            [Paragraph("<b>Institution Name:</b>", body_style), Paragraph(inst_name, body_style),
             Paragraph("<b>Current Status:</b>", body_style), Paragraph(f"<b>{app.status}</b>", body_style)],
            [Paragraph("<b>Regulatory Baseline:</b>", body_style), Paragraph(APH_DEFAULT_EDITION, body_style),
             Paragraph("<b>Intake / Land:</b>", body_style), Paragraph(f"{app.approved_intake} seats | {app.total_land_acres} Acres", body_style)],
            [Paragraph("<b>Dossier Generated:</b>", body_style), Paragraph(eval_time, body_style),
             Paragraph("<b>Officer / Role:</b>", body_style), Paragraph(f"{generated_by_user.full_name} ({generated_by_user.role})", body_style)],
        ]
        t_meta = Table(app_info, colWidths=[110, 160, 110, 160])
        t_meta.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(t_meta)
        elements.append(Spacer(1, 14))

        # 3. Document Inventory & Integrity Summary
        elements.append(Paragraph("1. Document Inventory & Visual Authenticity Indicators", section_style))
        docs = db.query(Document).filter_by(application_id=app.id).all()
        if not docs:
            elements.append(Paragraph("<i>No supporting documents uploaded to current application dossier.</i>", body_style))
        else:
            doc_rows = [[Paragraph("<b>Document Type</b>", body_style),
                         Paragraph("<b>Filename</b>", body_style),
                         Paragraph("<b>SHA-256 Digest</b>", body_style),
                         Paragraph("<b>Version</b>", body_style),
                         Paragraph("<b>Status</b>", body_style)]]
            for d in docs:
                doc_rows.append([
                    Paragraph(d.document_type, body_style),
                    Paragraph(d.filename[:28] + "...", body_style),
                    Paragraph(d.sha256_hash[:16] + "...", body_style),
                    Paragraph(f"v{d.version}", body_style),
                    Paragraph(d.status, body_style),
                ])
            t_docs = Table(doc_rows, colWidths=[130, 160, 120, 50, 80])
            t_docs.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
                ('TOPPADDING', (0,0), (-1,-1), 3),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ]))
            elements.append(t_docs)
        elements.append(Spacer(1, 14))

        # 4. Certificate Verification Summary
        elements.append(Paragraph("2. Statutory Certificate Verification Gateway", section_style))
        certs = db.query(Certificate).filter_by(application_id=app.id).all()
        if not certs:
            elements.append(Paragraph("<i>No certificates submitted or verified.</i>", body_style))
        else:
            cert_rows = [[Paragraph("<b>Certificate No</b>", body_style),
                          Paragraph("<b>Type</b>", body_style),
                          Paragraph("<b>Authority</b>", body_style),
                          Paragraph("<b>Result Status</b>", body_style),
                          Paragraph("<b>Verification Source</b>", body_style)]]
            for c in certs:
                cert_rows.append([
                    Paragraph(c.certificate_number, body_style),
                    Paragraph(c.certificate_type, body_style),
                    Paragraph(c.issuing_authority[:25] + "...", body_style),
                    Paragraph(f"<b>{c.verification_status}</b>", body_style),
                    Paragraph(c.verification_source, body_style),
                ])
            t_certs = Table(cert_rows, colWidths=[110, 80, 130, 110, 110])
            t_certs.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
                ('TOPPADDING', (0,0), (-1,-1), 3),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ]))
            elements.append(t_certs)
        elements.append(Spacer(1, 14))

        # 5. Deterministic Compliance Findings
        elements.append(Paragraph("3. AICTE APH 2024–27 Clause-by-Clause Compliance Findings", section_style))
        latest_eval = db.query(ComplianceEvaluation).filter_by(application_id=app.id).order_by(ComplianceEvaluation.created_at.desc()).first()
        if not latest_eval:
            elements.append(Paragraph("<i>Compliance evaluation has not yet been triggered for this application.</i>", body_style))
        else:
            elements.append(Paragraph(
                f"<b>Consolidated Compliance Index:</b> {latest_eval.consolidated_score:.1f}% | "
                f"<b>Compliant:</b> {latest_eval.passed_count} | <b>Deficiencies:</b> {latest_eval.failed_count} | "
                f"<b>Missing Evidence:</b> {latest_eval.missing_evidence_count}",
                body_style
            ))
            elements.append(Spacer(1, 6))

            findings = db.query(ComplianceFinding).filter_by(evaluation_id=latest_eval.id).all()
            finding_rows = [[Paragraph("<b>Rule ID</b>", body_style),
                             Paragraph("<b>Clause / Page</b>", body_style),
                             Paragraph("<b>Status</b>", body_style),
                             Paragraph("<b>Validation Explanation & Extracted Evidence</b>", body_style)]]
            for f in findings:
                finding_rows.append([
                    Paragraph(f"<b>{f.rule_id}</b>", body_style),
                    Paragraph(f.aph_clause, body_style),
                    Paragraph(f"<b>{f.status}</b>", body_style),
                    Paragraph(f"{f.explanation}<br/><font color='#64748b'>Evidence: {f.extracted_value}</font>", body_style),
                ])
            t_findings = Table(finding_rows, colWidths=[100, 110, 80, 250])
            t_findings.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
                ('TOPPADDING', (0,0), (-1,-1), 3),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ]))
            elements.append(t_findings)
        elements.append(Spacer(1, 14))

        # 6. Scrutiny Notes & Clarifications
        elements.append(Paragraph("4. Scrutiny Officer Remarks & Institutional Clarifications", section_style))
        comments = db.query(ReviewComment).filter_by(application_id=app.id).all()
        if not comments:
            elements.append(Paragraph("<i>No review notes or clarification requests registered.</i>", body_style))
        else:
            comm_rows = [[Paragraph("<b>Timestamp</b>", body_style),
                          Paragraph("<b>Role</b>", body_style),
                          Paragraph("<b>Type</b>", body_style),
                          Paragraph("<b>Observation / Response</b>", body_style)]]
            for c in comments:
                content = f"<b>Observation:</b> {c.comment_text}"
                if c.applicant_response:
                    content += f"<br/><b>Institutional Response:</b> {c.applicant_response}"
                comm_rows.append([
                    Paragraph(c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "", body_style),
                    Paragraph(c.user_role, body_style),
                    Paragraph(c.comment_type, body_style),
                    Paragraph(content, body_style),
                ])
            t_comms = Table(comm_rows, colWidths=[90, 80, 100, 270])
            t_comms.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
                ('TOPPADDING', (0,0), (-1,-1), 3),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ]))
            elements.append(t_comms)
        elements.append(Spacer(1, 16))

        # 7. Legal Disclaimer & Decision-Support Notice
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94a3b8"), spaceAfter=8))
        disclaimer = (
            "<b>STATUTORY DISCLAIMER:</b> Samiksha is an explainable decision-support system built for the "
            "AICTE Regulation Bureau (SIH 2026). It does not autonomously issue official approval, rejection, "
            "or fraud findings. All findings are traceable to AICTE Approval Process Handbook (2024-25 to 2026-27). "
            "Final regulatory decisions remain under the exclusive jurisdiction of the authorized statutory authority."
        )
        elements.append(Paragraph(disclaimer, badge_style))

        # Build PDF
        doc.build(elements)

        # Compute hash
        with open(filepath, "rb") as f:
            pdf_hash = hashlib.sha256(f.read()).hexdigest()

        # Persist report record
        rep_record = GeneratedReport(
            application_id=app.id,
            report_type="REGULATORY_SCRUTINY_DOSSIER",
            file_path=str(filepath),
            file_hash=pdf_hash,
            generated_by=generated_by_user.id,
        )
        db.add(rep_record)
        db.commit()

        log_audit_event(
            actor_id=generated_by_user.id,
            actor_username=generated_by_user.username,
            actor_role=generated_by_user.role,
            action="PDF_REPORT_GENERATED",
            target_type="APPLICATION",
            target_id=app.application_no,
            details={"file_name": filename, "hash": pdf_hash},
            db_session=db,
        )

        return str(filepath)

    finally:
        db.close()
