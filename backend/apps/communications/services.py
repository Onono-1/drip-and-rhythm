from __future__ import annotations

import base64
import json
import logging
from datetime import timedelta
from pathlib import Path

import resend
from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from rest_framework import status
from svix.webhooks import Webhook, WebhookVerificationError

from apps.accounts.models import User
from apps.audit.exceptions import ApplicationError
from apps.audit.services import log_audit_event
from apps.invitations.crypto import decrypt_token, encrypt_token
from apps.invitations.models import Invitation, InvitationStatus
from apps.invitations.services import (
    assert_can_manage_invitation,
    build_share_url,
    get_recoverable_share_token,
)

from .email_templates import build_invitation_email_content, build_password_reset_email_content
from .models import EmailDelivery, EmailStatus, EmailType, WebhookEvent
from .pdf_pass import generate_admission_pass_pdf

logger = logging.getLogger(__name__)

MONOTONIC_RANK = {
    EmailStatus.PENDING: 1,
    EmailStatus.PROCESSING: 2,
    EmailStatus.SENT: 3,
    EmailStatus.DELIVERED: 4,
    EmailStatus.BOUNCED: 5,
    EmailStatus.FAILED: 2,
    EmailStatus.CANCELLED: 6,
}


def schedule_post_commit_email_dispatch(job_id) -> None:
    """
    In workerless free-tier mode (EMAIL_INLINE_DISPATCH=True), attempt delivery
    immediately *after* the enclosing database transaction commits. External
    provider calls never occur inside the claim/resend/reset transaction, and
    any delivery error is absorbed and persisted on EmailDelivery.
    """
    if not getattr(settings, "EMAIL_INLINE_DISPATCH", False):
        return
    transaction.on_commit(lambda: dispatch_email_job_inline(job_id))


def enqueue_invitation_email(
    *,
    invitation: Invitation,
    email_type: str = EmailType.INVITATION_PASS,
    idempotency_key: str,
) -> EmailDelivery:
    delivery = EmailDelivery.objects.create(
        invitation=invitation,
        email_type=email_type,
        recipient_email=invitation.guest_email,
        admission_credential_version=invitation.admission_credential_version,
        status=EmailStatus.PENDING,
        provider=settings.EMAIL_DELIVERY_MODE,
        idempotency_key=idempotency_key,
        max_attempts=settings.EMAIL_MAX_RETRIES,
        next_retry_at=timezone.now(),
    )
    schedule_post_commit_email_dispatch(delivery.id)
    return delivery


def enqueue_password_reset_email(*, user: User, reset_url: str, reset_id: str) -> EmailDelivery:
    delivery = EmailDelivery.objects.create(
        invitation=None,
        email_type=EmailType.PASSWORD_RESET,
        recipient_email=user.email,
        context_payload={
            "display_name": user.display_name,
            "reset_url_encrypted": encrypt_token(reset_url),
        },
        status=EmailStatus.PENDING,
        provider=settings.EMAIL_DELIVERY_MODE,
        idempotency_key=f"pw-reset-{reset_id}",
        max_attempts=3,
        next_retry_at=timezone.now(),
    )
    schedule_post_commit_email_dispatch(delivery.id)
    return delivery


