from __future__ import annotations

import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pypdfium2 as pdfium
import pytest
import zxingcpp
from django.conf import settings
from django.db import close_old_connections
from PIL import Image
from rest_framework.test import APIClient
from svix.webhooks import Webhook

from apps.accounts.models import AdminRole, User
from apps.checkins.models import CheckIn, VerificationMethod
from apps.checkins.services import admit_guest, verify_manual_reference, verify_qr_payload
from apps.communications.models import EmailStatus
from apps.communications.pdf_pass import build_qr_payload, generate_admission_pass_pdf
from apps.communications.services import (
    acquire_next_email_job,
    process_acquired_email_job,
    process_resend_webhook,
)
from apps.events.contacts import build_whatsapp_contact_links
from apps.events.models import Event
from apps.invitations.artwork import FORMAT_SPECS, render_promotional_artwork
from apps.invitations.crypto import decrypt_token
from apps.invitations.models import Invitation, InvitationStatus
from apps.invitations.services import (
    claim_invitation,
    correct_guest_information,
    generate_invitations,
    inspect_invitation_by_token,
    revoke_invitation,
    sanitize_csv_cell,
)


def _csrf_client() -> tuple[APIClient, str]:
    client = APIClient(enforce_csrf_checks=True)
    resp = client.get("/api/auth/csrf/")
    assert resp.status_code == 200
    token = resp.json()["csrfToken"]
    return client, token


@pytest.mark.django_db
def test_admin_auth_csrf_rbac_deactivation_and_last_superadmin():
    super_admin = User.objects.create_superuser(
        email="super@drip.test",
        password="StrongSuperPassword!2026",
        display_name="Chief Host",
    )
    ordinary_admin = User.objects.create_user(
        email="host@drip.test",
        password="StrongHostPassword!2026",
        display_name="Floor Host",
        role=AdminRole.ADMIN,
        invitation_limit=3,
    )

    # 1. Anonymous login without CSRF token must be rejected
    raw_client = APIClient(enforce_csrf_checks=True)
    no_csrf = raw_client.post(
        "/api/auth/login/",
        {"email": "super@drip.test", "password": "StrongSuperPassword!2026"},
        format="json",
    )
    assert no_csrf.status_code == 403

    # 2. Valid login with CSRF succeeds
    super_client, super_csrf = _csrf_client()
    login_resp = super_client.post(
        "/api/auth/login/",
        {"email": "super@drip.test", "password": "StrongSuperPassword!2026"},
        format="json",
        HTTP_X_CSRFTOKEN=super_csrf,
    )
    assert login_resp.status_code == 200
    super_csrf = super_client.cookies["drip_csrf"].value

    # 3. Cannot deactivate the final active super administrator
    last_super_resp = super_client.post(
        f"/api/users/{super_admin.id}/deactivate/",
        {},
        format="json",
        HTTP_X_CSRFTOKEN=super_csrf,
    )
    assert last_super_resp.status_code == 400
    assert last_super_resp.json()["error"]["code"] == "LAST_SUPER_ADMIN"

    # 4. Ordinary admin RBAC restrictions (cannot view users, export CSV, or revoke other admin's link)
    super_batch = generate_invitations(actor=super_admin, quantity=1)
    super_inv = super_batch.invitations[0][0]

    ord_client, ord_csrf = _csrf_client()
    assert (
        ord_client.post(
            "/api/auth/login/",
            {"email": "host@drip.test", "password": "StrongHostPassword!2026"},
            format="json",
            HTTP_X_CSRFTOKEN=ord_csrf,
        ).status_code
        == 200
    )
    ord_csrf = ord_client.cookies["drip_csrf"].value

    assert ord_client.get("/api/users/").status_code == 403
    assert ord_client.get("/api/invitations/export/").status_code == 403
    assert (
        ord_client.post(
            f"/api/invitations/{super_inv.id}/revoke/",
            {"reason": "Attempted cross-admin revoke"},
            format="json",
            HTTP_X_CSRFTOKEN=ord_csrf,
        ).status_code
        == 403
    )

    # 5. Deactivating ordinary admin immediately invalidates their active session
    deact_resp = super_client.post(
        f"/api/users/{ordinary_admin.id}/deactivate/",
        {},
        format="json",
        HTTP_X_CSRFTOKEN=super_csrf,
    )
    assert deact_resp.status_code == 200
    after_deact = ord_client.get("/api/auth/me/")
    assert after_deact.status_code in {401, 403}


