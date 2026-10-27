"""
Officer-Controlled Rule Management Workspace for Samiksha
Allows authorized officers to propose, review, approve, and publish versioned regulatory rules.
Enforces strict separation of duties: Author cannot approve their own rule proposal.
"""

import streamlit as st
from datetime import datetime, timezone
import json
from modules.database import get_db_session, RegulatoryRule
from modules.permissions import (
    can_user, can_approve_rule, enforce_rule_approval, Permissions, PermissionDeniedError
)
from modules.audit_logger import log_audit_event
from config.settings import APH_DEFAULT_EDITION


def render_rule_management(user):
    st.markdown("## ⚙️ Officer Rule Management Workspace")
    st.markdown(
        "*Controlled regulatory configuration: propose, inspect, approve, and publish versioned AICTE rules.*"
    )

    if not can_user(user, Permissions.PROPOSE_RULE):
        st.error("Access Denied: You do not possess the `propose_rule` permission.")
        return

    db = get_db_session()
    try:
        tabs = st.tabs(["📚 Active Published Rules", "📝 Propose New Rule / Amendment", "⚖️ Pending Approvals (Separation of Duties)"])

        # Tab 1: Published Rules
        with tabs[0]:
            published_rules = db.query(RegulatoryRule).filter_by(status="PUBLISHED").all()
            st.markdown(f"### Published Rules in Force ({len(published_rules)} rules)")
            for r in published_rules:
                with st.expander(f"📜 **{r.rule_id}** (v{r.version}): {r.title}", expanded=False):
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        st.markdown(f"**Category:** {r.category}")
                        st.markdown(f"**Source Clause:** `{r.clause_reference}`")
                        st.markdown(f"**Source Page:** `{r.page_reference}`")
                        st.markdown(f"**Handbook Edition:** `{r.aph_edition}`")
                    with c2:
                        st.markdown(f"**Verified Grounding:** `{'✅ VERIFIED' if r.is_verified else 'DEMO SYNTHETIC'}`")
                        st.markdown(f"**Effective Dates:** `{r.effective_from}` to `{r.effective_to}`")
                    st.markdown(f"**Official Source Excerpt:**\n> *\"{r.source_excerpt}\"*")
                    st.markdown(f"**Description:** {r.description}")
                    st.markdown("**Structured Evaluation DSL:**")
                    st.json(json.loads(r.evaluation_logic_json))

        # Tab 2: Propose Rule
        with tabs[1]:
            st.markdown("### 📝 Draft New Regulatory Rule Proposal")
            with st.form("propose_rule_form"):
                f_id = st.text_input("Rule Identifier:", placeholder="e.g. RULE-APH24-SOLAR-01")
                f_title = st.text_input("Rule Title:", placeholder="e.g. Mandatory Renewable Energy & Solar Generation Norm")
                f_category = st.selectbox("Category:", ["Infrastructure", "Safety", "Faculty", "IT Infrastructure", "Library", "Governance"])
                f_clause = st.text_input("Exact APH Clause Reference:", placeholder="e.g. Chapter VI Clause 6.2.e")
                f_page = st.text_input("Page Reference in Official PDF:", placeholder="e.g. Book p. 53 (PDF p. 69)")
                f_excerpt = st.text_area("Faithful Excerpt from Official Handbook:", placeholder="Paste exact text from official PDF without modification...")
                f_desc = st.text_area("Operational Rule Description & Enforcement Criterion:")

                c_d1, c_d2 = st.columns(2)
                with c_d1:
                    f_from = st.date_input("Effective From Date:")
                with c_d2:
                    f_to = st.date_input("Effective Until Date:")

                submitted = st.form_submit_button("Submit Proposed Rule for Review", type="primary")
                if submitted:
                    if not f_id or not f_title or not f_clause or not f_excerpt:
                        st.error("Please fill in all mandatory regulatory fields and official source excerpts.")
                    else:
                        new_rule = RegulatoryRule(
                            rule_id=f_id,
                            version="1.0.0-DRAFT",
                            title=f_title,
                            description=f_desc,
                            aph_edition=APH_DEFAULT_EDITION,
                            clause_reference=f_clause,
                            page_reference=f_page,
                            source_excerpt=f_excerpt,
                            category=f_category,
                            evaluation_logic_json=json.dumps({"type": "custom_dsl", "field": f_id}),
                            required_evidence_json=json.dumps(["Supporting Inspection Verification"]),
                            effective_from=f_from.strftime("%Y-%m-%d"),
                            effective_to=f_to.strftime("%Y-%m-%d"),
                            status="PENDING_APPROVAL",
                            is_verified=True,
                            created_by=user.id,
                        )
                        db.add(new_rule)
                        db.commit()

                        log_audit_event(
                            actor_id=user.id,
                            actor_username=user.username,
                            actor_role=user.role,
                            action="REGULATORY_RULE_PROPOSED",
                            target_type="REGULATORY_RULE",
                            target_id=f_id,
                            details={"title": f_title, "clause": f_clause},
                            db_session=db,
                        )
                        st.success(f"Rule proposal **{f_id}** submitted! Awaiting independent reviewer approval.")
                        st.rerun()

        # Tab 3: Pending Approvals & Separation of Duties
        with tabs[2]:
            st.markdown("### ⚖️ Pending Approval Review Queue")
            st.info("ℹ️ **Separation of Duties Policy:** The author who drafted a proposed rule cannot approve or publish it.")

            drafts = db.query(RegulatoryRule).filter_by(status="PENDING_APPROVAL").all()
            if not drafts:
                st.info("No rule proposals currently awaiting review.")
            else:
                for d in drafts:
                    with st.expander(f"⏳ **{d.rule_id}**: {d.title} (Proposed by User #{d.created_by})", expanded=True):
                        st.markdown(f"**Clause:** `{d.clause_reference}` | **Page:** `{d.page_reference}`")
                        st.markdown(f"**Source Excerpt:** *\"{d.source_excerpt}\"*")
                        st.markdown(f"**Proposed by Actor ID:** `{d.created_by}` (Current Actor: `{user.id}`)")

                        is_author = (d.created_by == user.id)
                        if is_author:
                            st.warning("⚠️ **Separation of Duties Alert:** You are the author of this proposal. You cannot approve your own rule.")

                        c_btn1, c_btn2 = st.columns(2)
                        with c_btn1:
                            if st.button("✅ Approve & Publish Rule", key=f"apprv_{d.id}", disabled=is_author, type="primary"):
                                try:
                                    enforce_rule_approval(user, d, db)
                                    d.status = "PUBLISHED"
                                    d.approved_by = user.id
                                    d.version = "1.0.0"
                                    db.commit()
                                    log_audit_event(
                                        actor_id=user.id,
                                        actor_username=user.username,
                                        actor_role=user.role,
                                        action="REGULATORY_RULE_PUBLISHED",
                                        target_type="REGULATORY_RULE",
                                        target_id=d.rule_id,
                                        details={"approved_by": user.id},
                                        db_session=db,
                                    )
                                    st.success(f"Rule **{d.rule_id}** published successfully!")
                                    st.rerun()
                                except PermissionDeniedError as e:
                                    st.error(f"Approval Blocked: {e.message}")

                        with c_btn2:
                            if st.button("❌ Reject Proposal", key=f"rej_{d.id}"):
                                d.status = "WITHDRAWN"
                                db.commit()
                                log_audit_event(
                                    actor_id=user.id,
                                    actor_username=user.username,
                                    actor_role=user.role,
                                    action="REGULATORY_RULE_REJECTED",
                                    target_type="REGULATORY_RULE",
                                    target_id=d.rule_id,
                                    db_session=db,
                                )
                                st.warning("Rule proposal rejected and withdrawn.")
                                st.rerun()

    finally:
        db.close()
