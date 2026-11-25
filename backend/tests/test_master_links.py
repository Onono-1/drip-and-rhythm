from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import close_old_connections
from rest_framework.test import APIClient

from apps.accounts.models import AdminRole, User
from apps.audit.exceptions import ApplicationError
from apps.checkins.services import verify_qr_payload
from apps.communications.models import EmailDelivery, EmailStatus
from apps.communications.pdf_pass import build_qr_payload
from apps.communications.services import acquire_next_email_job, process_acquired_email_job
from apps.events.models import Event
from apps.invitations.artwork import get_or_render_promotional_artwork
from apps.invitations.crypto import decrypt_token
from apps.invitations.models import (
    GuestGender,
    Invitation,
    InvitationStatus,
    MasterInvitationLink,
    MasterLinkStatus,
)
from apps.invitations.services import (
    claim_invitation,
    close_master_link,
    create_master_link,
    generate_invitations,
    get_quota_usage,
    inspect_invitation_by_token,
    pause_master_link,
    resume_master_link,
    revoke_invitation,
)


@pytest.mark.django_db(transaction=True)
def test_master_link_lifecycle_quotas_permissions_and_existing_compatibility(tmp_path, settings):
    settings.ARTWORK_CACHE_DIR = str(tmp_path)

    event = Event.get_current()
    event.global_invitation_limit = 6
    event.save(update_fields=["global_invitation_limit", "updated_at"])

    super_admin = User.objects.create_superuser(
        email="ml-super@drip.test",
        password="StrongMasterPassword!2026",
        display_name="Chief Host",
    )
    admin_a = User.objects.create_user(
        email="ml-host-a@drip.test",
        password="StrongHostPassword!2026",
        display_name="Host A",
        role=AdminRole.ADMIN,
        invitation_limit=4,
    )
    admin_b = User.objects.create_user(
        email="ml-host-b@drip.test",
        password="StrongHostPassword!2026",
        display_name="Host B",
        role=AdminRole.ADMIN,
        invitation_limit=4,
    )

    # 1. Quota reservation on Master Link creation (single + bulk + master share exact accounting)
    with pytest.raises(ApplicationError) as exc_over:
        create_master_link(actor=admin_a, name="Too Big", max_tickets=5)
    assert exc_over.value.error_code == "INVITATION_LIMIT_REACHED"

    created = create_master_link(actor=admin_a, name="VIP Table", max_tickets=3)
    ml = created.master_link
    raw_token = created.claim_url.rsplit("/invite/", 1)[1]

    # Zero Invitation rows pre-created; full 3 slots reserved against admin_a & global quota
    assert Invitation.objects.filter(master_link=ml).count() == 0
    assert get_quota_usage(event=event) == 3
    assert get_quota_usage(event=event, actor=admin_a) == 3
    assert created.remaining_admin_quota == 1
    assert created.remaining_global_quota == 3

    # Existing single/bulk generation respects the reserved master link capacity
    single = generate_invitations(actor=admin_a, quantity=1)
    assert get_quota_usage(event=event, actor=admin_a) == 4
    with pytest.raises(ApplicationError) as exc_single_over:
        generate_invitations(actor=admin_a, quantity=1)
    assert exc_single_over.value.error_code == "INVITATION_LIMIT_REACHED"

    # 2. Guest inspects and claims via Master Link -> individual ticket, QR, email, personalized artwork
    inspect = inspect_invitation_by_token(raw_token)
    assert inspect["claimable"] is True
    assert inspect["state"] == "VALID_UNUSED"

    claim1 = claim_invitation(
        raw_token=raw_token,
        raw_nickname="Sasha",
        raw_email="sasha-ml@example.com",
        raw_gender=GuestGender.FEMALE,
    )
    inv1 = claim1.invitation
    ml.refresh_from_db()
    assert inv1.master_link_id == ml.id
    assert inv1.generated_by_id == admin_a.id
    assert inv1.reference.startswith("DR-")
    assert ml.claimed_count == 1
    assert ml.remaining_tickets == 2
    # Converting 1 reserved slot into 1 claimed Invitation must NOT double-count quota!
    assert get_quota_usage(event=event) == 4
    assert get_quota_usage(event=event, actor=admin_a) == 4

    # Verify QR admission check & email job & personalized artwork work cleanly on master-claimed ticket
    raw_adm = decrypt_token(inv1.admission_token_encrypted)
    qr_check = verify_qr_payload(raw_payload=build_qr_payload(raw_adm))
    assert qr_check["can_admit"] is True
    assert qr_check["reference"] == inv1.reference

    # Master link token itself must NEVER pass QR verification
    assert verify_qr_payload(raw_payload=build_qr_payload(raw_token))["can_admit"] is False

    job = acquire_next_email_job("ml-test-worker")
    assert job is not None and job.invitation_id == inv1.id
    assert process_acquired_email_job(job).status == EmailStatus.SENT

    art = get_or_render_promotional_artwork(
        event=event,
        format_name="story",
        nickname=inv1.nickname,
        invitation_id=str(inv1.id),
        sharing_version=inv1.sharing_version,
    )
    assert len(art.png_bytes) > 1000

    # 3. Duplicate email rejected across Single/Master without consuming capacity
    with pytest.raises(ApplicationError) as exc_dup:
        claim_invitation(
            raw_token=raw_token,
            raw_nickname="Sasha Dup",
            raw_email="SASHA-ML@example.com",
            raw_gender=GuestGender.FEMALE,
        )
    assert exc_dup.value.error_code == "DUPLICATE_EMAIL"
    ml.refresh_from_db()
    assert ml.claimed_count == 1

    # Single link also rejects the email already claimed via Master Link (and remains UNUSED)
    single_token = single.invitations[0][1].rsplit("/invite/", 1)[1]
    with pytest.raises(ApplicationError) as exc_cross_dup:
        claim_invitation(
            raw_token=single_token,
            raw_nickname="Cross",
            raw_email="sasha-ml@example.com",
            raw_gender=GuestGender.FEMALE,
        )
    assert exc_cross_dup.value.error_code == "DUPLICATE_EMAIL"
    assert inspect_invitation_by_token(single_token)["claimable"] is True

    # 4. Normal Admin ownership vs Super Admin permissions
    client_b = APIClient()
    client_b.force_authenticate(user=admin_b)
    # Normal Admin B can view all master links, but cannot pause/close Admin A's link
    assert client_b.get("/api/invitations/master-links/").status_code == 200
    assert client_b.post(f"/api/invitations/master-links/{ml.id}/pause/").status_code == 403
    assert client_b.post(f"/api/invitations/master-links/{ml.id}/close/").status_code == 403

    # 5. Pause retains reserved capacity; blocks new claims; Resume restores claiming
    pause_master_link(actor=admin_a, master_link_id=ml.id)
    assert get_quota_usage(event=event, actor=admin_a) == 4
    assert inspect_invitation_by_token(raw_token)["state"] == "MASTER_LINK_PAUSED"
    with pytest.raises(ApplicationError) as exc_paused:
        claim_invitation(
            raw_token=raw_token,
            raw_nickname="Blocked",
            raw_email="blocked-ml@example.com",
            raw_gender=GuestGender.MALE,
        )
    assert exc_paused.value.error_code == "MASTER_LINK_PAUSED"

    # Super Admin can resume Admin A's link
    resume_master_link(actor=super_admin, master_link_id=ml.id)
    assert inspect_invitation_by_token(raw_token)["claimable"] is True

    # 6. Revoking a claimed individual invitation does NOT replenish master link capacity
    claim2 = claim_invitation(
        raw_token=raw_token,
        raw_nickname="Mika",
        raw_email="mika-ml@example.com",
        raw_gender=GuestGender.MALE,
    )
    ml.refresh_from_db()
    assert ml.claimed_count == 2 and ml.remaining_tickets == 1
    revoke_invitation(actor=admin_a, invitation_id=claim2.invitation.id, reason="Test revoke")
    ml.refresh_from_db()
    assert ml.claimed_count == 2 and ml.remaining_tickets == 1

    # 7. Dashboard stats include claimed master tickets without counting reserved slots as claimed
    client_super = APIClient()
    client_super.force_authenticate(user=super_admin)
    dash = client_super.get("/api/dashboard/").json()
    assert dash["claimed"] == 1  # inv1 is CLAIMED; inv2 was REVOKED; 1 remaining reserved is NOT claimed
    assert dash["quota"]["global_used"] == 4
    assert dash["quota"]["global_remaining"] == 2

    # 8. Permanent close releases ONLY unclaimed capacity (1 ticket), exactly once; inv1 stays valid
    close_master_link(actor=super_admin, master_link_id=ml.id)
    ml.refresh_from_db()
    assert ml.status == MasterLinkStatus.CLOSED
    assert ml.released_tickets == 1
    assert ml.remaining_tickets == 0
    assert get_quota_usage(event=event) == 3  # 1 single unused + 2 master invitations created
    assert get_quota_usage(event=event, actor=admin_a) == 3

    # Calling close a second time is idempotent and releases nothing extra
    close_master_link(actor=super_admin, master_link_id=ml.id)
    ml.refresh_from_db()
    assert ml.released_tickets == 1
    assert get_quota_usage(event=event, actor=admin_a) == 3

    # Already-claimed inv1 remains valid after closing master link
    inv1.refresh_from_db()
    assert inv1.status == InvitationStatus.CLAIMED
    assert inspect_invitation_by_token(raw_token)["state"] == "MASTER_LINK_CLOSED"

    # CSV export includes Master source
    csv_text = client_super.get("/api/invitations/export/").content.decode("utf-8")
    assert "Source" in csv_text.splitlines()[0]
    assert "Master: VIP Table" in csv_text


