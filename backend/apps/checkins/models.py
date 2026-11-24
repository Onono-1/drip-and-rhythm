from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class VerificationMethod(models.TextChoices):
    QR = "QR", "QR Scan"
    MANUAL = "MANUAL", "Manual Reference"


class CheckIn(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invitation = models.OneToOneField(
        "invitations.Invitation",
        on_delete=models.PROTECT,
        related_name="checkin",
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="verified_checkins",
    )
    checked_in_at = models.DateTimeField(default=timezone.now, db_index=True)
    verification_method = models.CharField(
        max_length=16,
        choices=VerificationMethod.choices,
        default=VerificationMethod.QR,
    )
    notes = models.CharField(max_length=240, blank=True, default="")

    class Meta:
        ordering = ["-checked_in_at"]

    def __str__(self) -> str:
        return f"{self.invitation.reference} checked in at {self.checked_in_at.isoformat()}"
