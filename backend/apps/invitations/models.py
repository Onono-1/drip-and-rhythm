from __future__ import annotations

import datetime
import uuid
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import models
from django.utils import timezone


class InvitationStatus(models.TextChoices):
    UNUSED = "UNUSED", "Unused"
    CLAIMED = "CLAIMED", "Claimed"
    EXPIRED = "EXPIRED", "Expired"
    REVOKED = "REVOKED", "Revoked"


class GuestGender(models.TextChoices):
    MALE = "MALE", "Male"
    FEMALE = "FEMALE", "Female"


def compute_claim_receipt_expiry(event, claimed_at: datetime.datetime | None = None) -> datetime.datetime:
    base_time = claimed_at or timezone.now()
    configured_days = getattr(settings, "CLAIM_RECEIPT_TTL_DAYS", None)
    if isinstance(configured_days, int) and configured_days > 0:
        return base_time + datetime.timedelta(days=configured_days)

    tz_name = getattr(event, "time_zone", "Africa/Kampala") or "Africa/Kampala"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = datetime.UTC

    post_event_day = event.event_date + datetime.timedelta(days=7)
    event_window_end = datetime.datetime.combine(
        post_event_day,
        datetime.time(23, 59, 59),
        tzinfo=tz,
    )
    minimum_window = base_time + datetime.timedelta(days=7)
    return max(event_window_end, minimum_window)


class Invitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    reference_number = models.PositiveIntegerField(unique=True, null=True, blank=True)
    reference = models.CharField(max_length=24, unique=True, db_index=True)

    # Credential 1: Single-use claim token (encrypted copy kept ONLY while UNUSED)
    claim_token_digest = models.CharField(max_length=64, unique=True, db_index=True)
    claim_token_encrypted = models.TextField(blank=True, default="")

    # Credential 2: Admission QR token (DRIP1:<token>)
    admission_token_digest = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
    )
    admission_token_encrypted = models.TextField(blank=True, default="")
    admission_credential_version = models.PositiveIntegerField(default=0)

    # Credential 3: Read-only public sharing token (/share/[token])
    share_token_digest = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
    )
    share_token_encrypted = models.TextField(blank=True, default="")
    sharing_version = models.PositiveIntegerField(default=1)

    # Guest fields (nickname, email, private gender — excluded from emails, PDFs & public artwork)
    nickname = models.CharField(max_length=50, blank=True, default="")
    guest_email = models.EmailField(max_length=254, blank=True, default="")
    guest_email_normalized = models.CharField(max_length=254, null=True, blank=True, db_index=True)
    gender = models.CharField(
        max_length=10,
        choices=GuestGender.choices,
        blank=True,
        default="",
        db_index=True,
    )

    status = models.CharField(
        max_length=16,
        choices=InvitationStatus.choices,
        default=InvitationStatus.UNUSED,
        db_index=True,
    )

    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="generated_invitations",
    )
    generated_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    claimed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="revoked_invitations",
    )
    revocation_reason = models.CharField(max_length=240, blank=True, default="")

    # Sharing privacy (anonymous by default)
    show_nickname_publicly = models.BooleanField(default=False)
    public_sharing_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-generated_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "guest_email_normalized"],
                condition=models.Q(guest_email_normalized__isnull=False),
                name="uniq_event_guest_email_normalized",
            ),
        ]
        indexes = [
            models.Index(fields=["event", "status"]),
            models.Index(fields=["generated_by", "status"]),
        ]

    @property
    def effective_status(self) -> str:
        if self.status == InvitationStatus.UNUSED and self.expires_at and self.expires_at <= timezone.now():
            return InvitationStatus.EXPIRED
        return self.status

    def __str__(self) -> str:
        return f"{self.reference} ({self.status})"


class ClaimReceipt(models.Model):
    """Credential 4: Limited-purpose HTTP-only cookie credential for /invitation/success & sharing."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invitation = models.ForeignKey(
        Invitation,
        on_delete=models.CASCADE,
        related_name="claim_receipts",
    )
    token_digest = models.CharField(max_length=64, unique=True, db_index=True)
    credential_version = models.PositiveIntegerField(default=1)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def is_currently_valid(self) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at <= timezone.now():
            return False
        inv = self.invitation
        if inv.status != InvitationStatus.CLAIMED:
            return False
        if self.credential_version != inv.admission_credential_version:
            return False
        return True
