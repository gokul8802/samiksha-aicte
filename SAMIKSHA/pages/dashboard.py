"""
Samiksha Executive Dashboard
Computes live institutional scrutiny metrics directly from persisted database records.
"""

import streamlit as st
from modules.database import (
    get_db_session, Application, Document, TamperingRun, Certificate,
    ResourceConflict, RegulatoryRule, AuditEvent, Institution
)
from config.settings import Roles


def render_dashboard(user):
    st.markdown("## 📊 Regulation Bureau Executive Dashboard")
    st.markdown(
        "*Real-time scrutiny status, document authenticity indicators, and regulatory compliance posture.*"
    )

    db = get_db_session()
    try:
        # Base query filtered if applicant
        app_query = db.query(Application)
        if user.role == Roles.APPLICANT and user.institution_id:
            app_query = app_query.filter(Application.institution_id == user.institution_id)

        total_apps = app_query.count()
        under_scrutiny = app_query.filter(Application.status.in_(["SUBMITTED", "UNDER_SCRUTINY"])).count()
        approved_apps = app_query.filter(Application.status == "APPROVED").count()

        # Document and Tampering metrics
        total_docs = db.query(Document).count()
        flagged_docs = db.query(TamperingRun).filter(TamperingRun.is_flagged == True).count()

        # Certificate Verification metrics
        total_certs = db.query(Certificate).count()
        problem_certs = db.query(Certificate).filter(
            Certificate.verification_status.in_(["DETAILS_MISMATCH", "EXPIRED", "REVOKED", "ISSUER_UNAVAILABLE"])
        ).count()

        # Conflicts
        active_conflicts = db.query(ResourceConflict).filter(ResourceConflict.status != "DISMISSED_LEGITIMATE").count()

        # Verified Rules
        total_rules = db.query(RegulatoryRule).filter(RegulatoryRule.status == "PUBLISHED").count()

        # Audit events count
        audit_count = db.query(AuditEvent).count()

        # Metrics Row
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Applications Active</div>
                <div class="metric-value">{total_apps}</div>
                <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">{under_scrutiny} Under Scrutiny</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Documents & Integrity</div>
                <div class="metric-value">{total_docs}</div>
                <div style="font-size: 11px; color: #f87171; margin-top: 4px;">⚠️ {flagged_docs} Tampering Flags</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Certificate Checks</div>
                <div class="metric-value">{total_certs}</div>
                <div style="font-size: 11px; color: #facc15; margin-top: 4px;">⚠️ {problem_certs} Verification Mismatches</div>
            </div>
            """, unsafe_allow_html=True)
        with c4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Cross-App Conflicts</div>
                <div class="metric-value">{active_conflicts}</div>
                <div style="font-size: 11px; color: #38bdf8; margin-top: 4px;">{total_rules} APH Rules Active</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Main Applications Table
        col_main, col_side = st.columns([2, 1])

        with col_main:
            st.markdown("### 📋 Institutional Applications in Pipeline")
            apps = app_query.all()
            if not apps:
                st.info("No applications found in the current scope.")
            else:
                table_data = []
                for a in apps:
                    table_data.append({
                        "App Number": a.application_no,
                        "Institution": a.institution.name if a.institution else "N/A",
                        "Category": a.category,
                        "Program": a.program,
                        "Intake": a.approved_intake,
                        "Stage": a.current_stage,
                        "Status": a.status,
                    })
                st.dataframe(table_data, use_container_width=True)

        with col_side:
            st.markdown("### 🔔 Scrutiny Priority Alerts")
            
            # Show conflict or mismatch warnings
            conflicts = db.query(ResourceConflict).limit(3).all()
            if conflicts:
                for conf in conflicts:
                    st.error(f"**Resource Conflict Detected!**\n\n{conf.explanation}\n\n*Method: {conf.match_method} (Score: {conf.match_score:.1f})*")
            else:
                st.success("No critical cross-application resource overlaps currently flagged.")

            st.markdown("---")
            st.markdown("#### 📜 Regulatory Engine Version")
            st.markdown("**AICTE APH 2024–27** (Standard Norms & Requirements)")
            st.markdown(f"- Verified Rules in Force: **{total_rules}**")
            st.markdown(f"- Audit Trail Events Recorded: **{audit_count}**")

    finally:
        db.close()
