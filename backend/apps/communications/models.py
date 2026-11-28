from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone


class EmailType(models.TextChoices):
    INVITATION_PASS = "INVITATION_PASS", "Invitation Pass"
    INVITATION_RESEND = "INVITATION_RESEND", "Administrative Resend"
    INVITATION_CORRECTED = "INVITATION_CORRECTED", "Updated Invitation Pass"
    PASSWORD_RESET = "PASSWORD_RESET", "Administrator Password Reset"


class EmailStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    SENT = "SENT", "Sent"
    DELIVERED = "DELIVERED", "Delivered"
    FAILED = "FAILED", "Failed"
    BOUNCED = "BOUNCED", "Bounced"
    CANCELLED = "CANCELLED", "Cancelled"


class EmailDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invitation = models.ForeignKey(
        "invitations.Invitation",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="email_deliveries",
    )
    email_type = models.CharField(max_length=32, choices=EmailType.choices, db_index=True)
    recipient_email = models.EmailField(max_length=254, db_index=True)
    admission_credential_version = models.PositiveIntegerField(null=True, blank=True)
    context_payload = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=16,
        choices=EmailStatus.choices,
        default=EmailStatus.PENDING,
        db_index=True,
    )
    provider = models.CharField(max_length=32, default="local")
    provider_message_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    idempotency_key = models.CharField(max_length=128, unique=True)

    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    next_retry_at = models.DateTimeField(default=timezone.now, db_index=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    worker_id = models.CharField(max_length=64, blank=True, default="")

    last_attempted_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "next_retry_at"]),
            models.Index(fields=["status", "lease_expires_at"]),
            models.Index(fields=["invitation", "-created_at"], name="comm_email_inv_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.email_type} -> {self.recipient_email} ({self.status})"


class WebhookEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    svix_id = models.CharField(max_length=128, unique=True, db_index=True)
    event_type = models.CharField(max_length=64)
    provider_message_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
