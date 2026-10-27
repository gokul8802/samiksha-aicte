"""
Samiksha — AICTE Institutional Validation Platform
SIH 2026 Problem Statement 26261 | Regulation Bureau
Main Streamlit Application Entrypoint & Navigation Router
"""

import streamlit as st
from config.settings import APP_NAME, APP_SUBTITLE, AICTE_BUREAU, SIH_PROBLEM_ID, Roles, Permissions
from modules.database import init_db, get_db_session, User
from modules.auth import (
    is_authenticated, get_current_user, set_user_session,
    clear_user_session, switch_demo_user, get_demo_accounts
)
from modules.permissions import can_user

# Streamlit Page Config
st.set_page_config(
    page_title=f"{APP_NAME} | AICTE Validation",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling & Modern Glassmorphism Theme
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Top Header Bar */
    .top-navbar {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border-bottom: 2px solid #0284c7;
        padding: 12px 24px;
        border-radius: 8px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: #f8fafc;
    }
    .top-title {
        font-size: 20px;
        font-weight: 700;
        letter-spacing: 0.5px;
        color: #38bdf8;
    }
    .top-badge {
        background: rgba(2, 132, 199, 0.2);
        border: 1px solid #0284c7;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        color: #7dd3fc;
    }
    
    /* Metric Cards */
    .metric-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: #0284c7;
    }
    .metric-label {
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        color: #94a3b8;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 26px;
        font-weight: 700;
        color: #f8fafc;
        margin-top: 4px;
    }
    
    /* Status Pills */
    .status-pill {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 600;
    }
    .status-compliant { background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); }
    .status-noncompliant { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .status-pending { background: rgba(234, 179, 8, 0.15); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.3); }
    .status-info { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #0f172a;
        border-right: 1px solid #1e293b;
    }
</style>
""", unsafe_allow_html=True)


def init_app():
    """Ensure database is ready and set default demo session if unset."""
    init_db(seed_data=True)
    if "is_authenticated" not in st.session_state:
        # Default to Scrutiny Officer for first demo view
        switch_demo_user("scrutiny_sharma")


init_app()
user = get_current_user()

# Top Header Bar
st.markdown(f"""
<div class="top-navbar">
    <div>
        <span class="top-title">🏛️ {APP_NAME}</span>
        <span style="margin-left: 10px; color: #94a3b8; font-size: 13px;">| {AICTE_BUREAU}</span>
    </div>
    <div>
        <span class="top-badge">SIH 2026 #{SIH_PROBLEM_ID}</span>
        <span class="top-badge" style="margin-left: 6px; background: rgba(16, 185, 129, 0.15); border-color: #10b981; color: #6ee7b7;">APH 2024-27 Verified</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar: User Profile & Demo Switcher
