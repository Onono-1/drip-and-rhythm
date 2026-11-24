from __future__ import annotations

from rest_framework import serializers

from apps.events.serializers import PublicEventSerializer

from .models import GuestGender, Invitation
from .services import build_share_url, get_recoverable_claim_url, get_recoverable_share_token


class GenerateInvitationSerializer(serializers.Serializer):
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class BulkGenerateInvitationSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=500)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class ClaimInvitationSerializer(serializers.Serializer):
    nickname = serializers.CharField(max_length=80, trim_whitespace=True)
    email = serializers.CharField(max_length=254, trim_whitespace=True)
    gender = serializers.ChoiceField(
        choices=GuestGender.choices,
        required=True,
        allow_blank=False,
        error_messages={
            "required": "Please select Male or Female.",
            "invalid_choice": "Please select Male or Female.",
            "blank": "Please select Male or Female.",
            "null": "Please select Male or Female.",
        },
    )


class RevokeInvitationSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=240, required=False, allow_blank=True, default="")


class CorrectGuestSerializer(serializers.Serializer):
    nickname = serializers.CharField(max_length=80, required=False)
    email = serializers.CharField(max_length=254, required=False)
    gender = serializers.ChoiceField(
        choices=GuestGender.choices,
        required=False,
        allow_blank=False,
        error_messages={"invalid_choice": "Please select Male or Female."},
    )
    resend_email = serializers.BooleanField(required=False, default=True)


class SharingPreferenceSerializer(serializers.Serializer):
    show_nickname_publicly = serializers.BooleanField(required=False)
    public_sharing_enabled = serializers.BooleanField(required=False)


class AdminInvitationListSerializer(serializers.ModelSerializer):
    status = serializers.CharField(source="effective_status", read_only=True)
    generated_by_name = serializers.CharField(source="generated_by.display_name", read_only=True)
    generated_by_email = serializers.CharField(source="generated_by.email", read_only=True)
    latest_email_status = serializers.SerializerMethodField()
    is_admitted = serializers.SerializerMethodField()
    checked_in_at = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            "id",
            "reference",
            "nickname",
            "guest_email",
            "gender",
            "status",
            "latest_email_status",
            "is_admitted",
            "checked_in_at",
            "generated_by",
            "generated_by_name",
            "generated_by_email",
            "generated_at",
            "expires_at",
            "claimed_at",
            "revoked_at",
            "revocation_reason",
            "show_nickname_publicly",
            "public_sharing_enabled",
            "can_manage",
        ]

    def get_latest_email_status(self, obj: Invitation) -> str:
        latest = getattr(obj, "_prefetched_latest_delivery", None)
        if latest is not None:
            return latest
        delivery = obj.email_deliveries.order_by("-created_at").first()
        return delivery.status if delivery else "NOT_SCHEDULED"

    def get_is_admitted(self, obj: Invitation) -> bool:
        return hasattr(obj, "checkin")

    def get_checked_in_at(self, obj: Invitation):
        if hasattr(obj, "checkin"):
            return obj.checkin.checked_in_at
        return None

    def get_can_manage(self, obj: Invitation) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return bool(user.is_super_admin or obj.generated_by_id == user.id)


class AdminInvitationDetailSerializer(AdminInvitationListSerializer):
    claim_url = serializers.SerializerMethodField()
    revoked_by_name = serializers.SerializerMethodField()
    checkin_details = serializers.SerializerMethodField()

    class Meta(AdminInvitationListSerializer.Meta):
        fields = [
            *AdminInvitationListSerializer.Meta.fields,
            "claim_url",
            "revoked_by_name",
            "admission_credential_version",
            "checkin_details",
        ]

    def get_claim_url(self, obj: Invitation) -> str | None:
        return get_recoverable_claim_url(obj)

    def get_revoked_by_name(self, obj: Invitation) -> str | None:
        if obj.revoked_by_id and obj.revoked_by:
            return obj.revoked_by.display_name
        return None

    def get_checkin_details(self, obj: Invitation) -> dict | None:
        if not hasattr(obj, "checkin"):
            return None
        ci = obj.checkin
        return {
            "id": str(ci.id),
            "checked_in_at": ci.checked_in_at,
            "verification_method": ci.verification_method,
            "verified_by_name": ci.verified_by.display_name if ci.verified_by else "Administrator",
            "notes": ci.notes,
        }


def serialize_claim_receipt_payload(invitation: Invitation) -> dict[str, object]:
    event = invitation.event
    latest_delivery = invitation.email_deliveries.order_by("-created_at").first()
    raw_share = get_recoverable_share_token(invitation)
    share_enabled = bool(event.public_sharing_enabled and invitation.public_sharing_enabled and raw_share)
    share_url = build_share_url(raw_share) if (raw_share and share_enabled) else None
    v = invitation.sharing_version

    artwork_urls = (
        {
            fmt: f"/api/share/{raw_share}/image/?format={fmt}&v={v}"
            for fmt in ("story", "square", "portrait", "preview")
        }
        if raw_share
        else {}
    )

    return {
        "nickname": invitation.nickname,
        "guest_email": invitation.guest_email,
        "reference": invitation.reference,
        "claimed_at": invitation.claimed_at,
        "email_delivery_status": latest_delivery.status if latest_delivery else "PENDING",
        "show_nickname_publicly": invitation.show_nickname_publicly,
        "public_sharing_enabled": invitation.public_sharing_enabled,
        "event_sharing_enabled": event.public_sharing_enabled,
        "sharing_version": v,
        "share_token": raw_share if share_enabled else None,
        "share_url": share_url,
        "artwork_urls": artwork_urls,
        "event": PublicEventSerializer(event).data,
    }