@pytest.mark.django_db(transaction=True)
def test_concurrent_master_claims_final_ticket_and_concurrent_mixed_generation():
    event = Event.get_current()
    event.global_invitation_limit = 5
    event.save(update_fields=["global_invitation_limit", "updated_at"])

    super_admin = User.objects.create_superuser(
        email="conc-super@drip.test",
        password="StrongConcPassword!2026",
        display_name="Chief Host",
    )

    # Create a Master Link with 2 tickets; 6 concurrent guests compete for those 2 tickets
    ml_res = create_master_link(actor=super_admin, name="Hot Drop", max_tickets=2)
    raw_tok = ml_res.claim_url.rsplit("/invite/", 1)[1]

    def _attempt_claim(idx: int) -> str:
        close_old_connections()
        try:
            claim_invitation(
                raw_token=raw_tok,
                raw_nickname=f"Guest {idx}",
                raw_email=f"race-ml-{idx}@example.com",
                raw_gender=GuestGender.FEMALE if idx % 2 == 0 else GuestGender.MALE,
            )
            return "OK"
        except ApplicationError as exc:
            return exc.error_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=6) as pool:
        claim_outcomes = list(pool.map(_attempt_claim, range(6)))

    assert claim_outcomes.count("OK") == 2
    assert claim_outcomes.count("MASTER_LINK_EXHAUSTED") == 4

    ml = MasterInvitationLink.objects.get(pk=ml_res.master_link.id)
    assert ml.claimed_count == 2
    assert ml.status == MasterLinkStatus.EXHAUSTED
    assert Invitation.objects.filter(master_link=ml).count() == 2
    assert EmailDelivery.objects.filter(invitation__master_link=ml).count() == 2

    # Concurrent mixed generation (Single + Bulk + Master) competing for the remaining 3 global slots
    def _attempt_generate(kind: str) -> str:
        close_old_connections()
        try:
            if kind == "single":
                generate_invitations(actor=super_admin, quantity=2)
            elif kind == "bulk":
                generate_invitations(actor=super_admin, quantity=2)
            else:
                create_master_link(actor=super_admin, name="Concurrent Master", max_tickets=2)
            return "OK"
        except ApplicationError as exc:
            return exc.error_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=3) as pool:
        gen_outcomes = list(pool.map(_attempt_generate, ["single", "bulk", "master"]))

    # Only ONE 2-ticket generation can fit into the 3 remaining global slots (total limit = 5)
    assert gen_outcomes.count("OK") == 1
    assert gen_outcomes.count("INVITATION_LIMIT_REACHED") == 2
    assert get_quota_usage(event=event) == 4
