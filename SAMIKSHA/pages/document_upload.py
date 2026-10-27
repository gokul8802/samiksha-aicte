"""
Document Upload & Inventory Management for Samiksha
Handles file upload, mime validation, size constraints, SHA-256 hash preservation,
and versioned storage of supporting application documents.
"""

import streamlit as st
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from modules.database import get_db_session, Application, Document, DocumentVersion
from modules.permissions import can_user, Permissions
from modules.audit_logger import log_audit_event
from config.settings import UPLOADS_DIR, ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB, Roles

DOCUMENT_CATEGORIES = [
    ("FIRE_SAFETY", "Fire & Life Safety Certificate (State Fire Dept)"),
    ("OCCUPANCY_CERT", "Occupancy / Completion Certificate (Local Authority)"),
    ("LAND_TITLE_DEED", "Registered Land Sale Deed / Lease Deed (>=30 yrs)"),
    ("LAND_CONVERSION_CLU", "Land Use Certificate / CLU for Educational Purpose"),
    ("ARCHITECT_CERT_1", "Architect Land Certificate (Certificate 1)"),
    ("ARCHITECT_CERT_2", "Architect Building & Barrier-Free Certificate (Certificate 2)"),
    ("BANK_CERT_3", "Bank Financial Status Certificate (Certificate 3)"),
    ("RESOLUTION_FORMAT_3", "Trust/Society Resolution (Format 3)"),
    ("REGISTRATION_TRUST", "Trust / Society / Section 8 Company Registration & MoA"),
    ("FACULTY_MASTER_LIST", "Certified Faculty Master Register & Joining Orders"),
    ("EQUIPMENT_STOCK_REGISTER", "Computer & Laboratory Hardware Stock Register"),
]


def render_document_upload(user):
    st.markdown("## 📤 Document Upload & Ingestion Gateway")
    st.markdown(
        "*Upload supporting institutional documents for PDF extraction, tampering analysis, and regulatory verification.*"
    )

    if not can_user(user, Permissions.UPLOAD_DOCUMENT):
        st.error("Access Denied: You do not have permission to upload documents.")
        return

    db = get_db_session()
    try:
        # Get accessible applications for upload target
        if user.role == Roles.APPLICANT:
            apps = db.query(Application).filter(Application.institution_id == user.institution_id).all()
        else:
            apps = db.query(Application).all()

        if not apps:
            st.warning("No active application available. Please create an application first.")
            return

        app_options = {f"{a.application_no} ({a.institution.name if a.institution else 'N/A'})": a for a in apps}
        selected_app_label = st.selectbox("Select Target Application:", list(app_options.keys()))
        target_app = app_options[selected_app_label]

        st.markdown("---")
        st.markdown("### 📁 Upload Supporting Document")

        c1, c2 = st.columns([1, 1])
        with c1:
            doc_type_choice = st.selectbox(
                "Document Regulatory Classification:",
                options=DOCUMENT_CATEGORIES,
                format_func=lambda x: f"{x[0]} — {x[1]}"
            )
            doc_type_code = doc_type_choice[0]

        with c2:
            uploaded_file = st.file_uploader(
                f"Choose Document (PDF or Image, max {MAX_FILE_SIZE_MB}MB):",
                type=["pdf", "png", "jpg", "jpeg"]
            )

        if uploaded_file and st.button("Upload & Verify File Hash", type="primary"):
            file_bytes = uploaded_file.read()
            file_size = len(file_bytes)

            if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                st.error(f"File size exceeds limit of {MAX_FILE_SIZE_MB} MB.")
                return

            # Compute SHA-256 hash
            sha256 = hashlib.sha256(file_bytes).hexdigest()
            clean_name = f"{target_app.application_no}_{doc_type_code}_{uploaded_file.name}"
            save_path = UPLOADS_DIR / clean_name

            with open(save_path, "wb") as f:
                f.write(file_bytes)

            # Check if this document type already exists (Version control)
            existing_doc = db.query(Document).filter_by(
                application_id=target_app.id, document_type=doc_type_code
            ).first()

            if existing_doc:
                # Archive old version
                old_ver = DocumentVersion(
                    document_id=existing_doc.id,
                    version_num=existing_doc.version,
                    filename=existing_doc.filename,
                    storage_path=existing_doc.storage_path,
                    sha256_hash=existing_doc.sha256_hash,
                    uploaded_by=existing_doc.uploaded_by,
                )
                db.add(old_ver)
                # Update current document
                existing_doc.filename = clean_name
                existing_doc.storage_path = str(save_path)
                existing_doc.file_size = file_size
                existing_doc.sha256_hash = sha256
                existing_doc.mime_type = uploaded_file.type or "application/octet-stream"
                existing_doc.version += 1
                existing_doc.uploaded_by = user.id
                db.commit()
                st.success(f"Updated **{doc_type_code}** to version v{existing_doc.version} (Hash: `{sha256[:12]}...`)")
            else:
                new_doc = Document(
                    application_id=target_app.id,
                    document_type=doc_type_code,
                    filename=clean_name,
                    storage_path=str(save_path),
                    file_size=file_size,
                    sha256_hash=sha256,
                    mime_type=uploaded_file.type or "application/octet-stream",
                    status="UPLOADED",
                    version=1,
                    uploaded_by=user.id,
                )
                db.add(new_doc)
                db.commit()
                st.success(f"Successfully uploaded **{doc_type_code}** (Hash: `{sha256[:12]}...`)")

            log_audit_event(
                actor_id=user.id,
                actor_username=user.username,
                actor_role=user.role,
                action="DOCUMENT_UPLOADED",
                target_type="DOCUMENT",
                target_id=doc_type_code,
                details={"app_no": target_app.application_no, "size": file_size, "hash": sha256},
                db_session=db,
            )
            st.rerun()

        # Display Document Inventory for this Application
        st.markdown("---")
        st.markdown(f"### 📋 Current Document Inventory for {target_app.application_no}")
        docs = db.query(Document).filter_by(application_id=target_app.id).all()
        if not docs:
            st.info("No documents uploaded yet for this application.")
        else:
            table_docs = []
            for d in docs:
                table_docs.append({
                    "Type": d.document_type,
                    "Filename": d.filename,
                    "Size (KB)": f"{d.file_size / 1024:.1f}",
                    "Version": f"v{d.version}",
                    "Status": d.status,
                    "SHA-256 Digest": d.sha256_hash[:16] + "...",
                    "Uploaded": d.created_at.strftime("%Y-%m-%d %H:%M") if d.created_at else "N/A",
                })
            st.dataframe(table_docs, use_container_width=True)

    finally:
        db.close()
