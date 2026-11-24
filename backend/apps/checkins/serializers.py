from rest_framework import serializers

from .models import CheckIn, VerificationMethod


class VerifyQrSerializer(serializers.Serializer):
    qr_payload = serializers.CharField(max_length=512)


class VerifyManualSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=32)


class AdmitGuestSerializer(serializers.Serializer):
    verification_method = serializers.ChoiceField(choices=VerificationMethod.choices)
    qr_payload = serializers.CharField(max_length=512, required=False, allow_blank=True, default="")
    reference = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    confirm_manual = serializers.BooleanField(required=False, default=False)
    notes = serializers.CharField(max_length=240, required=False, allow_blank=True, default="")


class CheckInSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(source="invitation.reference", read_only=True)
    nickname = serializers.CharField(source="invitation.nickname", read_only=True)
    guest_email = serializers.CharField(source="invitation.guest_email", read_only=True)
    gender = serializers.CharField(source="invitation.gender", read_only=True)
    verified_by_name = serializers.CharField(source="verified_by.display_name", read_only=True)

    class Meta:
        model = CheckIn
        fields = [
            "id",
            "invitation",
            "reference",
            "nickname",
            "guest_email",
            "gender",
            "verified_by",
            "verified_by_name",
            "checked_in_at",
            "verification_method",
            "notes",
        ]
