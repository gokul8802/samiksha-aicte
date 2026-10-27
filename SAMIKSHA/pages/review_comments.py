"""
Review Comments, Deficiency Ticketing & Clarification System for Samiksha
Manages two-way communication between Scrutiny Officers, Committee Members, and Applicants.
"""

import streamlit as st
from datetime import datetime, timezone
from modules.database import get_db_session, Application, ReviewComment
from modules.permissions import can_user, Permissions
from modules.audit_logger import log_audit_event
from config.settings import Roles


def render_review_comments(user):
    st.markdown("## 💬 Scrutiny Notes & Clarification Workspace")
    st.markdown(
        "*Formal review observations, deficiency clarification tickets, and institutional responses.*"
    )

    db = get_db_session()
    try:
        if user.role == Roles.APPLICANT and user.institution_id:
            apps = db.query(Application).filter(Application.institution_id == user.institution_id).all()
        else:
            apps = db.query(Application).all()

        if not apps:
            st.info("No applications available.")
            return

        app_options = {f"{a.application_no} — {a.institution.name if a.institution else 'N/A'}": a for a in apps}
        selected_label = st.selectbox("Select Application:", list(app_options.keys()))
        app = app_options[selected_label]

        # Display comments history
        st.markdown(f"### 📋 Communication Log for Application **{app.application_no}**")
        comments = db.query(ReviewComment).filter_by(application_id=app.id).order_by(ReviewComment.created_at.asc()).all()

        if not comments:
            st.info("No scrutiny notes or clarification requests recorded yet for this application.")
        else:
            for c in comments:
                is_clarification = c.is_clarification_request
                badge_type = "🚨 Clarification Request" if is_clarification else "📝 Scrutiny Observation"
                box_color = "#fef2f2" if is_clarification else "#f8fafc"

                with st.container():
                    st.markdown(f"""
                    <div style="background:{box_color}; border:1px solid #cbd5e1; border-radius:8px; padding:12px; margin-bottom:12px; color:#0f172a;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                            <strong>{badge_type}</strong>
                            <span style="font-size:12px; color:#64748b;">{c.created_at.strftime('%Y-%m-%d %H:%M UTC') if c.created_at else ''}</span>
                        </div>
                        <p style="margin:0 0 8px 0;">{c.comment_text}</p>
                        <div style="font-size:12px; color:#475569;">By: <em>{c.user_role}</em></div>
                    </div>
                    """, unsafe_allow_html=True)

                    # If clarification request and user is applicant, show response form
                    if is_clarification:
                        if c.applicant_response:
                            st.success(f"**Institutional Response:** {c.applicant_response}")
                        elif user.role == Roles.APPLICANT:
                            with st.form(f"resp_form_{c.id}"):
                                resp_text = st.text_area("Provide Institutional Clarification / Upload Reference:")
                                if st.form_submit_button("Submit Formal Response", type="primary"):
                                    c.applicant_response = resp_text
                                    c.resolved_at = datetime.now(timezone.utc)
                                    db.commit()
                                    log_audit_event(
                                        actor_id=user.id,
                                        actor_username=user.username,
                                        actor_role=user.role,
                                        action="CLARIFICATION_RESPONDED",
                                        target_type="REVIEW_COMMENT",
                                        target_id=str(c.id),
                                        details={"response": resp_text},
                                        db_session=db,
                                    )
                                    st.success("Clarification submitted to Scrutiny Committee.")
                                    st.rerun()

        # Officer Add Observation Form
        st.markdown("---")
        if user.role != Roles.APPLICANT:
            st.markdown("### ✍️ Record Scrutiny Note or Request Institutional Clarification")
            with st.form("new_comment_form"):
                comment_type = st.radio("Entry Classification:", ["Scrutiny Observation / Note", "Formal Clarification Request (Requires Applicant Response)"])
                comm_text = st.text_area("Observation Details / Regulatory Query:")
                submit_note = st.form_submit_button("Post Entry to Application Dossier", type="primary")

                if submit_note and comm_text:
                    is_clar = "Clarification" in comment_type
                    new_comm = ReviewComment(
                        application_id=app.id,
                        user_id=user.id,
                        user_role=user.role,
                        comment_type="CLARIFICATION_REQUEST" if is_clar else "SCRUTINY_OBSERVATION",
                        comment_text=comm_text,
                        is_clarification_request=is_clar,
                    )
                    db.add(new_comm)
                    if is_clar:
                        app.status = "CLARIFICATION_REQUESTED"
                    db.commit()

                    log_audit_event(
                        actor_id=user.id,
                        actor_username=user.username,
                        actor_role=user.role,
                        action="SCRUTINY_NOTE_ADDED",
                        target_type="APPLICATION",
                        target_id=app.application_no,
                        details={"is_clarification": is_clar, "text": comm_text[:50]},
                        db_session=db,
                    )
                    st.success("Scrutiny record saved.")
                    st.rerun()

    finally:
        db.close()
