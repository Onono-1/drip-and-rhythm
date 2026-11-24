from rest_framework import serializers

from .models import EmailDelivery


class EmailDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailDelivery
        fields = [
            "id",
            "email_type",
            "recipient_email",
            "admission_credential_version",
            "status",
            "provider",
            "provider_message_id",
            "attempt_count",
            "max_attempts",
            "next_retry_at",
            "last_attempted_at",
            "sent_at",
            "delivered_at",
            "failure_reason",
            "created_at",
        ]
