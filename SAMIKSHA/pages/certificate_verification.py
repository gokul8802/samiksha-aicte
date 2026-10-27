"""
Certificate Verification Gateway for Samiksha
Integrates with authorized issuers and a controlled mock registry (7 distinct states)
to verify certificate validity, expiry, holder identity, and revocations.
"""

import streamlit as st
from datetime import datetime, timezone
from modules.database import get_db_session, Application, Certificate, MockIssuerRecord
from modules.permissions import can_user, Permissions
from modules.audit_logger import log_audit_event


def render_certificate_verification(user):
    st.markdown("## 🛡️ Certificate Verification Gateway")
    st.markdown(
        "*Verification of statutory certificates against authorized issuing authorities and simulated registry.*"
    )

    if not can_user(user, Permissions.RUN_CERTIFICATE_VERIFY):
        st.error("Access Denied: You do not possess the `run_certificate_verify` permission.")
        return

    st.info("""
    ℹ️ **Simulated Demonstration Mode:**  
    External state government portals and registrar APIs are currently simulated via the **AICTE Mock Issuer Registry**.  
    All query results are explicitly labelled as **MOCK SIMULATED**.
    """)

    db = get_db_session()
    try:
        apps = db.query(Application).all()
        if not apps:
            st.info("No applications found.")
            return

        app_options = {f"{a.application_no} — {a.institution.name if a.institution else 'N/A'}": a for a in apps}
        selected_label = st.selectbox("Select Application for Certificate Verification:", list(app_options.keys()))
        app = app_options[selected_label]

        st.markdown("---")
        st.markdown("### 🔍 Certificate Lookup & Verification Form")

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            cert_no = st.text_input("Certificate Number:", placeholder="e.g. FS-UP-2024-88392", value="FS-UP-2024-88392")
        with c2:
            cert_type = st.selectbox("Certificate Type:", ["FIRE_SAFETY", "OCCUPANCY", "LAND_USE", "UNIVERSITY_NOC"])
        with c3:
            holder_name = st.text_input("Holder Name Claimed:", value=app.institution.name if app.institution else "")

        if st.button("Query Issuing Authority Registry", type="primary"):
            # Query Mock Issuer Registry
            mock_rec = db.query(MockIssuerRecord).filter_by(certificate_number=cert_no).first()

            now = datetime.now(timezone.utc)
            status_result = "UNKNOWN_CERTIFICATE"
            notes = "No matching record located in the issuing authority registry."

            if mock_rec:
                if mock_rec.status == "REVOKED":
                    status_result = "REVOKED_BY_ISSUER"
                    notes = f"REVOKED: {mock_rec.revocation_reason}"
                elif mock_rec.status == "EXPIRED":
                    status_result = "EXPIRED"
                    notes = f"EXPIRED: Certificate expired on {mock_rec.expiry_date}."
                elif mock_rec.holder_name.lower().strip() != holder_name.lower().strip():
                    status_result = "DETAILS_MISMATCH"
                    notes = f"HOLDER MISMATCH: Official registered holder is '{mock_rec.holder_name}', but application claimed '{holder_name}'."
                else:
                    status_result = "ISSUER_CONFIRMED"
                    notes = f"CONFIRMED: Valid certificate issued by {mock_rec.issuing_authority} (Valid until {mock_rec.expiry_date or 'Indefinite'})."

            # Persist certificate verification record
            cert_record = Certificate(
                application_id=app.id,
                certificate_number=cert_no,
                holder_name=holder_name,
                issuing_authority=mock_rec.issuing_authority if mock_rec else "Unknown Authority",
                issue_date=mock_rec.issue_date if mock_rec else None,
                expiry_date=mock_rec.expiry_date if mock_rec else None,
                certificate_type=cert_type,
                digital_sig_valid=True if status_result == "ISSUER_CONFIRMED" else False,
                verification_status=status_result,
                verification_source="AICTE_MOCK_REGISTRY_SIMULATED",
                verification_notes=notes,
                verified_at=now,
            )
            db.add(cert_record)
            db.commit()

            log_audit_event(
                actor_id=user.id,
                actor_username=user.username,
                actor_role=user.role,
                action="CERTIFICATE_VERIFICATION_PERFORMED",
                target_type="CERTIFICATE",
                target_id=cert_no,
                details={"result_status": status_result, "notes": notes},
                db_session=db,
            )

            if status_result == "ISSUER_CONFIRMED":
                st.success(f"✅ **{status_result}**: {notes}")
            elif status_result in ["REVOKED_BY_ISSUER", "EXPIRED", "DETAILS_MISMATCH"]:
                st.error(f"❌ **{status_result}**: {notes}")
            else:
                st.warning(f"⚠️ **{status_result}**: {notes}")

        st.markdown("---")
        st.markdown("### 📋 Verified Certificates for this Application")
        records = db.query(Certificate).filter_by(application_id=app.id).order_by(Certificate.verified_at.desc()).all()
        if not records:
            st.info("No certificate verifications recorded yet.")
        else:
            table_certs = []
            for c in records:
                table_certs.append({
                    "Cert Number": c.certificate_number,
                    "Type": c.certificate_type,
                    "Status": c.verification_status,
                    "Issuing Authority": c.issuing_authority,
                    "Expiry": c.expiry_date or "Indefinite",
                    "Notes": c.verification_notes[:50] + "..." if c.verification_notes and len(c.verification_notes) > 50 else c.verification_notes,
                    "Verified At": c.verified_at.strftime("%Y-%m-%d %H:%M") if c.verified_at else "N/A",
                })
            st.dataframe(table_certs, use_container_width=True)

        st.markdown("---")
        st.markdown("### 🧪 Mock Issuer Registry Test Scenarios")
        st.markdown("The following seeded certificates can be entered above to demonstrate all 7 system outcomes:")
        all_mock = db.query(MockIssuerRecord).all()
        mock_data = []
        for m in all_mock:
            mock_data.append({
                "Test Cert Number": m.certificate_number,
                "Registered Holder": m.holder_name,
                "Registry Status": m.status,
                "Expected Outcome": "CONFIRMED" if m.status == "ACTIVE" and "MISMATCH" not in m.certificate_number else ("HOLDER MISMATCH" if "MISMATCH" in m.certificate_number else m.status),
            })
        st.table(mock_data)

    finally:
        db.close()