@pytest.mark.django_db
def test_quotas_single_use_claim_duplicate_email_and_non_consuming_get():
    Event.get_current()
    event = Event.objects.get(slug=Event.SINGLETON_SLUG)
    event.global_invitation_limit = 4
    event.save()

    host = User.objects.create_user(
        email="quota@drip.test",
        password="StrongHostPassword!2026",
        display_name="Quota Host",
        role=AdminRole.ADMIN,
        invitation_limit=3,
    )

    # Requesting 4 exceeds per-admin quota (3) -> zero partial batch created
    with pytest.raises(Exception) as exc_info:
        generate_invitations(actor=host, quantity=4)
    assert getattr(exc_info.value, "error_code", "") == "INVITATION_LIMIT_REACHED"
    assert Invitation.objects.count() == 0

    batch = generate_invitations(actor=host, quantity=3)
    assert len(batch.invitations) == 3

    inv1, url1 = batch.invitations[0]
    inv2, url2 = batch.invitations[1]
    token1 = url1.rsplit("/", 1)[-1]
    token2 = url2.rsplit("/", 1)[-1]

    # GET preview NEVER consumes invitation
    preview1 = inspect_invitation_by_token(token1)
    preview2 = inspect_invitation_by_token(token1)
    assert preview1["state"] == "VALID_UNUSED"
    assert preview2["state"] == "VALID_UNUSED"

    # First claim succeeds and wipes recoverable claim token
    res1 = claim_invitation(
        raw_token=token1,
        raw_nickname="Amina ✨",
        raw_email="  Guest.One+VIP@Example.COM ", raw_gender="FEMALE",
    )
    inv1.refresh_from_db()
    assert inv1.status == InvitationStatus.CLAIMED
    assert inv1.claim_token_encrypted == ""
    assert res1.raw_receipt_token != token1
    assert res1.raw_share_token != token1

    # Second claim on same link rejected
    with pytest.raises(Exception) as dup_link_exc:
        claim_invitation(raw_token=token1, raw_nickname="Other", raw_email="other@example.com", raw_gender="FEMALE")
    assert getattr(dup_link_exc.value, "error_code", "") == "INVITATION_ALREADY_CLAIMED"

    # Duplicate email (case-insensitive) on a SECOND unused link is rejected AND leaves inv2 UNUSED!
    with pytest.raises(Exception) as dup_email_exc:
        claim_invitation(
            raw_token=token2,
            raw_nickname="Amina Again",
            raw_email="guest.one+vip@example.com", raw_gender="FEMALE",
        )
    assert getattr(dup_email_exc.value, "error_code", "") == "DUPLICATE_EMAIL"
    inv2.refresh_from_db()
    assert inv2.status == InvitationStatus.UNUSED
    assert inv2.guest_email_normalized is None

    # Preserves Gmail dots / +aliases as distinct addresses
    res_distinct = claim_invitation(
        raw_token=token2,
        raw_nickname="Amina Alias",
        raw_email="guestone@example.com", raw_gender="FEMALE",
    )
    assert res_distinct.invitation.status == InvitationStatus.CLAIMED


