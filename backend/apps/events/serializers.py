from __future__ import annotations

from rest_framework import serializers

from .contacts import build_whatsapp_contact_links
from .models import Event


class PublicEventSerializer(serializers.ModelSerializer):
    venue_display = serializers.SerializerMethodField()
    reservation_contact_links = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "name",
            "subtitle",
            "tagline",
            "organizers",
            "hashtag",
            "event_date",
            "start_time",
            "end_time",
            "location",
            "venue_display",
            "venue_is_public",
            "reservation_contacts",
            "reservation_contact_links",
            "time_zone",
            "age_restriction",
            "claiming_enabled",
            "public_sharing_enabled",
        ]

    def get_venue_display(self, obj: Event) -> str | None:
        if obj.venue_is_public and obj.exact_venue.strip():
            return obj.exact_venue.strip()
        return None

    def get_reservation_contact_links(self, obj: Event) -> list[dict[str, str]]:
        return build_whatsapp_contact_links(obj)


class AdminEventSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "id",
            "name",
            "subtitle",
            "tagline",
            "organizers",
            "hashtag",
            "event_date",
            "start_time",
            "end_time",
            "location",
            "exact_venue",
            "venue_is_public",
            "reservation_contacts",
            "time_zone",
            "age_restriction",
            "global_invitation_limit",
            "max_bulk_quantity",
            "claim_deadline",
            "claiming_enabled",
            "admission_enabled",
            "public_sharing_enabled",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]

    def validate_reservation_contacts(self, value: list[str]) -> list[str]:
        if not isinstance(value, list):
            raise serializers.ValidationError("Reservation contacts must be a list of phone numbers.")
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if len(cleaned) > 10:
            raise serializers.ValidationError("Maximum of 10 reservation contacts allowed.")
        return cleaned

    def validate_max_bulk_quantity(self, value: int) -> int:
        if value < 1 or value > 500:
            raise serializers.ValidationError("Max bulk quantity must be between 1 and 500.")
        return value
