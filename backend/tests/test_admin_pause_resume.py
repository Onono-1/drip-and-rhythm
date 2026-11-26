from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import AdminRole, User
from apps.audit.models import AuditLog
from apps.invitations.models import GuestGender
from apps.invitations.services import claim_invitation, create_master_link, generate_invitations

PAUSED_LOGIN_MESSAGE = (
    "Your administrator account has been temporarily paused. "
    "Please contact the Super Admin to restore your access."
)


def _csrf_client() -> tuple[APIClient, str]:
    client = APIClient(enforce_csrf_checks=True)
    resp = client.get("/api/auth/csrf/")
    assert resp.status_code == 200
    return client, resp.json()["csrfToken"]


@pytest.mark.django_db
def test_admin_pause_resume_blocks_sessions_protects_superadmins_and_preserves_invitations():
    super_admin = User.objects.create_superuser(
        email="pause-super@drip.test",
        password="StrongSuperPassword!2026",
        display_name="Chief Host",
    )
    second_super = User.objects.create_superuser(
        email="pause-super-2@drip.test",
        password="StrongSuperPassword!2026",
        display_name="Second Chief",
    )
    normal_admin = User.objects.create_user(
        email="pause-host@drip.test",
        password="StrongHostPassword!2026",
        display_name="Floor Host",
        role=AdminRole.ADMIN,
        invitation_limit=10,
    )

    # Normal admin generates single, bulk, and master links BEFORE being paused
    single = generate_invitations(actor=normal_admin, quantity=1)
    bulk = generate_invitations(actor=normal_admin, quantity=2)
    master = create_master_link(actor=normal_admin, name="Host VIP", max_tickets=2)

    # Normal admin logs in with an active session
    host_client, host_csrf = _csrf_client()
    login_ok = host_client.post(
        "/api/auth/login/",
        {"email": normal_admin.email, "password": "StrongHostPassword!2026"},
        format="json",
        HTTP_X_CSRFTOKEN=host_csrf,
    )
    assert login_ok.status_code == 200
    assert host_client.get("/api/auth/me/").status_code == 200

    # Normal admin cannot pause/resume anyone (only Super Admins can)
    host_csrf = host_client.cookies["drip_csrf"].value
    assert (
        host_client.post(
            f"/api/users/{normal_admin.id}/pause/",
            {},
            format="json",
            HTTP_X_CSRFTOKEN=host_csrf,
        ).status_code
        == 403
    )

    # Super Admin logs in
    super_client, super_csrf = _csrf_client()
    assert (
        super_client.post(
            "/api/auth/login/",
            {"email": super_admin.email, "password": "StrongSuperPassword!2026"},
            format="json",
            HTTP_X_CSRFTOKEN=super_csrf,
        ).status_code
        == 200
    )
    super_csrf = super_client.cookies["drip_csrf"].value

    # Super Admin accounts must NOT be pausable (neither self nor another Super Admin)
    assert (
        super_client.post(
            f"/api/users/{super_admin.id}/pause/",
            {},
            format="json",
            HTTP_X_CSRFTOKEN=super_csrf,
        ).status_code
        == 400
    )
    assert (
        super_client.post(
            f"/api/users/{second_super.id}/pause/",
            {},
            format="json",
            HTTP_X_CSRFTOKEN=super_csrf,
        ).status_code
        == 400
    )

    # Super Admin pauses Normal Admin -> immediate session invalidation + audit log
    pause_resp = super_client.post(
        f"/api/users/{normal_admin.id}/pause/",
        {},
        format="json",
        HTTP_X_CSRFTOKEN=super_csrf,
    )
    assert pause_resp.status_code == 200
    assert pause_resp.json()["is_active"] is False
    assert AuditLog.objects.filter(action_type="ADMIN_USER_PAUSED", target_id=str(normal_admin.id)).exists()

    # Existing authenticated session is immediately blocked on protected endpoints
    assert host_client.get("/api/auth/me/").status_code in {401, 403}
    assert host_client.get("/api/dashboard/").status_code in {401, 403}

    # Paused admin entering valid login credentials sees the exact required message
    fresh_client, fresh_csrf = _csrf_client()
    blocked_login = fresh_client.post(
        "/api/auth/login/",
        {"email": normal_admin.email, "password": "StrongHostPassword!2026"},
        format="json",
        HTTP_X_CSRFTOKEN=fresh_csrf,
    )
    assert blocked_login.status_code == 403
    assert blocked_login.json()["error"]["message"] == PAUSED_LOGIN_MESSAGE

    # All previously generated single, bulk, and master invitation links continue working normally!
    single_tok = single.invitations[0][1].rsplit("/invite/", 1)[1]
    bulk_tok = bulk.invitations[0][1].rsplit("/invite/", 1)[1]
    master_tok = master.claim_url.rsplit("/invite/", 1)[1]

    c_single = claim_invitation(
        raw_token=single_tok,
        raw_nickname="Amina",
        raw_email="amina-paused@example.com",
        raw_gender=GuestGender.FEMALE,
    )
    c_bulk = claim_invitation(
        raw_token=bulk_tok,
        raw_nickname="Kato",
        raw_email="kato-paused@example.com",
        raw_gender=GuestGender.MALE,
    )
    c_master = claim_invitation(
        raw_token=master_tok,
        raw_nickname="Nia",
        raw_email="nia-paused@example.com",
        raw_gender=GuestGender.FEMALE,
    )
    assert c_single.invitation.status == "CLAIMED"
    assert c_bulk.invitation.status == "CLAIMED"
    assert c_master.invitation.status == "CLAIMED"

    # Super Admin resumes Normal Admin -> audit log recorded and sign-in restored
    resume_resp = super_client.post(
        f"/api/users/{normal_admin.id}/resume/",
        {},
        format="json",
        HTTP_X_CSRFTOKEN=super_csrf,
    )
    assert resume_resp.status_code == 200
    assert resume_resp.json()["is_active"] is True
    assert AuditLog.objects.filter(action_type="ADMIN_USER_RESUMED", target_id=str(normal_admin.id)).exists()

    restored_client, restored_csrf = _csrf_client()
    assert (
        restored_client.post(
            "/api/auth/login/",
            {"email": normal_admin.email, "password": "StrongHostPassword!2026"},
            format="json",
            HTTP_X_CSRFTOKEN=restored_csrf,
        ).status_code
        == 200
    )
    assert restored_client.get("/api/auth/me/").status_code == 200