def admin_resend_invitation_email(*, actor: User, invitation_id, request=None) -> EmailDelivery:
    now = timezone.now()
    with transaction.atomic():
        inv = Invitation.objects.select_for_update().filter(pk=invitation_id).first()
        if inv is None:
            raise ApplicationError(
                code="NOT_FOUND",
                message="Invitation not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        assert_can_manage_invitation(actor, inv)
        if inv.status != InvitationStatus.CLAIMED:
            raise ApplicationError(
                code="VALIDATION_ERROR",
                message="Only claimed, active invitations can be resent.",
                status_code=status.HTTP_409_CONFLICT,
            )

        resend_count = inv.email_deliveries.filter(email_type=EmailType.INVITATION_RESEND).count() + 1
        delivery = enqueue_invitation_email(
            invitation=inv,
            email_type=EmailType.INVITATION_RESEND,
            idempotency_key=f"inv-{inv.id}-v{inv.admission_credential_version}-resend-{resend_count}-{int(now.timestamp())}",
        )
        log_audit_event(
            actor=actor,
            action_type="INVITATION_EMAIL_RESENT",
            target_type="Invitation",
            target_id=inv.reference,
            metadata={"delivery_id": str(delivery.id)},
            request=request,
        )
        return delivery


def acquire_next_email_job(worker_id: str) -> EmailDelivery | None:
    now = timezone.now()
    lease_until = now + timedelta(seconds=settings.EMAIL_WORKER_LEASE_SECONDS)
    with transaction.atomic():
        job = (
            EmailDelivery.objects.select_for_update(skip_locked=True)
            .filter(
                models.Q(status=EmailStatus.PENDING, next_retry_at__lte=now)
                | models.Q(status=EmailStatus.PROCESSING, lease_expires_at__lte=now)
            )
            .order_by("next_retry_at", "created_at")
            .first()
        )
        if job is None:
            return None

        if job.attempt_count >= job.max_attempts:
            job.status = EmailStatus.FAILED
            job.lease_expires_at = None
            job.failure_reason = job.failure_reason or "Exceeded maximum retry attempts after worker lease expiry."
            job.save(update_fields=["status", "lease_expires_at", "failure_reason", "updated_at"])
            return None

        job.status = EmailStatus.PROCESSING
        job.attempt_count += 1
        job.lease_expires_at = lease_until
        job.worker_id = worker_id
        job.last_attempted_at = now
        job.save(
            update_fields=[
                "status",
                "attempt_count",
                "lease_expires_at",
                "worker_id",
                "last_attempted_at",
                "updated_at",
            ]
        )
        return job


def acquire_email_job_by_id(job_id, worker_id: str) -> EmailDelivery | None:
    now = timezone.now()
    lease_until = now + timedelta(seconds=settings.EMAIL_WORKER_LEASE_SECONDS)
    with transaction.atomic():
        job = (
            EmailDelivery.objects.select_for_update(skip_locked=True)
            .filter(
                pk=job_id,
                status=EmailStatus.PENDING,
            )
            .first()
        )
        if job is None or job.attempt_count >= job.max_attempts:
            return None

        job.status = EmailStatus.PROCESSING
        job.attempt_count += 1
        job.lease_expires_at = lease_until
        job.worker_id = worker_id
        job.last_attempted_at = now
        job.save(
            update_fields=[
                "status",
                "attempt_count",
                "lease_expires_at",
                "worker_id",
                "last_attempted_at",
                "updated_at",
            ]
        )
        return job


def dispatch_email_job_inline(job_id) -> EmailDelivery | None:
    """Best-effort post-commit dispatch; never raises to callers."""
    try:
        job = acquire_email_job_by_id(job_id, "inline-post-commit")
        if job is None:
            return None
        return process_acquired_email_job(job)
    except Exception as exc:
        logger.warning("Inline post-commit dispatch failed for job %s: %s", job_id, type(exc).__name__)
        return None


def admin_process_pending_emails(
    *,
    actor: User,
    max_jobs: int = 10,
    include_failed: bool = True,
    request=None,
) -> dict[str, int]:
    """
    Bounded, authenticated admin trigger to retry pending/failed email jobs on
    free-tier deployments where no always-on background worker is running.
    """
    now = timezone.now()
    bounded_limit = max(1, min(int(max_jobs), 25))

    if include_failed:
        with transaction.atomic():
            EmailDelivery.objects.filter(status=EmailStatus.FAILED).update(
                status=EmailStatus.PENDING,
                attempt_count=0,
                next_retry_at=now,
                lease_expires_at=None,
            )

    # Make any backed-off pending jobs immediately eligible for this manual retry pass
    EmailDelivery.objects.filter(
        status=EmailStatus.PENDING,
        next_retry_at__gt=now,
    ).update(next_retry_at=now)

    counts = {"processed": 0, "sent": 0, "failed": 0, "cancelled": 0}
    worker_id = f"admin-manual-{actor.id}"
    for _ in range(bounded_limit):
        job = acquire_next_email_job(worker_id)
        if job is None:
            break
        updated = process_acquired_email_job(job)
        counts["processed"] += 1
        if updated.status in {EmailStatus.SENT, EmailStatus.DELIVERED}:
            counts["sent"] += 1
        elif updated.status == EmailStatus.CANCELLED:
            counts["cancelled"] += 1
        else:
            counts["failed"] += 1

    counts["remaining_pending"] = EmailDelivery.objects.filter(
        status__in=[EmailStatus.PENDING, EmailStatus.FAILED]
    ).count()

    log_audit_event(
        actor=actor,
        action_type="EMAIL_QUEUE_MANUAL_RETRY",
        target_type="EmailDelivery",
        target_id="batch",
        metadata=counts,
        request=request,
    )
    return counts


def _send_via_provider(
    *,
    job: EmailDelivery,
    subject: str,
    html_body: str,
    text_body: str,
    attachments: list[tuple[str, bytes]],
) -> tuple[str, str]:
    mode = settings.EMAIL_DELIVERY_MODE
    if mode == "resend":
        if not settings.RESEND_API_KEY:
            raise RuntimeError("RESEND_API_KEY is not set while EMAIL_DELIVERY_MODE=resend.")
        resend.api_key = settings.RESEND_API_KEY
        from_header = f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>"
        params: dict[str, object] = {
            "from": from_header,
            "to": [job.recipient_email],
            "subject": subject,
            "html": html_body,
            "text": text_body,
        }
        if settings.RESEND_REPLY_TO_EMAIL:
            params["reply_to"] = settings.RESEND_REPLY_TO_EMAIL
        if attachments:
            params["attachments"] = [
                {
                    "filename": fname,
                    "content": base64.b64encode(content).decode("ascii"),
                }
                for fname, content in attachments
            ]
        resp = resend.Emails.send(params, options={"idempotency_key": job.idempotency_key})
        msg_id = resp.get("id", "") if isinstance(resp, dict) else getattr(resp, "id", "")
        return "resend", str(msg_id)

    # Local file + metadata sink for deterministic non-live development & automated verification
    out_dir = Path(settings.LOCAL_DEV_OUTPUT_DIR) / str(job.id)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "email.html").write_text(html_body, encoding="utf-8")
    (out_dir / "email.txt").write_text(text_body, encoding="utf-8")
    meta = {
        "job_id": str(job.id),
        "to": job.recipient_email,
        "subject": subject,
        "idempotency_key": job.idempotency_key,
        "attachments": [fname for fname, _ in attachments],
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    for fname, content in attachments:
        (out_dir / fname).write_bytes(content)
    return "local", f"local-{job.id}"


def process_acquired_email_job(job: EmailDelivery) -> EmailDelivery:
    try:
        attachments: list[tuple[str, bytes]] = []
        if job.email_type == EmailType.PASSWORD_RESET:
            display_name = str(job.context_payload.get("display_name", "Administrator"))
            encrypted_url = str(job.context_payload.get("reset_url_encrypted", ""))
            reset_url = decrypt_token(encrypted_url)
            subject, html_body, text_body = build_password_reset_email_content(
                display_name=display_name,
                reset_url=reset_url,
            )
        else:
            inv = (
                Invitation.objects.select_related("event")
                .filter(pk=job.invitation_id)
                .first()
            )
            if inv is None or inv.status != InvitationStatus.CLAIMED:
                job.status = EmailStatus.CANCELLED
                job.lease_expires_at = None
                job.failure_reason = "Invitation was revoked or unavailable prior to dispatch."
                job.save(update_fields=["status", "lease_expires_at", "failure_reason", "updated_at"])
                return job

            if (
                job.admission_credential_version is not None
                and inv.admission_credential_version != job.admission_credential_version
            ):
                job.status = EmailStatus.CANCELLED
                job.lease_expires_at = None
                job.failure_reason = "Stale admission credential version superseded prior to dispatch."
                job.save(update_fields=["status", "lease_expires_at", "failure_reason", "updated_at"])
                return job

            raw_admission_token = decrypt_token(inv.admission_token_encrypted)
            pdf_filename, pdf_bytes = generate_admission_pass_pdf(
                invitation=inv,
                raw_admission_token=raw_admission_token,
            )
            attachments.append((pdf_filename, pdf_bytes))

            raw_share = get_recoverable_share_token(inv)
            share_url = (
                build_share_url(raw_share)
                if (raw_share and inv.public_sharing_enabled and inv.event.public_sharing_enabled)
                else None
            )
            subject, html_body, text_body = build_invitation_email_content(
                invitation=inv,
                share_url=share_url,
            )

            # Final pre-send recheck to narrow external race window
            inv.refresh_from_db(fields=["status", "admission_credential_version"])
            if inv.status != InvitationStatus.CLAIMED or (
                job.admission_credential_version is not None
                and inv.admission_credential_version != job.admission_credential_version
            ):
                job.status = EmailStatus.CANCELLED
                job.lease_expires_at = None
                job.failure_reason = "Invitation revoked or credential rotated immediately before send."
                job.save(update_fields=["status", "lease_expires_at", "failure_reason", "updated_at"])
                return job

        provider_name, provider_msg_id = _send_via_provider(
            job=job,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            attachments=attachments,
        )
        now = timezone.now()
        with transaction.atomic():
            locked_job = EmailDelivery.objects.select_for_update().get(pk=job.pk)
            if locked_job.status not in {EmailStatus.DELIVERED, EmailStatus.BOUNCED, EmailStatus.CANCELLED}:
                locked_job.status = EmailStatus.SENT
            locked_job.provider = provider_name
            locked_job.provider_message_id = provider_msg_id
            locked_job.sent_at = now
            locked_job.lease_expires_at = None
            locked_job.failure_reason = ""
            locked_job.save()
            return locked_job

    except Exception as exc:
        logger.warning("Email job %s attempt %s failed: %s", job.id, job.attempt_count, type(exc).__name__)
        now = timezone.now()
        with transaction.atomic():
            locked_job = EmailDelivery.objects.select_for_update().get(pk=job.pk)
            locked_job.lease_expires_at = None
            locked_job.failure_reason = str(exc)[:500]
            if locked_job.attempt_count >= locked_job.max_attempts:
                locked_job.status = EmailStatus.FAILED
            else:
                backoff_seconds = min(900, 15 * (2 ** max(0, locked_job.attempt_count - 1)))
                locked_job.status = EmailStatus.PENDING
                locked_job.next_retry_at = now + timedelta(seconds=backoff_seconds)
            locked_job.save()
            return locked_job


def process_resend_webhook(*, raw_body: bytes, headers: dict[str, str]) -> dict[str, str]:
    secret = settings.RESEND_WEBHOOK_SECRET
    if not secret:
        raise ApplicationError(
            code="WEBHOOK_NOT_CONFIGURED",
            message="Webhook secret is not configured.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    svix_headers = {
        "svix-id": headers.get("svix-id", ""),
        "svix-timestamp": headers.get("svix-timestamp", ""),
        "svix-signature": headers.get("svix-signature", ""),
    }
    try:
        wh = Webhook(secret)
        verified = wh.verify(raw_body, svix_headers)
        payload = verified if isinstance(verified, dict) else json.loads(raw_body.decode("utf-8"))
    except (WebhookVerificationError, ValueError, UnicodeDecodeError) as exc:
        raise ApplicationError(
            code="INVALID_WEBHOOK_SIGNATURE",
            message="Webhook signature verification failed.",
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from exc

    svix_id = svix_headers["svix-id"]
    event_type = str(payload.get("type", ""))
    data = payload.get("data") or {}
    email_id = str(data.get("email_id", "")).strip()

    target_status_map = {
        "email.sent": EmailStatus.SENT,
        "email.delivered": EmailStatus.DELIVERED,
        "email.bounced": EmailStatus.BOUNCED,
        "email.complained": EmailStatus.BOUNCED,
        "email.delivery_delayed": EmailStatus.SENT,
    }

    with transaction.atomic():
        try:
            with transaction.atomic():
                WebhookEvent.objects.create(
                    svix_id=svix_id,
                    event_type=event_type,
                    provider_message_id=email_id,
                )
        except IntegrityError:
            return {"status": "duplicate_ignored"}

        new_status = target_status_map.get(event_type)
        if not email_id or not new_status:
            return {"status": "accepted_untracked_event"}

        delivery = (
            EmailDelivery.objects.select_for_update()
            .filter(provider_message_id=email_id)
            .first()
        )
        if delivery is None:
            return {"status": "accepted_unknown_message"}

        current_rank = MONOTONIC_RANK.get(delivery.status, 0)
        incoming_rank = MONOTONIC_RANK.get(new_status, 0)
        if incoming_rank > current_rank:
            delivery.status = new_status
            if new_status == EmailStatus.DELIVERED:
                delivery.delivered_at = timezone.now()
            elif new_status == EmailStatus.BOUNCED:
                bounce_info = data.get("bounce") or {}
                delivery.failure_reason = str(bounce_info.get("message", "Email bounced by recipient server."))[:500]
            delivery.save()

    return {"status": "processed"}
