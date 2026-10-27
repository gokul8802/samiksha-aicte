"""
Cross-Application Resource Intelligence for Samiksha
Detects potential duplicate claims or conflicting resource allocations
(Faculty, Land Parcels, Facilities) across multiple institutional applications.
"""

import streamlit as st
from rapidfuzz import fuzz
from modules.database import get_db_session, Application, ResourceClaim, ResourceConflict
from modules.permissions import can_user, Permissions
from modules.audit_logger import log_audit_event


def render_resource_intelligence(user):
    st.markdown("## 👥 Cross-Application Resource Intelligence")
    st.markdown(
        "*Detection of potential duplicate or conflicting resource claims across institutional applications.*"
    )

    if not can_user(user, Permissions.RUN_RESOURCE_INTELLIGENCE):
        st.error("Access Denied: You do not possess the `run_resource_intelligence` permission.")
        return

    st.info("""
    ℹ️ **Decision Support Notice:**  
    An entity or faculty match across two applications is **not automatic proof of fraud**. 
    Legitimate shared arrangements or transition notices may exist under AICTE guidelines. 
    Reviewers must verify supporting documents before taking regulatory action.
    """)

    db = get_db_session()
    try:
        # Seed demo claims if none exist
        if db.query(ResourceClaim).count() == 0:
            apps = db.query(Application).all()
            if len(apps) >= 2:
                # Same faculty claimed by both institutions
                c1 = ResourceClaim(
                    application_id=apps[0].id,
                    resource_type="FACULTY",
                    entity_identifier="PAN-ABCDE1234F",
                    entity_name="Dr. Ramanathan Sundaram",
                    details_json='{"designation": "Professor & HOD", "department": "Computer Science & Engineering"}',
                )
                c2 = ResourceClaim(
                    application_id=apps[1].id,
                    resource_type="FACULTY",
                    entity_identifier="PAN-ABCDE1234F", # Identical PAN
                    entity_name="Dr. R. Sundaram", # Fuzzy name
                    details_json='{"designation": "Professor", "department": "Information Technology"}',
                )
                # Same land parcel / survey number
                c3 = ResourceClaim(
                    application_id=apps[0].id,
                    resource_type="LAND_PARCEL",
                    entity_identifier="SURVEY-NO-45/2A",
                    entity_name="Plot 12, Phase 1",
                    details_json='{"area_acres": 3.5, "tehsil": "Dadri"}',
                )
                db.add_all([c1, c2, c3])
                db.commit()

        # Action: Run Cross-Application Conflict Scan
        if st.button("🚀 Run Cross-Application Conflict Scanner", type="primary"):
            claims = db.query(ResourceClaim).all()
            conflicts_found = 0

            for i in range(len(claims)):
                for j in range(i + 1, len(claims)):
                    c_a, c_b = claims[i], claims[j]
                    if c_a.application_id == c_b.application_id:
                        continue # Same application

                    # 1. Exact Identifier Match (PAN, Survey No, Machine Serial)
                    if c_a.entity_identifier.lower().strip() == c_b.entity_identifier.lower().strip():
                        # Conflict detected!
                        explanation = (
                            f"Exact Identifier Match on {c_a.resource_type}: Identifier '{c_a.entity_identifier}' "
                            f"claimed by Application #{c_a.application_id} as '{c_a.entity_name}' "
                            f"and Application #{c_b.application_id} as '{c_b.entity_name}'."
                        )

                        # Check if conflict already logged
                        existing = db.query(ResourceConflict).filter(
                            ((ResourceConflict.primary_claim_id == c_a.id) & (ResourceConflict.conflicting_claim_id == c_b.id)) |
                            ((ResourceConflict.primary_claim_id == c_b.id) & (ResourceConflict.conflicting_claim_id == c_a.id))
                        ).first()

                        if not existing:
                            conflict = ResourceConflict(
                                primary_claim_id=c_a.id,
                                conflicting_claim_id=c_b.id,
                                primary_app_id=c_a.application_id,
                                conflicting_app_id=c_b.application_id,
                                resource_type=c_a.resource_type,
                                match_score=100.0,
                                match_method="EXACT_IDENTIFIER_MATCH",
                                explanation=explanation,
                                status="UNREVIEWED",
                            )
                            db.add(conflict)
                            conflicts_found += 1

                    # 2. Fuzzy Name Match
                    else:
                        similarity = fuzz.token_sort_ratio(c_a.entity_name.lower(), c_b.entity_name.lower())
                        if similarity > 88.0 and c_a.resource_type == c_b.resource_type:
                            explanation = (
                                f"Fuzzy Name Match ({similarity:.1f}%) on {c_a.resource_type}: '{c_a.entity_name}' "
                                f"(App #{c_a.application_id}) vs '{c_b.entity_name}' (App #{c_b.application_id})."
                            )
                            existing = db.query(ResourceConflict).filter(
                                ((ResourceConflict.primary_claim_id == c_a.id) & (ResourceConflict.conflicting_claim_id == c_b.id)) |
                                ((ResourceConflict.primary_claim_id == c_b.id) & (ResourceConflict.conflicting_claim_id == c_a.id))
                            ).first()
                            if not existing:
                                conflict = ResourceConflict(
                                    primary_claim_id=c_a.id,
                                    conflicting_claim_id=c_b.id,
                                    primary_app_id=c_a.application_id,
                                    conflicting_app_id=c_b.application_id,
                                    resource_type=c_a.resource_type,
                                    match_score=float(similarity),
                                    match_method="FUZZY_NAME_MATCH",
                                    explanation=explanation,
                                    status="UNREVIEWED",
                                )
                                db.add(conflict)
                                conflicts_found += 1

            db.commit()
            log_audit_event(
                actor_id=user.id,
                actor_username=user.username,
                actor_role=user.role,
                action="CROSS_APPLICATION_SCAN_RUN",
                target_type="CONFLICT_ENGINE",
                target_id="ALL",
                details={"new_conflicts_detected": conflicts_found},
                db_session=db,
            )
            st.success(f"Scan complete. {conflicts_found} new potential conflict(s) registered.")
            st.rerun()

        # Display Flagged Conflicts
        st.markdown("---")
        st.markdown("### 🚨 Detected Resource Conflicts Requiring Scrutiny Review")
        conflicts = db.query(ResourceConflict).order_by(ResourceConflict.created_at.desc()).all()

        if not conflicts:
            st.success("No cross-application resource conflicts currently detected.")
        else:
            for conf in conflicts:
                status_color = "red" if conf.status == "UNREVIEWED" else ("orange" if conf.status == "CONFIRMED_CONFLICT" else "green")
                with st.expander(f"⚠️ Conflict #{conf.id}: {conf.resource_type} [{conf.status}] — Score: {conf.match_score:.1f}%", expanded=True):
                    st.markdown(f"**Explanation:** {conf.explanation}")
                    st.markdown(f"**Detection Method:** `{conf.match_method}`")
                    st.markdown(f"**Involved Applications:** App ID #{conf.primary_app_id} ↔ App ID #{conf.conflicting_app_id}")

                    # Reviewer Action
                    c_act1, c_act2 = st.columns(2)
                    with c_act1:
                        new_conf_status = st.selectbox(
                            "Review Outcome:",
                            ["UNREVIEWED", "CONFIRMED_CONFLICT", "DISMISSED_LEGITIMATE"],
                            index=["UNREVIEWED", "CONFIRMED_CONFLICT", "DISMISSED_LEGITIMATE"].index(conf.status),
                            key=f"conf_status_{conf.id}"
                        )
                    with c_act2:
                        notes = st.text_input("Reviewer Justification / Order Reference:", value=conf.review_notes or "", key=f"conf_notes_{conf.id}")

                    if st.button("Save Review Outcome", key=f"save_conf_{conf.id}"):
                        conf.status = new_conf_status
                        conf.reviewed_by = user.id
                        conf.review_notes = notes
                        db.commit()
                        log_audit_event(
                            actor_id=user.id,
                            actor_username=user.username,
                            actor_role=user.role,
                            action="RESOURCE_CONFLICT_REVIEWED",
                            target_type="RESOURCE_CONFLICT",
                            target_id=str(conf.id),
                            details={"new_status": new_conf_status, "notes": notes},
                            db_session=db,
                        )
                        st.success("Conflict review outcome saved.")
                        st.rerun()

    finally:
        db.close()