@pytest.mark.django_db
def test_pdf_qr_real_decoding_artwork_dimensions_and_privacy():
    super_admin = User.objects.create_superuser(
        email="pdf@drip.test",
        password="StrongSuperPassword!2026",
        display_name="PDF Admin",
    )
    batch = generate_invitations(actor=super_admin, quantity=1)
    token = batch.invitations[0][1].rsplit("/", 1)[-1]

    unicode_long_nick = "Nankya Zuri — 東京ファッション Queen 2026"
    claim_res = claim_invitation(
        raw_token=token,
        raw_nickname=unicode_long_nick,
        raw_email="zuri@example.com", raw_gender="FEMALE",
    )
    inv = claim_res.invitation
    raw_adm_token = decrypt_token(inv.admission_token_encrypted)

    # Render ReportLab PDF and decode actual QR pixels from rendered page
    filename, pdf_bytes = generate_admission_pass_pdf(
        invitation=inv,
        raw_admission_token=raw_adm_token,
    )
    assert filename == f"DRIP-AND-RHYTHM-{inv.reference}.pdf"
    doc = pdfium.PdfDocument(pdf_bytes)
    assert len(doc) == 1
    pil_page = doc[0].render(scale=3.0).to_pil()
    decoded = zxingcpp.read_barcodes(pil_page)
    assert len(decoded) == 1
    assert decoded[0].text == build_qr_payload(raw_adm_token)
    assert inv.guest_email not in decoded[0].text
    assert token not in decoded[0].text

    # Verify all 4 Pillow PNG artwork compositions & exact pixel dimensions
    for fmt, expected_size in FORMAT_SPECS.items():
        png_bytes = render_promotional_artwork(
            event=inv.event,
            format_name=fmt,
            nickname=inv.nickname,
            show_nickname=True,
        )
        img = Image.open(io.BytesIO(png_bytes))
        assert img.format == "PNG"
        assert img.size == expected_size

    # Verify public share privacy (anonymous by default; never exposes email/ref/QR)
    anon_client = APIClient()
    share_resp = anon_client.get(f"/api/share/{claim_res.raw_share_token}/")
    assert share_resp.status_code == 200
    share_json = share_resp.json()
    assert share_json["nickname"] is None
    serialized_str = json.dumps(share_json)
    assert "zuri@example.com" not in serialized_str
    assert inv.reference not in serialized_str
    assert raw_adm_token not in serialized_str

    # Verify HTTP image endpoint works with ?format= query parameter across all 4 formats
    for fmt, expected_size in FORMAT_SPECS.items():
        img_resp = anon_client.get(f"/api/share/{claim_res.raw_share_token}/image/?format={fmt}&v=1")
        assert img_resp.status_code == 200
        assert img_resp["Content-Type"] == "image/png"
        http_img = Image.open(io.BytesIO(img_resp.content))
        assert http_img.size == expected_size

    # Verify PDF contains clickable WhatsApp reservation annotations & decodes QR accurately
    assert b"https://wa.me/256781210342?text=Hello%2C%20I%20would%20like%20to%20inquire%20about%20DRIP%20%26%20RHYTHM%20on%205%20December%202026." in pdf_bytes
    assert re.fullmatch(r"DR-\d{8}", inv.reference)

    # Verify WhatsApp links helper & manual verification for both new 8-digit & legacy 6-digit references
    wa_links = build_whatsapp_contact_links(inv.event)
    assert [c["display"] for c in wa_links] == ["0781210342", "0742627388", "0700246148"]
    assert wa_links[0]["whatsapp_url"].startswith("https://wa.me/256781210342?text=Hello")

    manual_new = verify_manual_reference(reference=inv.reference)
    assert manual_new["result_code"] == "VALID"

    # Simulate preserved legacy 6-digit reference remaining valid for manual lookup
    inv.reference = "DR-000001"
    inv.save(update_fields=["reference"])
    manual_legacy = verify_manual_reference(reference="DR-000001")
    assert manual_legacy["result_code"] == "VALID"

    # CSV formula injection protection
    assert sanitize_csv_cell("=CMD|' /C calc'!A0") == "'=CMD|' /C calc'!A0"
    assert sanitize_csv_cell("@SUM(1+1)") == "'@SUM(1+1)"


