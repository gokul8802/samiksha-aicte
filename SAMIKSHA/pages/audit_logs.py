"""
Audit Log Viewer Page for Samiksha
Provides an immutable record of authentication, document operations,
regulatory rule proposals/approvals, and security incidents.
"""

import streamlit as st
import json
from modules.database import get_db_session, AuditEvent
from modules.permissions import can_user, Permissions


def render_audit_logs(user):
    st.markdown("## 🔒 Immutable System Audit Logs")
    st.markdown(
        "*Complete, tamper-evident audit trail of system activities, compliance evaluations, and security alerts.*"
    )

    if not can_user(user, Permissions.VIEW_AUDIT_LOGS):
        st.error("Access Denied: You do not possess the `view_audit_logs` permission.")
        return

    db = get_db_session()
    try:
        # Filter options
        c1, c2 = st.columns([2, 1])
        with c1:
            action_filter = st.selectbox(
                "Filter by Action:",
                ["ALL", "LOGIN_SUCCESS", "LOGOUT", "UNAUTHORIZED_ACCESS_ATTEMPT", "TENANT_ISOLATION_BREACH_ATTEMPT",
                 "SEPARATION_OF_DUTIES_VIOLATION", "APPLICATION_CREATED", "APPLICATION_STATUS_UPDATED",
                 "COMPLIANCE_EVALUATION_RUN", "RULE_PROPOSED", "RULE_PUBLISHED", "REPORT_GENERATED"]
            )
        with c2:
            limit_val = st.number_input("Max Events to Display:", min_value=10, max_value=500, value=50, step=10)

        query = db.query(AuditEvent).order_by(AuditEvent.created_at.desc())
        if action_filter != "ALL":
            query = query.filter(AuditEvent.action == action_filter)

        events = query.limit(limit_val).all()

        if not events:
            st.info("No audit events recorded under this filter.")
        else:
            event_rows = []
            for ev in events:
                is_security_alert = "ATTEMPT" in ev.action or "VIOLATION" in ev.action
                action_display = f"🚨 {ev.action}" if is_security_alert else ev.action
                event_rows.append({
                    "Timestamp (UTC)": ev.created_at.strftime("%Y-%m-%d %H:%M:%S") if ev.created_at else "N/A",
                    "Actor": f"{ev.actor_username} ({ev.actor_role})",
                    "Action": action_display,
                    "Target Type": ev.target_type or "-",
                    "Target ID": ev.target_id or "-",
                    "IP Address": ev.ip_address,
                    "Details": ev.details_json[:80] + "..." if ev.details_json and len(ev.details_json) > 80 else ev.details_json,
                })

            st.dataframe(event_rows, use_container_width=True)

            # Details expander for inspected event
            st.markdown("---")
            st.markdown("#### 🔍 Inspect Event Payload")
            selected_idx = st.selectbox("Select event row by index:", range(len(events)), format_func=lambda i: f"#{events[i].id} | {events[i].action} by {events[i].actor_username}")
            if selected_idx is not None:
                ev = events[selected_idx]
                st.json({
                    "id": ev.id,
                    "actor_id": ev.actor_id,
                    "actor_username": ev.actor_username,
                    "actor_role": ev.actor_role,
                    "action": ev.action,
                    "target_type": ev.target_type,
                    "target_id": ev.target_id,
                    "ip_address": ev.ip_address,
                    "created_at": ev.created_at.isoformat() if ev.created_at else None,
                    "details": json.loads(ev.details_json) if ev.details_json else None,
                })

    finally:
        db.close()
