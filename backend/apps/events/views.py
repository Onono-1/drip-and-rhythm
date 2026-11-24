from __future__ import annotations

from django.db import transaction
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsActiveAdmin, IsSuperAdmin
from apps.audit.services import log_audit_event

from .models import Event
from .serializers import AdminEventSettingsSerializer, PublicEventSerializer


class PublicEventView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        event = Event.get_current()
        resp = Response(PublicEventSerializer(event).data)
        resp["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
        return resp


class EventSettingsView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [IsActiveAdmin()]
        return [IsSuperAdmin()]

    def get(self, request):
        event = Event.get_current()
        return Response(AdminEventSettingsSerializer(event).data)

    def patch(self, request):
        with transaction.atomic():
            event = Event.get_current(lock=True)
            serializer = AdminEventSettingsSerializer(event, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            updated_fields = list(serializer.validated_data.keys())
            serializer.save()
            log_audit_event(
                actor=request.user,
                action_type="EVENT_SETTINGS_UPDATED",
                target_type="Event",
                target_id=str(event.id),
                metadata={"updated_fields": updated_fields},
                request=request,
            )
        return Response(serializer.data)
