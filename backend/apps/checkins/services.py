from __future__ import annotations

import re

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import User
from apps.audit.exceptions import ApplicationError
from apps.audit.services import log_audit_event
from apps.events.models import Event
from apps.invitations.crypto import hash_token
from apps.invitations.models import Invitation, InvitationStatus

from .models import CheckIn, VerificationMethod

QR_PREFIX = "DRIP1:"
# Supports both new random 8-digit references (DR-83729164) and preserved legacy references (DR-000001)
VALID_REFERENCE_RE = re.compile(r"^DR-\d{6,8}$")


def parse_qr_token(raw_payload: str) -> str | None:
    cleaned = (raw_payload or "").strip()
    if not cleaned.startswith(QR_PREFIX):
        return None
    token_part = cleaned[len(QR_PREFIX) :].strip()
    if len(token_part) < 16 or len(token_part) > 128:
        return None
    return token_part


def _format_verification_result(inv: Invitation, *, event: Event, verification_method: str) -> dict[str, object]:
    if not event.admission_enabled:
        return {
            "result_code": "ADMISSION_DISABLED",
            "can_admit": False,
            "message": "Guest admission is currently disabled in event settings.",
            "verification_method": verification_method,
        }

    if inv.status == InvitationStatus.REVOKED:
        return {
            "result_code": "INVITATION_REVOKED",
            "can_admit": False,
            "message": "Admission denied — this invitation has been revoked.",
            "reference": inv.reference,
            "nickname": inv.nickname or None,
            "revoked_at": inv.revoked_at,
            "revocation_reason": inv.revocation_reason,
            "verification_method": verification_method,
        }

    if inv.status != InvitationStatus.CLAIMED:
        return {
            "result_code": "INVALID_INVITATION",
            "can_admit": False,
            "message": f"Invitation {inv.reference} has not been claimed ({inv.effective_status}).",
            "reference": inv.reference,
            "verification_method": verification_method,
        }

    if hasattr(inv, "checkin"):
        ci = inv.checkin
        return {
            "result_code": "ALREADY_ADMITTED",
            "can_admit": False,
            "message": "Guest has already been admitted with this invitation.",
            "invitation_id": str(inv.id),
            "reference": inv.reference,
            "nickname": inv.nickname,
            "guest_email": inv.guest_email,
            "checked_in_at": ci.checked_in_at,
            "verified_by_name": ci.verified_by.display_name if ci.verified_by else "Administrator",
            "previous_method": ci.verification_method,
            "verification_method": verification_method,
        }

    result: dict[str, object] = {
        "result_code": "VALID",
        "can_admit": True,
        "message": "Valid invitation — eligible for one admission.",
        "invitation_id": str(inv.id),
        "reference": inv.reference,
        "nickname": inv.nickname,
        "guest_email": inv.guest_email,
        "status": inv.status,
        "claimed_at": inv.claimed_at,
        "generated_by_name": inv.generated_by.display_name if inv.generated_by else "",
        "verification_method": verification_method,
    }
    if verification_method == VerificationMethod.MANUAL:
        result["manual_warning"] = (
            "Manual reference lookup does not cryptographically verify a QR pass. "
            "Confirm the guest's official PDF invitation and email before admitting."
        )
    return result


def verify_qr_payload(*, raw_payload: str) -> dict[str, object]:
    """Read-only QR verification. NEVER mutates or admits."""
    event = Event.get_current()
    if not event.admission_enabled:
        return {
            "result_code": "ADMISSION_DISABLED",
            "can_admit": False,
            "message": "Guest admission is currently disabled in event settings.",
            "verification_method": VerificationMethod.QR,
        }

    raw_token = parse_qr_token(raw_payload)
    if not raw_token:
        return {
            "result_code": "INVALID_QR_CODE",
            "can_admit": False,
            "message": "Unrecognized QR code payload.",
            "verification_method": VerificationMethod.QR,
        }

    digest = hash_token(raw_token)
    inv = (
        Invitation.objects.select_related("generated_by", "checkin", "checkin__verified_by")
        .filter(event=event, admission_token_digest=digest)
        .first()
    )
    if inv is None:
        return {
            "result_code": "INVALID_QR_CODE",
            "can_admit": False,
            "message": "QR code is invalid or has been superseded by an updated pass.",
            "verification_method": VerificationMethod.QR,
        }

    return _format_verification_result(inv, event=event, verification_method=VerificationMethod.QR)


