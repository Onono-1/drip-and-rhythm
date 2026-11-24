from __future__ import annotations

import datetime
import uuid

from django.db import models


def default_reservation_contacts() -> list[str]:
    return ["0781210342", "0742627388", "0700246148"]


class Event(models.Model):
    SINGLETON_SLUG = "drip-and-rhythm-2026"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, default="DRIP & RHYTHM")
    slug = models.SlugField(max_length=80, unique=True, default=SINGLETON_SLUG)
    subtitle = models.CharField(max_length=120, default="Private Party")
    tagline = models.CharField(max_length=200, default="An affair of fashion, music and culture")
    organizers = models.CharField(max_length=180, default="After Dark Events × Hype District")
    hashtag = models.CharField(max_length=64, default="#DripAndRhythm")
    event_date = models.DateField(default=datetime.date(2026, 12, 5))
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=160, default="Muyenga, Kampala, Uganda")
    exact_venue = models.CharField(max_length=200, blank=True, default="")
    venue_is_public = models.BooleanField(default=False)
    reservation_contacts = models.JSONField(default=default_reservation_contacts)
    time_zone = models.CharField(max_length=64, default="Africa/Kampala")
    age_restriction = models.CharField(max_length=32, default="18+")
    global_invitation_limit = models.PositiveIntegerField(null=True, blank=True, default=500)
    max_bulk_quantity = models.PositiveIntegerField(default=100)
    claim_deadline = models.DateTimeField(null=True, blank=True)
    claiming_enabled = models.BooleanField(default=True)
    admission_enabled = models.BooleanField(default=True)
    public_sharing_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    @classmethod
    def get_current(cls, *, lock: bool = False) -> Event:
        qs = cls.objects.select_for_update() if lock else cls.objects.all()
        event = qs.filter(slug=cls.SINGLETON_SLUG).first()
        if event is not None:
            return event
        event, _ = cls.objects.get_or_create(slug=cls.SINGLETON_SLUG)
        if lock:
            return cls.objects.select_for_update().get(pk=event.pk)
        return event

    def __str__(self) -> str:
        return f"{self.name} ({self.event_date.isoformat()})"