with st.sidebar:
    st.markdown("### 👤 Active Identity")
    if user:
        st.markdown(f"**{user.full_name}**")
        st.markdown(f"<span class='status-pill status-info'>{Roles.LABELS.get(user.role, user.role)}</span>", unsafe_allow_html=True)
        inst = getattr(user, "institution", None)
        if inst:
            st.caption(f"🏛️ {inst.name}")
    else:
        st.warning("Not Signed In")

    st.markdown("---")
    st.markdown("#### ⚡ 1-Click Role Switcher *(SIH Demo)*")
    demo_accounts = get_demo_accounts()
    current_idx = 0
    for idx, acc in enumerate(demo_accounts):
        if user and acc["username"] == user.username:
            current_idx = idx
            break

    selected_account = st.selectbox(
        "Switch User Perspective:",
        options=demo_accounts,
        index=current_idx,
        format_func=lambda x: f"{x['label']}",
        key="demo_role_selector",
    )

    if user and selected_account["username"] != user.username:
        if st.button("Apply Role Switch", use_container_width=True, type="primary"):
            switch_demo_user(selected_account["username"])
            st.rerun()

    st.markdown("---")
    st.markdown("### 📋 Navigation")

    # Define Navigation Pages and Permissions
    pages_menu = [
        {"name": "📊 Dashboard", "key": "dashboard", "perm": None},
        {"name": "📁 Applications", "key": "applications", "perm": None},
        {"name": "📤 Document Upload", "key": "document_upload", "perm": Permissions.UPLOAD_DOCUMENT},
        {"name": "🔍 Document Integrity (AI)", "key": "document_integrity", "perm": Permissions.RUN_TAMPERING_ANALYSIS},
        {"name": "🛡️ Certificate Gateway", "key": "certificate_verification", "perm": Permissions.RUN_CERTIFICATE_VERIFY},
        {"name": "👥 Resource Intelligence", "key": "resource_intelligence", "perm": Permissions.RUN_RESOURCE_INTELLIGENCE},
        {"name": "📜 APH Compliance Review", "key": "compliance_review", "perm": Permissions.RUN_COMPLIANCE_EVAL},
        {"name": "🗺️ Institution ChangeMap", "key": "institution_changemap", "perm": None},
        {"name": "🔄 Rule-Change Replay", "key": "rule_change_replay", "perm": Permissions.RUN_RULE_REPLAY},
        {"name": "⚙️ Rule Management", "key": "rule_management", "perm": Permissions.PROPOSE_RULE},
        {"name": "💬 Scrutiny & Comments", "key": "review_comments", "perm": None},
        {"name": "📄 Reports & Dossiers", "key": "reports", "perm": Permissions.DOWNLOAD_REPORT},
        {"name": "🔒 Immutable Audit Logs", "key": "audit_logs", "perm": Permissions.VIEW_AUDIT_LOGS},
        {"name": "🖥️ System & Model Status", "key": "system_status", "perm": None},
    ]

    # Filter pages based on user role permissions
    visible_pages = []
    for p in pages_menu:
        if p["perm"] is None or can_user(user, p["perm"]):
            visible_pages.append(p)

    selected_page_name = st.radio(
        "Go to page:",
        options=[p["name"] for p in visible_pages],
        label_visibility="collapsed",
    )

    selected_page_key = next(p["key"] for p in visible_pages if p["name"] == selected_page_name)

    st.markdown("---")
    if st.button("🚪 Sign Out", use_container_width=True):
        clear_user_session()
        st.rerun()

    st.caption("Samiksha v1.0.0 • SIH 2026 Prototype")

# Route to Page Implementation
if selected_page_key == "dashboard":
    from pages.dashboard import render_dashboard
    render_dashboard(user)
elif selected_page_key == "applications":
    from pages.applications import render_applications
    render_applications(user)
elif selected_page_key == "document_upload":
    from pages.document_upload import render_document_upload
    render_document_upload(user)
elif selected_page_key == "document_integrity":
    from pages.document_integrity import render_document_integrity
    render_document_integrity(user)
elif selected_page_key == "certificate_verification":
    from pages.certificate_verification import render_certificate_verification
    render_certificate_verification(user)
elif selected_page_key == "resource_intelligence":
    from pages.resource_intelligence import render_resource_intelligence
    render_resource_intelligence(user)
elif selected_page_key == "compliance_review":
    from pages.compliance_review import render_compliance_review
    render_compliance_review(user)
elif selected_page_key == "institution_changemap":
    from pages.institution_changemap import render_institution_changemap
    render_institution_changemap(user)
elif selected_page_key == "rule_change_replay":
    from pages.rule_change_replay import render_rule_change_replay
    render_rule_change_replay(user)
elif selected_page_key == "rule_management":
    from pages.rule_management import render_rule_management
    render_rule_management(user)
elif selected_page_key == "review_comments":
    from pages.review_comments import render_review_comments
    render_review_comments(user)
elif selected_page_key == "reports":
    from pages.reports import render_reports
    render_reports(user)
elif selected_page_key == "audit_logs":
    from pages.audit_logs import render_audit_logs
    render_audit_logs(user)
elif selected_page_key == "system_status":
    from pages.system_status import render_system_status
    render_system_status(user)