def verify_manual_reference(*, reference: str) -> dict[str, object]:
    """Read-only manual reference inspection. NEVER mutates or admits."""
    event = Event.get_current()
    cleaned_ref = (reference or "").strip().upper()
    if not cleaned_ref or not VALID_REFERENCE_RE.match(cleaned_ref):
        raise ApplicationError(
            code="VALIDATION_ERROR",
            message="Enter a valid invitation reference (e.g. DR-83729164).",
        )

    inv = (
        Invitation.objects.select_related("generated_by", "checkin", "checkin__verified_by")
        .filter(event=event, reference__iexact=cleaned_ref)
        .first()
    )
    if inv is None:
        return {
            "result_code": "INVALID_INVITATION",
            "can_admit": False,
            "message": f"No invitation found matching reference {cleaned_ref}.",
            "verification_method": VerificationMethod.MANUAL,
        }

    return _format_verification_result(inv, event=event, verification_method=VerificationMethod.MANUAL)


def admit_guest(
    *,
    actor: User,
    verification_method: str,
    qr_payload: str = "",
    reference: str = "",
    confirm_manual: bool = False,
    notes: str = "",
    request=None,
) -> CheckIn:
    if verification_method not in VerificationMethod.values:
        raise ApplicationError(code="VALIDATION_ERROR", message="Invalid verification method.")

    if verification_method == VerificationMethod.MANUAL and not confirm_manual:
        raise ApplicationError(
            code="MANUAL_CONFIRMATION_REQUIRED",
            message="Explicit staff confirmation is required for manual admission.",
        )

    # Canonical lock ordering: Event -> Invitation
    with transaction.atomic():
        event = Event.get_current(lock=True)
        if not event.admission_enabled:
            raise ApplicationError(
                code="ADMISSION_DISABLED",
                message="Guest admission is currently disabled in event settings.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        if verification_method == VerificationMethod.QR:
            raw_token = parse_qr_token(qr_payload)
            if not raw_token:
                raise ApplicationError(
                    code="INVALID_QR_CODE",
                    message="Unrecognized QR code payload.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            digest = hash_token(raw_token)
            inv = (
                Invitation.objects.select_for_update()
                .filter(event=event, admission_token_digest=digest)
                .first()
            )
            if inv is None:
                raise ApplicationError(
                    code="INVALID_QR_CODE",
                    message="QR code is invalid or has been superseded.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
        else:
            cleaned_ref = reference.strip().upper()
            inv = (
                Invitation.objects.select_for_update()
                .filter(event=event, reference__iexact=cleaned_ref)
                .first()
            )
            if inv is None:
                raise ApplicationError(
                    code="INVALID_INVITATION",
                    message="Invitation reference not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

        if inv.status == InvitationStatus.REVOKED:
            raise ApplicationError(
                code="INVITATION_REVOKED",
                message="Admission denied — this invitation has been revoked.",
                status_code=status.HTTP_409_CONFLICT,
            )

        if inv.status != InvitationStatus.CLAIMED:
            raise ApplicationError(
                code="INVALID_INVITATION",
                message="Only claimed invitations are eligible for admission.",
                status_code=status.HTTP_409_CONFLICT,
            )

        existing = CheckIn.objects.select_related("verified_by").filter(invitation=inv).first()
        if existing is not None:
            raise ApplicationError(
                code="ALREADY_ADMITTED",
                message="This guest has already been admitted.",
                status_code=status.HTTP_409_CONFLICT,
                details={
                    "reference": inv.reference,
                    "nickname": inv.nickname,
                    "checked_in_at": existing.checked_in_at.isoformat(),
                    "verified_by_name": existing.verified_by.display_name,
                },
            )

        try:
            with transaction.atomic():
                checkin = CheckIn.objects.create(
                    invitation=inv,
                    verified_by=actor,
                    checked_in_at=timezone.now(),
                    verification_method=verification_method,
                    notes=notes.strip()[:240],
                )
        except IntegrityError as exc:
            raise ApplicationError(
                code="ALREADY_ADMITTED",
                message="This guest has already been admitted.",
                status_code=status.HTTP_409_CONFLICT,
            ) from exc

        log_audit_event(
            actor=actor,
            action_type="GUEST_ADMITTED_MANUAL" if verification_method == VerificationMethod.MANUAL else "GUEST_ADMITTED_QR",
            target_type="Invitation",
            target_id=inv.reference,
            metadata={
                "verification_method": verification_method,
                "notes": checkin.notes,
            },
            request=request,
        )
        return checkin
