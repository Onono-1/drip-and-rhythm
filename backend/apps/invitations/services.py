from __future__ import annotations

import datetime
import re
import secrets
import unicodedata
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import User
from apps.audit.exceptions import ApplicationError
from apps.audit.services import log_audit_event
from apps.events.models import Event

from .crypto import decrypt_token, encrypt_token, generate_secure_token, hash_token
from .models import (
    ClaimReceipt,
    GuestGender,
    Invitation,
    InvitationStatus,
    compute_claim_receipt_expiry,
)

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(FORMULA_PREFIXES):
        return f"'{text}"
    return text


def validate_guest_nickname(raw_nickname: str) -> str:
    if not isinstance(raw_nickname, str):
        raise ApplicationError(
            code="VALIDATION_ERROR",
            message="Please enter a valid nickname.",
            details={"nickname": ["Nickname is required."]},
        )
    trimmed = raw_nickname.strip()
    if not trimmed:
        raise ApplicationError(
            code="VALIDATION_ERROR",
            message="Please enter your nickname.",
            details={"nickname": ["Nickname cannot be empty."]},
        )
    if len(trimmed) > 50:
        raise ApplicationError(
            code="VALIDATION_ERROR",
            message="Nickname must be 50 characters or fewer.",
            details={"nickname": ["Nickname must be 50 characters or fewer."]},
        )
    for ch in trimmed:
        cat = unicodedata.category(ch)
        if cat.startswith("C"):
            raise ApplicationError(
                code="VALIDATION_ERROR",
                message="Nickname contains unsupported control characters.",
                details={"nickname": ["Control or invisible formatting characters are not allowed."]},
            )
    if "<" in trimmed or ">" in trimmed:
        raise ApplicationError(
            code="VALIDATION_ERROR",
            message="Nickname cannot contain HTML brackets.",
            details={"nickname": ["HTML angle brackets are not allowed."]},
        )
    return re.sub(r"\s{2,}", " ", trimmed)


def normalize_guest_email(raw_email: str) -> tuple[str, str]:
    if not isinstance(raw_email, str):
        raise ApplicationError(
            code="VALIDATION_ERROR",
            message="Please enter a valid email address.",
            details={"email": ["Email address is required."]},
        )
    cleaned = raw_email.strip()
    if not cleaned or "@" not in cleaned or len(cleaned) > 254:
        raise ApplicationError(
            code="VALIDATION_ERROR",
            message="Please enter a valid email address.",
            details={"email": ["Enter a valid email address."]},
        )
    local_part, domain_part = cleaned.rsplit("@", 1)
    try:
        idna_domain = domain_part.strip().lower().encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ApplicationError(
            code="VALIDATION_ERROR",
            message="Email domain is invalid.",
            details={"email": ["Email domain is invalid."]},
        ) from exc

    normalized_candidate = f"{local_part.strip().lower()}@{idna_domain}"
    try:
        validate_email(normalized_candidate)
    except DjangoValidationError as exc:
        raise ApplicationError(
            code="VALIDATION_ERROR",
            message="Please enter a valid email address.",
            details={"email": ["Enter a valid email address."]},
        ) from exc

    display_email = f"{local_part.strip()}@{domain_part.strip().lower()}"
    return display_email, normalized_candidate


def build_claim_url(raw_token: str) -> str:
    return f"{settings.APP_BASE_URL}/invite/{raw_token}"


def build_share_url(raw_token: str) -> str:
    return f"{settings.APP_BASE_URL}/share/{raw_token}"


def get_recoverable_claim_url(invitation: Invitation) -> str | None:
    if invitation.effective_status != InvitationStatus.UNUSED or not invitation.claim_token_encrypted:
        return None
    try:
        raw_token = decrypt_token(invitation.claim_token_encrypted)
        return build_claim_url(raw_token) if raw_token else None
    except ValueError:
        return None


def get_recoverable_share_token(invitation: Invitation) -> str | None:
    if not invitation.share_token_encrypted:
        return None
    try:
        return decrypt_token(invitation.share_token_encrypted) or None
    except ValueError:
        return None


REFERENCE_PATTERN = re.compile(r"^DR-\d{6,8}$", re.IGNORECASE)
MAX_REFERENCE_GENERATION_ATTEMPTS = 25


def generate_random_invitation_reference() -> str:
    """Generate a non-sequential DR-XXXXXXXX reference using CSPRNG randomness."""
    digits = 10_000_000 + secrets.randbelow(90_000_000)
    return f"DR-{digits:08d}"


