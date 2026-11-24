from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_display_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "actor_email",
            "actor_display_name",
            "action_type",
            "target_type",
            "target_id",
            "metadata",
            "ip_address",
            "created_at",
        ]

    def get_actor_display_name(self, obj: AuditLog) -> str:
        if obj.actor_id and obj.actor:
            return obj.actor.display_name
        return obj.actor_email or "System"
