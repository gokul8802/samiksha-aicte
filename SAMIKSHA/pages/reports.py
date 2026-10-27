"""
Reports and Dossiers Page for Samiksha
Generates and downloads statutory PDF validation dossiers with cryptographic hashes.
"""

import streamlit as st
from pathlib import Path
from modules.database import get_db_session, Application, GeneratedReport
from modules.permissions import can_user, Permissions
from modules.report_generator import generate_application_pdf_report
from config.settings import Roles


def render_reports(user):
    st.markdown("## 📄 Statutory Reports & Scrutiny Dossiers")
    st.markdown(
        "*Download official evidence dossiers containing complete clause-by-clause regulatory traceability.*"
    )

    if not can_user(user, Permissions.DOWNLOAD_REPORT):
        st.error("Access Denied: You do not possess the `download_report` permission.")
        return

    db = get_db_session()
    try:
        if user.role == Roles.APPLICANT and user.institution_id:
            apps = db.query(Application).filter(Application.institution_id == user.institution_id).all()
        else:
            apps = db.query(Application).all()

        if not apps:
            st.info("No applications available to generate reports.")
            return

        app_options = {f"{a.application_no} — {a.institution.name if a.institution else 'N/A'}": a for a in apps}
        selected_label = st.selectbox("Select Target Application for Dossier Generation:", list(app_options.keys()))
        app = app_options[selected_label]

        st.markdown("---")
        st.markdown("### 🖨️ Generate Statutory Compliance Dossier")
        st.markdown("""
        The generated PDF includes:
        - Institution Profile & Application Metadata
        - Document Inventory, SHA-256 Hashes & Version History
        - Tampering Indicator Diagnostic Scores & ELA Findings
        - Certificate Verification Outcomes (Mock Registry / Authoritative API)
        - AICTE APH 2024–27 Clause-by-Clause Compliance Table
        - Scrutiny Officer Notes & Institutional Clarification History
        - Cryptographic File Checksum & Legal Decision-Support Disclaimers
        """)

        if st.button("Generate Official Scrutiny PDF Report", type="primary"):
            with st.spinner("Compiling regulatory evidence and generating PDF..."):
                pdf_path = generate_application_pdf_report(app.id, user)
                st.success(f"Report successfully compiled at: `{pdf_path}`")

                # Provide direct download
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()

                st.download_button(
                    label="⬇️ Download Generated Dossier (PDF)",
                    data=pdf_bytes,
                    file_name=Path(pdf_path).name,
                    mime="application/pdf",
                    key="download_latest_report"
                )

        # Historical Generated Reports
        st.markdown("---")
        st.markdown("### 🗄️ Historical Dossier Archives")
        reports = db.query(GeneratedReport).filter_by(application_id=app.id).order_by(GeneratedReport.created_at.desc()).all()

        if not reports:
            st.info("No prior dossiers generated for this application.")
        else:
            for rep in reports:
                col_r1, col_r2 = st.columns([3, 1])
                with col_r1:
                    st.markdown(f"**Dossier #{rep.id}** — `{Path(rep.file_path).name}`")
                    st.caption(f"Generated: {rep.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')} | Checksum: `{rep.file_hash[:16]}...`")
                with col_r2:
                    if Path(rep.file_path).exists():
                        with open(rep.file_path, "rb") as f:
                            r_bytes = f.read()
                        st.download_button(
                            "⬇️ Download",
                            data=r_bytes,
                            file_name=Path(rep.file_path).name,
                            mime="application/pdf",
                            key=f"dl_rep_{rep.id}"
                        )
                    else:
                        st.caption("File moved")

    finally:
        db.close()
