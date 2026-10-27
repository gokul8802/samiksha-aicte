"""
Application Management Page for Samiksha
Handles creation, listing, searching, details viewing, and workflow transitions.
Strict tenant isolation enforced: Applicants only view their own institution's data.
"""

import streamlit as st
from datetime import datetime, timezone
import json
from modules.database import get_db_session, Application, Institution, Document, User, ApplicationVersion
from modules.permissions import can_user, can_access_application, enforce_application_access, PermissionDeniedError
from modules.audit_logger import log_audit_event
from config.settings import Roles, Permissions, APPLICATION_CATEGORIES


def render_applications(user):
    st.markdown("## 📁 Institutional Application Management")
    st.markdown("*Create, track, and inspect institutional applications under AICTE Approval Process Handbook.*")

    db = get_db_session()
    try:
        # Determine accessible applications based on role
        if user.role == Roles.APPLICANT:
            if not user.institution_id:
                st.warning("Your user profile is not linked to an institution. Please contact administrator.")
                return
            apps = db.query(Application).filter(Application.institution_id == user.institution_id).all()
            st.info(f"Viewing applications for: **{user.institution.name}** (AICTE ID: `{user.institution.aicte_id}`)")
        else:
            apps = db.query(Application).all()

        tabs = st.tabs(["📋 Applications List", "➕ Create New Application"])

        # Tab 1: Application List & Inspector
        with tabs[0]:
            # Filter bar
            c1, c2 = st.columns([3, 1])
            with c1:
                search_query = st.text_input("🔍 Search by Application No or Institution Name:", placeholder="e.g. AICTE-2025 or Apex")
            with c2:
                status_filter = st.selectbox("Status Filter:", ["ALL", "DRAFT", "SUBMITTED", "UNDER_SCRUTINY", "APPROVED", "REJECTED"])

            filtered_apps = apps
            if search_query:
                q = search_query.lower()
                filtered_apps = [a for a in filtered_apps if q in a.application_no.lower() or (a.institution and q in a.institution.name.lower())]
            if status_filter != "ALL":
                filtered_apps = [a for a in filtered_apps if a.status == status_filter]

            if not filtered_apps:
                st.info("No matching applications found.")
            else:
                for app in filtered_apps:
                    with st.expander(f"🏛️ **{app.application_no}** — {app.institution.name if app.institution else 'N/A'} [{app.status}]", expanded=False):
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.markdown(f"**Category:** {app.category}")
                            st.markdown(f"**Program:** {app.program}")
                            st.markdown(f"**Academic Year:** {app.academic_year}")
                        with col_b:
                            st.markdown(f"**Approved Intake:** {app.approved_intake} seats")
                            st.markdown(f"**Total Land:** {app.total_land_acres} Acres")
                            st.markdown(f"**Built-up Area:** {app.built_up_area_sqm} sq.m")
                        with col_c:
                            st.markdown(f"**Current Stage:** `{app.current_stage}`")
                            st.markdown(f"**Version:** v{app.version}")
                            st.markdown(f"**Submitted:** {app.submission_date.strftime('%Y-%m-%d %H:%M') if app.submission_date else 'Draft'}")

                        st.markdown("---")
                        docs_count = len(app.documents)
                        st.markdown(f"**Documents Uploaded:** {docs_count} files")
                        if app.documents:
                            doc_items = [f"- `{d.document_type}`: {d.filename} ({d.file_size / 1024:.1f} KB) [Hash: `{d.sha256_hash[:10]}...`]" for d in app.documents]
                            st.markdown("\n".join(doc_items))

                        # Officer status change actions
                        if can_user(user, Permissions.CHANGE_APP_STATUS):
                            st.markdown("#### ⚡ Workflow Actions (Officer Only)")
                            new_status = st.selectbox(
                                "Change Application Stage / Status:",
                                ["SUBMITTED", "UNDER_SCRUTINY", "CLARIFICATION_REQUESTED", "COMMITTEE_REVIEW", "APPROVED", "REJECTED"],
                                index=0,
                                key=f"status_select_{app.id}"
                            )
                            new_stage = st.text_input("Stage Description:", value=app.current_stage, key=f"stage_desc_{app.id}")
                            if st.button("Update Status", key=f"btn_upd_{app.id}"):
                                app.status = new_status
                                app.current_stage = new_stage
                                app.version += 1
                                db.commit()
                                log_audit_event(
                                    actor_id=user.id,
                                    actor_username=user.username,
                                    actor_role=user.role,
                                    action="APPLICATION_STATUS_UPDATED",
                                    target_type="APPLICATION",
                                    target_id=app.application_no,
                                    details={"new_status": new_status, "new_stage": new_stage, "version": app.version},
                                    db_session=db,
                                )
                                st.success("Application status updated successfully.")
                                st.rerun()

        # Tab 2: Create Application
        with tabs[1]:
            if not can_user(user, Permissions.CREATE_APPLICATION):
                st.warning("Only Institution Applicants can create new institutional applications.")
            else:
                st.markdown("### 📝 New AICTE Approval Application Form")
                with st.form("create_application_form"):
                    f_inst = user.institution.name if user.institution else "Demo Institution"
                    st.text_input("Institution:", value=f_inst, disabled=True)
                    
                    f_cat = st.selectbox("Application Category (per APH 2024-27):", APPLICATION_CATEGORIES)
                    f_prog = st.selectbox("Programme:", [
                        "Engineering & Technology",
                        "Management (MBA/PGDM)",
                        "Computer Applications (MCA/BCA)",
                        "Planning & Architecture",
                        "Design & Applied Arts"
                    ])
                    f_year = st.selectbox("Academic Year:", ["2025-26", "2026-27"])

                    c_in1, c_in2, c_in3 = st.columns(3)
                    with c_in1:
                        f_intake = st.number_input("Proposed Intake (Seats):", min_value=30, max_value=2400, value=360, step=30)
                    with c_in2:
                        f_land = st.number_input("Total Land Area (Acres):", min_value=0.5, max_value=100.0, value=5.0, step=0.5)
                    with c_in3:
                        f_bld = st.number_input("Built-up Area (Sq. Meters):", min_value=100.0, max_value=50000.0, value=4500.0, step=100.0)

                    submitted = st.form_submit_button("Submit Application for Processing", type="primary")
                    if submitted:
                        app_count = db.query(Application).count() + 1
                        new_app_no = f"AICTE-2025-APP-{app_count:04d}"
                        new_app = Application(
                            application_no=new_app_no,
                            institution_id=user.institution_id,
                            academic_year=f_year,
                            category=f_cat,
                            program=f_prog,
                            status="SUBMITTED",
                            current_stage="Scrutiny Intake",
                            approved_intake=f_intake,
                            total_land_acres=f_land,
                            built_up_area_sqm=f_bld,
                            submission_date=datetime.now(timezone.utc),
                            created_by=user.id,
                            version=1,
                        )
                        db.add(new_app)
                        db.commit()

                        log_audit_event(
                            actor_id=user.id,
                            actor_username=user.username,
                            actor_role=user.role,
                            action="APPLICATION_CREATED",
                            target_type="APPLICATION",
                            target_id=new_app_no,
                            details={"category": f_cat, "program": f_prog, "intake": f_intake},
                            db_session=db,
                        )
                        st.success(f"Application **{new_app_no}** created and submitted for scrutiny!")
                        st.rerun()

    finally:
        db.close()