@pytest.mark.django_db
def test_email_worker_webhook_revocation_and_email_correction_rotation():
    super_admin = User.objects.create_superuser(
        email="ops@drip.test",
        password="StrongSuperPassword!2026",
        display_name="Ops Lead",
    )
    batch = generate_invitations(actor=super_admin, quantity=2)
    token_a = batch.invitations[0][1].rsplit("/", 1)[-1]
    token_b = batch.invitations[1][1].rsplit("/", 1)[-1]

    claim_a = claim_invitation(raw_token=token_a, raw_nickname="Kato", raw_email="kato@example.com", raw_gender="FEMALE")
    inv_a = claim_a.invitation
    old_adm_token = decrypt_token(inv_a.admission_token_encrypted)
    old_qr = build_qr_payload(old_adm_token)

    # Worker acquires and processes pending email job
    job = acquire_next_email_job("test-worker-1")
    assert job is not None
    processed = process_acquired_email_job(job)
    assert processed.status == EmailStatus.SENT

    # Svix webhook signature verification + monotonic status + replay deduplication
    secret_b64 = settings.RESEND_WEBHOOK_SECRET
    wh = Webhook(secret_b64)
    msg_id = "msg_2bTestSvix001"
    now_dt = datetime.now(tz=UTC)
    ts_str = str(int(now_dt.timestamp()))
    body_bytes = json.dumps(
        {"type": "email.delivered", "data": {"email_id": processed.provider_message_id}}
    ).encode("utf-8")
    sig = wh.sign(msg_id, now_dt, body_bytes.decode("utf-8"))
    headers = {"svix-id": msg_id, "svix-timestamp": ts_str, "svix-signature": sig}

    res_wh = process_resend_webhook(raw_body=body_bytes, headers=headers)
    assert res_wh["status"] == "processed"
    processed.refresh_from_db()
    assert processed.status == EmailStatus.DELIVERED

    # Duplicate webhook replay ignored
    dup_wh = process_resend_webhook(raw_body=body_bytes, headers=headers)
    assert dup_wh["status"] == "duplicate_ignored"

    # Out-of-order `email.sent` does NOT downgrade `DELIVERED`
    older_id = "msg_2bTestSvix002"
    older_bytes = json.dumps(
        {"type": "email.sent", "data": {"email_id": processed.provider_message_id}}
    ).encode("utf-8")
    older_sig = wh.sign(older_id, now_dt, older_bytes.decode("utf-8"))
    process_resend_webhook(
        raw_body=older_bytes,
        headers={"svix-id": older_id, "svix-timestamp": ts_str, "svix-signature": older_sig},
    )
    processed.refresh_from_db()
    assert processed.status == EmailStatus.DELIVERED

    # Super admin corrects guest email -> old QR and old claim receipt MUST be invalidated immediately!
    updated_inv = correct_guest_information(
        actor=super_admin,
        invitation_id=inv_a.id,
        new_email="kato.updated@example.com",
    )
    assert updated_inv.admission_credential_version == 2
    old_verify = verify_qr_payload(raw_payload=old_qr)
    assert old_verify["result_code"] == "INVALID_QR_CODE"
    assert old_verify["can_admit"] is False

    new_qr = build_qr_payload(decrypt_token(updated_inv.admission_token_encrypted))
    new_verify = verify_qr_payload(raw_payload=new_qr)
    assert new_verify["result_code"] == "VALID"
    assert new_verify["can_admit"] is True

    # Revoking a claimed invitation blocks QR admission & public sharing while keeping email reserved
    claim_b = claim_invitation(raw_token=token_b, raw_nickname="Nambi", raw_email="nambi@example.com", raw_gender="FEMALE")
    qr_b = build_qr_payload(decrypt_token(claim_b.invitation.admission_token_encrypted))
    revoke_invitation(actor=super_admin, invitation_id=claim_b.invitation.id, reason="Test revoke")

    rev_verify = verify_qr_payload(raw_payload=qr_b)
    assert rev_verify["result_code"] == "INVITATION_REVOKED"
    assert APIClient().get(f"/api/share/{claim_b.raw_share_token}/").status_code == 404


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_claims_and_concurrent_admissions():
    super_admin = User.objects.create_superuser(
        email="concurrency@drip.test",
        password="StrongSuperPassword!2026",
        display_name="Concurrency Host",
    )
    batch = generate_invitations(actor=super_admin, quantity=3)
    same_link_token = batch.invitations[0][1].rsplit("/", 1)[-1]
    dup_email_token_1 = batch.invitations[1][1].rsplit("/", 1)[-1]
    dup_email_token_2 = batch.invitations[2][1].rsplit("/", 1)[-1]

    # 1. Two simultaneous claims against the SAME invitation link -> exactly 1 succeeds
    def _claim_same_link(idx: int) -> str:
        close_old_connections()
        try:
            claim_invitation(
                raw_token=same_link_token,
                raw_nickname=f"Racer {idx}",
                raw_email=f"racer{idx}@example.com", raw_gender="FEMALE",
            )
            return "OK"
        except Exception as exc:
            return getattr(exc, "error_code", type(exc).__name__)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        same_link_outcomes = sorted(pool.map(_claim_same_link, [1, 2]))
    assert same_link_outcomes == ["INVITATION_ALREADY_CLAIMED", "OK"]

    # 2. Two simultaneous claims using the SAME normalized email on two DIFFERENT links -> 1 succeeds, 2nd stays UNUSED
    def _claim_same_email(tok: str) -> str:
        close_old_connections()
        try:
            claim_invitation(
                raw_token=tok,
                raw_nickname="Twin Email",
                raw_email="shared.guest@example.com", raw_gender="FEMALE",
            )
            return "OK"
        except Exception as exc:
            return getattr(exc, "error_code", type(exc).__name__)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        same_email_outcomes = sorted(pool.map(_claim_same_email, [dup_email_token_1, dup_email_token_2]))
    assert same_email_outcomes == ["DUPLICATE_EMAIL", "OK"]

    unused_remaining = Invitation.objects.filter(
        id__in=[batch.invitations[1][0].id, batch.invitations[2][0].id],
        status=InvitationStatus.UNUSED,
    ).count()
    assert unused_remaining == 1

    # 3. Two administrators simultaneously admitting the SAME guest -> exactly 1 CheckIn created
    claimed_inv = Invitation.objects.get(guest_email_normalized="shared.guest@example.com")
    qr_payload = build_qr_payload(decrypt_token(claimed_inv.admission_token_encrypted))

    def _admit_race(_idx: int) -> str:
        close_old_connections()
        try:
            admit_guest(
                actor=super_admin,
                verification_method=VerificationMethod.QR,
                qr_payload=qr_payload,
            )
            return "ADMITTED"
        except Exception as exc:
            return getattr(exc, "error_code", type(exc).__name__)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        admit_outcomes = sorted(pool.map(_admit_race, [1, 2]))
    assert admit_outcomes == ["ADMITTED", "ALREADY_ADMITTED"]
    assert CheckIn.objects.filter(invitation=claimed_inv).count() == 1