def _create_invitation_with_unique_reference(
    *,
    event: Event,
    actor: User,
    now: datetime.datetime,
    expires_at: datetime.datetime | None,
    used_in_batch: set[str],
) -> tuple[Invitation, str]:
    raw_claim_token = generate_secure_token()
    claim_digest = hash_token(raw_claim_token)
    claim_encrypted = encrypt_token(raw_claim_token)

    for _ in range(MAX_REFERENCE_GENERATION_ATTEMPTS):
        candidate_ref = generate_random_invitation_reference()
        if candidate_ref in used_in_batch:
            continue
        try:
            with transaction.atomic():
                inv = Invitation.objects.create(
                    event=event,
                    reference_number=None,
                    reference=candidate_ref,
                    claim_token_digest=claim_digest,
                    claim_token_encrypted=claim_encrypted,
                    status=InvitationStatus.UNUSED,
                    generated_by=actor,
                    generated_at=now,
                    expires_at=expires_at,
                )
            used_in_batch.add(candidate_ref)
            return inv, build_claim_url(raw_claim_token)
        except IntegrityError:
            continue

    raise ApplicationError(
        code="REFERENCE_GENERATION_FAILED",
        message="Unable to allocate a unique invitation reference. Please retry.",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@dataclass
class GeneratedBatchResult:
    invitations: list[tuple[Invitation, str]]
    remaining_global_quota: int | None
    remaining_admin_quota: int | None


def generate_invitations(
    *,
    actor: User,
    quantity: int = 1,
    expires_at: datetime.datetime | None = None,
    request=None,
) -> GeneratedBatchResult:
    if quantity < 1:
        raise ApplicationError(code="VALIDATION_ERROR", message="Quantity must be at least 1.")

    if expires_at is not None and expires_at <= timezone.now():
        raise ApplicationError(
            code="VALIDATION_ERROR",
            message="Expiration time must be in the future.",
            details={"expires_at": ["Expiration time must be in the future."]},
        )

    # Canonical lock ordering: Event -> User -> Invitation
    with transaction.atomic():
        event = Event.get_current(lock=True)
        locked_actor = User.objects.select_for_update().get(pk=actor.pk)
        if not locked_actor.is_active:
            raise ApplicationError(
                code="ACCOUNT_DEACTIVATED",
                message="Your administrator account is deactivated.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        if quantity > event.max_bulk_quantity:
            raise ApplicationError(
                code="VALIDATION_ERROR",
                message=f"Cannot generate more than {event.max_bulk_quantity} invitations in a single request.",
                details={"quantity": [f"Maximum batch size is {event.max_bulk_quantity}."]},
            )

        global_issued = Invitation.objects.filter(event=event).count()
        if event.global_invitation_limit is not None:
            remaining_global = max(0, event.global_invitation_limit - global_issued)
            if quantity > remaining_global:
                raise ApplicationError(
                    code="INVITATION_LIMIT_REACHED",
                    message=(
                        f"Requested {quantity} links, but only {remaining_global} remain in the global event quota."
                    ),
                    status_code=status.HTTP_409_CONFLICT,
                    details={"remaining_global_quota": remaining_global},
                )

        admin_issued = Invitation.objects.filter(event=event, generated_by=locked_actor).count()
        if locked_actor.invitation_limit is not None:
            remaining_admin = max(0, locked_actor.invitation_limit - admin_issued)
            if quantity > remaining_admin:
                raise ApplicationError(
                    code="INVITATION_LIMIT_REACHED",
                    message=(
                        f"Requested {quantity} links, but only {remaining_admin} remain in your administrator quota."
                    ),
                    status_code=status.HTTP_409_CONFLICT,
                    details={"remaining_admin_quota": remaining_admin},
                )

        created_pairs: list[tuple[Invitation, str]] = []
        used_in_batch: set[str] = set()
        now = timezone.now()
        for _ in range(quantity):
            pair = _create_invitation_with_unique_reference(
                event=event,
                actor=locked_actor,
                now=now,
                expires_at=expires_at,
                used_in_batch=used_in_batch,
            )
            created_pairs.append(pair)

        new_global_remaining = (
            max(0, event.global_invitation_limit - (global_issued + quantity))
            if event.global_invitation_limit is not None
            else None
        )
        new_admin_remaining = (
            max(0, locked_actor.invitation_limit - (admin_issued + quantity))
            if locked_actor.invitation_limit is not None
            else None
        )

        log_audit_event(
            actor=locked_actor,
            action_type="INVITATION_BULK_GENERATED" if quantity > 1 else "INVITATION_GENERATED",
            target_type="Invitation",
            target_id=created_pairs[0][0].reference if quantity == 1 else f"batch:{quantity}",
            metadata={
                "quantity": quantity,
                "first_reference": created_pairs[0][0].reference,
                "last_reference": created_pairs[-1][0].reference,
            },
            request=request,
        )

        return GeneratedBatchResult(
            invitations=created_pairs,
            remaining_global_quota=new_global_remaining,
            remaining_admin_quota=new_admin_remaining,
        )


def inspect_invitation_by_token(raw_token: str) -> dict[str, object]:
    """Read-only validation for GET /api/invite/{token}/. NEVER consumes or mutates state."""
    event = Event.get_current()
    digest = hash_token(raw_token)
    inv = Invitation.objects.filter(event=event, claim_token_digest=digest).first()
    now = timezone.now()

    if inv is None:
        return {"state": "INVALID_INVITATION", "claimable": False, "event": event}

    if inv.status == InvitationStatus.REVOKED:
        return {"state": "INVITATION_REVOKED", "claimable": False, "event": event}

    if inv.status == InvitationStatus.CLAIMED:
        return {"state": "INVITATION_ALREADY_CLAIMED", "claimable": False, "event": event}

    if (
        inv.status == InvitationStatus.EXPIRED
        or (inv.expires_at and inv.expires_at <= now)
        or (event.claim_deadline and event.claim_deadline <= now)
    ):
        return {"state": "INVITATION_EXPIRED", "claimable": False, "event": event}

    if not event.claiming_enabled:
        return {"state": "CLAIMING_DISABLED", "claimable": False, "event": event}

    return {
        "state": "VALID_UNUSED",
        "claimable": True,
        "expires_at": inv.expires_at,
        "event": event,
    }


@dataclass
class ClaimSuccessResult:
    invitation: Invitation
    raw_receipt_token: str
    receipt_expires_at: datetime.datetime
    raw_share_token: str


def validate_guest_gender(raw_gender: str | None) -> str:
    value = (raw_gender or "").strip().upper()
    if value not in GuestGender.values:
        raise ApplicationError(
            code="VALIDATION_ERROR",
            message="Please select Male or Female.",
            details={"gender": ["Please select Male or Female."]},
        )
    return value


def claim_invitation(
    *,
    raw_token: str,
    raw_nickname: str,
    raw_email: str,
    raw_gender: str,
) -> ClaimSuccessResult:
    nickname = validate_guest_nickname(raw_nickname)
    display_email, normalized_email = normalize_guest_email(raw_email)
    gender = validate_guest_gender(raw_gender)
    digest = hash_token(raw_token)
    now = timezone.now()

    # Canonical lock ordering: Event -> Invitation -> EmailDelivery
    with transaction.atomic():
        event = Event.get_current(lock=True)
        inv = Invitation.objects.select_for_update().filter(event=event, claim_token_digest=digest).first()

        if inv is None:
            raise ApplicationError(
                code="INVALID_INVITATION",
                message="This invitation link is invalid or not recognized.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if inv.status == InvitationStatus.REVOKED:
            raise ApplicationError(
                code="INVITATION_REVOKED",
                message="This invitation has been revoked and can no longer be used.",
                status_code=status.HTTP_410_GONE,
            )

        if inv.status == InvitationStatus.CLAIMED:
            raise ApplicationError(
                code="INVITATION_ALREADY_CLAIMED",
                message="This invitation link has already been claimed.",
                status_code=status.HTTP_409_CONFLICT,
            )

        if (
            inv.status == InvitationStatus.EXPIRED
            or (inv.expires_at and inv.expires_at <= now)
            or (event.claim_deadline and event.claim_deadline <= now)
        ):
            if inv.status == InvitationStatus.UNUSED and inv.expires_at and inv.expires_at <= now:
                inv.status = InvitationStatus.EXPIRED
                inv.claim_token_encrypted = ""
                inv.save(update_fields=["status", "claim_token_encrypted", "updated_at"])
            raise ApplicationError(
                code="INVITATION_EXPIRED",
                message="This invitation link has expired.",
                status_code=status.HTTP_410_GONE,
            )

        if not event.claiming_enabled:
            raise ApplicationError(
                code="CLAIMING_DISABLED",
                message="Invitation claiming is currently paused. Please try again later.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Pre-check email uniqueness before modifying the unused invitation
        if Invitation.objects.filter(event=event, guest_email_normalized=normalized_email).exists():
            raise ApplicationError(
                code="DUPLICATE_EMAIL",
                message=(
                    "An invitation has already been registered using this email address. "
                    "Please check your inbox or spam folder for your official admission pass."
                ),
                status_code=status.HTTP_409_CONFLICT,
            )

        raw_admission_token = generate_secure_token()
        raw_share_token = generate_secure_token()
        raw_receipt_token = generate_secure_token()
        receipt_expires_at = compute_claim_receipt_expiry(event, claimed_at=now)

        try:
            with transaction.atomic():
                inv.nickname = nickname
                inv.guest_email = display_email
                inv.guest_email_normalized = normalized_email
                inv.gender = gender
                inv.status = InvitationStatus.CLAIMED
                inv.claimed_at = now
                inv.claim_token_encrypted = ""
                inv.admission_token_digest = hash_token(raw_admission_token)
                inv.admission_token_encrypted = encrypt_token(raw_admission_token)
                inv.admission_credential_version = 1
                inv.share_token_digest = hash_token(raw_share_token)
                inv.share_token_encrypted = encrypt_token(raw_share_token)
                inv.sharing_version = 1
                inv.show_nickname_publicly = False
                inv.public_sharing_enabled = True
                inv.save()
        except IntegrityError as exc:
            raise ApplicationError(
                code="DUPLICATE_EMAIL",
                message=(
                    "An invitation has already been registered using this email address. "
                    "Please check your inbox or spam folder for your official admission pass."
                ),
                status_code=status.HTTP_409_CONFLICT,
            ) from exc

        ClaimReceipt.objects.create(
            invitation=inv,
            token_digest=hash_token(raw_receipt_token),
            credential_version=inv.admission_credential_version,
            expires_at=receipt_expires_at,
        )

        from apps.communications.services import enqueue_invitation_email

        enqueue_invitation_email(
            invitation=inv,
            email_type="INVITATION_PASS",
            idempotency_key=f"inv-{inv.id}-v{inv.admission_credential_version}-initial",
        )

        return ClaimSuccessResult(
            invitation=inv,
            raw_receipt_token=raw_receipt_token,
            receipt_expires_at=receipt_expires_at,
            raw_share_token=raw_share_token,
        )


def assert_can_manage_invitation(actor: User, invitation: Invitation) -> None:
    if actor.is_super_admin:
        return
    if invitation.generated_by_id != actor.id:
        raise ApplicationError(
            code="PERMISSION_DENIED",
            message="Ordinary administrators can only manage invitations they generated.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


def revoke_invitation(*, actor: User, invitation_id, reason: str = "", request=None) -> Invitation:
    now = timezone.now()
    # Canonical lock ordering: Event -> Invitation -> EmailDelivery
    with transaction.atomic():
        Event.get_current(lock=True)
        inv = Invitation.objects.select_for_update().filter(pk=invitation_id).first()
        if inv is None:
            raise ApplicationError(
                code="NOT_FOUND",
                message="Invitation not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        assert_can_manage_invitation(actor, inv)

        if hasattr(inv, "checkin"):
            raise ApplicationError(
                code="ALREADY_ADMITTED",
                message="Cannot revoke an invitation after the guest has already been admitted.",
                status_code=status.HTTP_409_CONFLICT,
            )

        if inv.status == InvitationStatus.REVOKED:
            return inv

        inv.status = InvitationStatus.REVOKED
        inv.revoked_at = now
        inv.revoked_by = actor
        inv.revocation_reason = reason.strip()[:240]
        inv.claim_token_encrypted = ""
        inv.admission_token_encrypted = ""
        inv.public_sharing_enabled = False
        inv.sharing_version += 1
        inv.save()

        ClaimReceipt.objects.filter(invitation=inv, revoked_at__isnull=True).update(revoked_at=now)

        from apps.communications.models import EmailDelivery, EmailStatus

        EmailDelivery.objects.filter(
            invitation=inv,
            status__in=[EmailStatus.PENDING, EmailStatus.FAILED],
        ).update(status=EmailStatus.CANCELLED, failure_reason="Invitation revoked before delivery.")

        log_audit_event(
            actor=actor,
            action_type="INVITATION_REVOKED",
            target_type="Invitation",
            target_id=inv.reference,
            metadata={"reason": inv.revocation_reason},
            request=request,
        )
        return inv


def correct_guest_information(
    *,
    actor: User,
    invitation_id,
    new_nickname: str | None = None,
    new_email: str | None = None,
    new_gender: str | None = None,
    resend_after_nickname_change: bool = True,
    request=None,
) -> Invitation:
    if not actor.is_super_admin:
        raise ApplicationError(
            code="PERMISSION_DENIED",
            message="Only a super administrator can correct guest information.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    now = timezone.now()
    # Canonical lock ordering: Event -> Invitation -> EmailDelivery
    with transaction.atomic():
        event = Event.get_current(lock=True)
        inv = Invitation.objects.select_for_update().filter(event=event, pk=invitation_id).first()
        if inv is None:
            raise ApplicationError(
                code="NOT_FOUND",
                message="Invitation not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if inv.status != InvitationStatus.CLAIMED:
            raise ApplicationError(
                code="VALIDATION_ERROR",
                message="Guest details can only be corrected on claimed, active invitations.",
            )
        if hasattr(inv, "checkin"):
            raise ApplicationError(
                code="ALREADY_ADMITTED",
                message="Cannot modify guest information after the guest has already been admitted.",
                status_code=status.HTTP_409_CONFLICT,
            )

        changed_nickname = False
        changed_email = False
        changed_gender = False

        if new_nickname is not None:
            validated_nick = validate_guest_nickname(new_nickname)
            if validated_nick != inv.nickname:
                inv.nickname = validated_nick
                changed_nickname = True

        if new_email is not None:
            display_email, normalized_email = normalize_guest_email(new_email)
            if normalized_email != inv.guest_email_normalized:
                if (
                    Invitation.objects.filter(event=event, guest_email_normalized=normalized_email)
                    .exclude(pk=inv.pk)
                    .exists()
                ):
                    raise ApplicationError(
                        code="DUPLICATE_EMAIL",
                        message="Another invitation is already registered with that email address.",
                        status_code=status.HTTP_409_CONFLICT,
                    )
                inv.guest_email = display_email
                inv.guest_email_normalized = normalized_email
                changed_email = True

        if new_gender is not None:
            validated_gender = validate_guest_gender(new_gender)
            if validated_gender != inv.gender:
                inv.gender = validated_gender
                changed_gender = True

        if not changed_nickname and not changed_email and not changed_gender:
            return inv

        from apps.communications.models import EmailDelivery, EmailStatus
        from apps.communications.services import enqueue_invitation_email

        if changed_email:
            # Rotate admission credential + invalidate previous QR, claim receipts, share credential, and pending jobs
            new_admission_token = generate_secure_token()
            new_share_token = generate_secure_token()
            inv.admission_credential_version += 1
            inv.admission_token_digest = hash_token(new_admission_token)
            inv.admission_token_encrypted = encrypt_token(new_admission_token)
            inv.share_token_digest = hash_token(new_share_token)
            inv.share_token_encrypted = encrypt_token(new_share_token)
            inv.sharing_version += 1
            inv.save()

            ClaimReceipt.objects.filter(invitation=inv, revoked_at__isnull=True).update(revoked_at=now)
            EmailDelivery.objects.filter(
                invitation=inv,
                status__in=[EmailStatus.PENDING, EmailStatus.FAILED],
            ).update(
                status=EmailStatus.CANCELLED,
                failure_reason="Superseded by guest email correction and credential rotation.",
            )

            enqueue_invitation_email(
                invitation=inv,
                email_type="INVITATION_CORRECTED",
                idempotency_key=f"inv-{inv.id}-v{inv.admission_credential_version}-email-corrected",
            )
        elif changed_nickname:
            inv.sharing_version += 1
            inv.save()
            if resend_after_nickname_change:
                enqueue_invitation_email(
                    invitation=inv,
                    email_type="INVITATION_CORRECTED",
                    idempotency_key=f"inv-{inv.id}-v{inv.admission_credential_version}-nick-{int(now.timestamp())}",
                )
        else:
            # Gender is private and excluded from emails/PDFs/artwork; save without rotating credentials or resending
            inv.save(update_fields=["gender", "updated_at"])

        log_audit_event(
            actor=actor,
            action_type="GUEST_INFO_CORRECTED",
            target_type="Invitation",
            target_id=inv.reference,
            metadata={
                "changed_nickname": changed_nickname,
                "changed_email": changed_email,
                "changed_gender": changed_gender,
                "new_credential_version": inv.admission_credential_version,
            },
            request=request,
        )
        return inv


def resolve_valid_claim_receipt(raw_cookie_token: str | None) -> ClaimReceipt:
    if not raw_cookie_token:
        raise ApplicationError(
            code="CLAIM_RECEIPT_REQUIRED",
            message="No active invitation confirmation session was found in this browser.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    digest = hash_token(raw_cookie_token)
    receipt = (
        ClaimReceipt.objects.select_related("invitation", "invitation__event")
        .filter(token_digest=digest)
        .first()
    )
    if receipt is None or not receipt.is_currently_valid():
        raise ApplicationError(
            code="CLAIM_RECEIPT_INVALID",
            message="Your invitation confirmation session has expired or is no longer valid.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return receipt
