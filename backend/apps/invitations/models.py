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


class MasterLinkStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    PAUSED = "PAUSED", "Paused"
    EXHAUSTED = "EXHAUSTED", "Exhausted"
    CLOSED = "CLOSED", "Closed"


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


class MasterInvitationLink(models.Model):
    """
    Lightweight reusable invitation link with a fixed ticket allocation.
    Reserves max_tickets against global & creator quotas on creation without
    pre-creating unused Invitation rows, PDFs, QR tokens, or artwork.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="master_links",
    )
    name = models.CharField(max_length=120, blank=True, default="")
    token_digest = models.CharField(max_length=64, unique=True, db_index=True)
    token_encrypted = models.TextField(blank=True, default="")

    max_tickets = models.PositiveIntegerField()
    claimed_count = models.PositiveIntegerField(default=0)
    released_tickets = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=16,
        choices=MasterLinkStatus.choices,
        default=MasterLinkStatus.ACTIVE,
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_master_links",
    )
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="closed_master_links",
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_tickets__gte=1),
                name="chk_master_link_max_tickets_gte_1",
            ),
            models.CheckConstraint(
                condition=models.Q(claimed_count__lte=models.F("max_tickets")),
                name="chk_master_link_claimed_lte_max",
            ),
        ]
        indexes = [
            models.Index(fields=["event", "status"]),
            models.Index(fields=["created_by", "status"]),
        ]

    @property
    def remaining_tickets(self) -> int:
        if self.status == MasterLinkStatus.CLOSED:
            return 0
        return max(0, self.max_tickets - self.claimed_count)

    @property
    def effective_status(self) -> str:
        if self.status == MasterLinkStatus.CLOSED:
            return MasterLinkStatus.CLOSED
        if self.claimed_count >= self.max_tickets or self.status == MasterLinkStatus.EXHAUSTED:
            return MasterLinkStatus.EXHAUSTED
        if self.status == MasterLinkStatus.PAUSED:
            return MasterLinkStatus.PAUSED
        if self.expires_at and self.expires_at <= timezone.now():
            return "EXPIRED"
        return MasterLinkStatus.ACTIVE

    def __str__(self) -> str:
        label = self.name or str(self.id)[:8]
        return f"MasterLink({label}: {self.claimed_count}/{self.max_tickets}, {self.status})"


class Invitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    master_link = models.ForeignKey(
        MasterInvitationLink,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="claimed_invitations",
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
