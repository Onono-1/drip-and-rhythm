from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.checkins.models import VerificationMethod
from apps.checkins.services import admit_guest
from apps.communications.email_templates import build_invitation_email_content
from apps.communications.pdf_pass import generate_admission_pass_pdf
from apps.invitations.crypto import decrypt_token
from apps.invitations.models import GuestGender
from apps.invitations.services import claim_invitation, generate_invitations


@pytest.mark.django_db
def test_gender_validation_persistence_filtering_dashboard_correction_csv_and_privacy():
    super_admin = User.objects.create_superuser(
        email="gender-super@drip.test",
        password="StrongGenderPassword!2026",
        display_name="Chief Host",
    )
    batch = generate_invitations(actor=super_admin, quantity=3)
    token_m = batch.invitations[0][1].rsplit("/invite/", 1)[1]
    token_f = batch.invitations[1][1].rsplit("/invite/", 1)[1]
    token_invalid = batch.invitations[2][1].rsplit("/invite/", 1)[1]

    # 1. API rejects missing or invalid gender on claim
    guest_client = APIClient()
    missing_resp = guest_client.post(
        f"/api/invite/{token_invalid}/claim/",
        {"nickname": "NoGender", "email": "nogender@example.com"},
        format="json",
    )
    assert missing_resp.status_code == 400
    assert "gender" in missing_resp.json()["error"]["details"]

    invalid_resp = guest_client.post(
        f"/api/invite/{token_invalid}/claim/",
        {"nickname": "BadGender", "email": "badgender@example.com", "gender": "OTHER"},
        format="json",
    )
    assert invalid_resp.status_code == 400
    assert "gender" in invalid_resp.json()["error"]["details"]

    # 2. Valid MALE and FEMALE claims persist to PostgreSQL
    res_m = claim_invitation(
        raw_token=token_m,
        raw_nickname="Kato",
        raw_email="kato-g@example.com",
        raw_gender=GuestGender.MALE,
    )
    res_f = claim_invitation(
        raw_token=token_f,
        raw_nickname="Nambi",
        raw_email="nambi-g@example.com",
        raw_gender=GuestGender.FEMALE,
    )
    assert res_m.invitation.gender == GuestGender.MALE
    assert res_f.invitation.gender == GuestGender.FEMALE

    # Admit only the Female guest to verify claimed vs admitted breakdown
    admit_guest(
        actor=super_admin,
        verification_method=VerificationMethod.MANUAL,
        reference=res_f.invitation.reference,
        confirm_manual=True,
    )

    admin_client = APIClient()
    admin_client.force_authenticate(user=super_admin)

    # 3. Filtering in invitations & check-ins
    inv_f = admin_client.get("/api/invitations/?gender=FEMALE").json()
    assert inv_f["count"] == 1
    assert inv_f["results"][0]["reference"] == res_f.invitation.reference
    assert inv_f["results"][0]["gender"] == "FEMALE"

    ci_m = admin_client.get("/api/check-ins/?gender=MALE").json()
    assert ci_m["count"] == 0
    ci_f = admin_client.get("/api/check-ins/?gender=FEMALE").json()
    assert ci_f["count"] == 1
    assert ci_f["results"][0]["gender"] == "FEMALE"

    # 4. Dashboard male/female counts and percentages for claimed & admitted
    dash = admin_client.get("/api/dashboard/").json()["gender_breakdown"]
    assert dash["claimed"] == {"male": 1, "female": 1, "male_percent": 50.0, "female_percent": 50.0}
    assert dash["admitted"] == {"male": 0, "female": 1, "male_percent": 0.0, "female_percent": 100.0}

    # 5. Super admin gender correction updates gender without rotating credential version
    prev_ver = res_m.invitation.admission_credential_version
    corr_resp = admin_client.post(
        f"/api/invitations/{res_m.invitation.id}/correct-guest/",
        {"gender": "FEMALE"},
        format="json",
    )
    assert corr_resp.status_code == 200
    assert corr_resp.json()["gender"] == "FEMALE"
    res_m.invitation.refresh_from_db()
    assert res_m.invitation.gender == GuestGender.FEMALE
    assert res_m.invitation.admission_credential_version == prev_ver

    # 6. Authorized CSV exports include Gender column
    inv_csv = admin_client.get("/api/invitations/export/").content.decode("utf-8")
    assert "Gender" in inv_csv.splitlines()[0]
    assert ",Female," in inv_csv

    ci_csv = admin_client.get("/api/check-ins/export/").content.decode("utf-8")
    assert "Gender" in ci_csv.splitlines()[0]
    assert ",Female," in ci_csv

    # 7. Privacy: gender is excluded from emails, PDFs, and public share payload
    _subj, html_body, text_body = build_invitation_email_content(
        invitation=res_f.invitation,
        share_url=None,
    )
    assert "FEMALE" not in html_body.upper()
    assert "GENDER" not in html_body.upper()
    assert "FEMALE" not in text_body.upper()

    raw_admission = decrypt_token(res_f.invitation.admission_token_encrypted)
    _fname, pdf_bytes = generate_admission_pass_pdf(
        invitation=res_f.invitation,
        raw_admission_token=raw_admission,
    )
    assert b"Gender" not in pdf_bytes
    assert b"Female" not in pdf_bytes

    share_resp = guest_client.get(f"/api/share/{res_f.raw_share_token}/")
    assert share_resp.status_code == 200
    assert "gender" not in share_resp.json()
