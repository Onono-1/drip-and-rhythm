from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import AdminRole, User
from apps.communications.models import EmailDelivery, EmailStatus
from apps.events.models import Event
from apps.invitations.models import InvitationStatus
from apps.invitations.services import claim_invitation, generate_invitations


@pytest.mark.django_db
def test_proxy_shared_secret_blocks_direct_access_but_allows_health_and_verified_proxy():
    client = APIClient()
    with override_settings(PROXY_SHARED_SECRET="super-secret-proxy-token-2026"):
        # 1. Direct unauthenticated call to public API is rejected with 403
        direct = client.get("/api/event/public/")
        assert direct.status_code == 403
        assert direct.json()["error"]["code"] == "FORBIDDEN"

        # 2. Direct call with wrong secret is rejected
        wrong = client.get("/api/event/public/", HTTP_X_DRIP_PROXY_SECRET="wrong-secret")
        assert wrong.status_code == 403

        # 3. Render health check remains reachable without the proxy secret
        health = client.get("/api/health/")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        # 4. Verified proxy request succeeds
        proxied = client.get(
            "/api/event/public/",
            HTTP_X_DRIP_PROXY_SECRET="super-secret-proxy-token-2026",
        )
        assert proxied.status_code == 200


@pytest.mark.django_db(transaction=True)
def test_inline_post_commit_email_dispatch_and_admin_retry_endpoint():
    super_admin = User.objects.create_superuser(
        email="free-super@drip.test",
        password="StrongFreePassword!2026",
        display_name="Chief Host",
    )
    batch = generate_invitations(actor=super_admin, quantity=2)
    token_ok = batch.invitations[0][1].rsplit("/invite/", 1)[1]
    token_fail = batch.invitations[1][1].rsplit("/invite/", 1)[1]

    # 1. Normal post-commit inline dispatch succeeds without a separate worker
    with override_settings(EMAIL_INLINE_DISPATCH=True, EMAIL_DELIVERY_MODE="local"):
        res = claim_invitation(
            raw_token=token_ok,
            raw_nickname="Amina",
            raw_email="amina-free@example.com",
            raw_gender="FEMALE",
        )
        delivery = EmailDelivery.objects.get(invitation=res.invitation)
        assert delivery.status == EmailStatus.SENT
        assert delivery.attempt_count == 1

    # 2. Provider failure during inline dispatch MUST NOT roll back or invalidate the claim
    with (
        override_settings(EMAIL_INLINE_DISPATCH=True, EMAIL_DELIVERY_MODE="local"),
        patch(
            "apps.communications.services._send_via_provider",
            side_effect=RuntimeError("Simulated Resend outage"),
        ),
    ):
        res_fail = claim_invitation(
            raw_token=token_fail,
            raw_nickname="Kato",
            raw_email="kato-free@example.com",
            raw_gender="MALE",
        )
        res_fail.invitation.refresh_from_db()
        assert res_fail.invitation.status == InvitationStatus.CLAIMED
        failed_delivery = EmailDelivery.objects.get(invitation=res_fail.invitation)
        assert failed_delivery.status == EmailStatus.PENDING
        assert "Simulated Resend outage" in failed_delivery.failure_reason

    # 3. Unauthenticated retry request is rejected; authenticated admin retries pending job cleanly
    anon = APIClient()
    assert anon.post("/api/emails/process-pending/", {}, format="json").status_code in {401, 403}

    admin_client = APIClient()
    admin_client.force_authenticate(user=super_admin)
    retry_resp = admin_client.post(
        "/api/emails/process-pending/",
        {"include_failed": True, "max_jobs": 10},
        format="json",
    )
    assert retry_resp.status_code == 200
    assert retry_resp.json()["sent"] >= 1
    failed_delivery.refresh_from_db()
    assert failed_delivery.status == EmailStatus.SENT


@pytest.mark.django_db
def test_bootstrap_production_is_idempotent_and_never_resets_existing_password(monkeypatch):
    monkeypatch.setenv("INITIAL_SUPERADMIN_EMAIL", "boot@drip.test")
    monkeypatch.setenv("INITIAL_SUPERADMIN_PASSWORD", "InitialStrongPass!2026")
    monkeypatch.setenv("INITIAL_SUPERADMIN_NAME", "Event Lead")

    out1 = StringIO()
    call_command("bootstrap_production", stdout=out1)
    assert Event.objects.filter(slug=Event.SINGLETON_SLUG).exists()
    user = User.objects.get(email="boot@drip.test")
    assert user.role == AdminRole.SUPER_ADMIN
    assert user.check_password("InitialStrongPass!2026")

    # Change password and re-run bootstrap with a different env password — must NOT reset!
    user.set_password("RotatedProductionPass!2026")
    user.save()
    monkeypatch.setenv("INITIAL_SUPERADMIN_PASSWORD", "AttemptedOverwrite!2026")

    out2 = StringIO()
    call_command("bootstrap_production", stdout=out2)
    user.refresh_from_db()
    assert user.check_password("RotatedProductionPass!2026")
    assert not user.check_password("AttemptedOverwrite!2026")
