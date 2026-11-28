from __future__ import annotations

import threading
import time

from django.db import transaction
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsActiveAdmin, IsSuperAdmin
from apps.audit.services import log_audit_event

from .models import Event
from .serializers import AdminEventSettingsSerializer, PublicEventSerializer

# Short in-process cache for non-sensitive public event metadata (single gthread worker).
# Immediately invalidated whenever EventSettingsView.patch commits an update.
_PUBLIC_EVENT_CACHE_LOCK = threading.Lock()
_PUBLIC_EVENT_CACHE_TTL_SECONDS = 30.0
_public_event_cache: tuple[float, dict] | None = None


def invalidate_public_event_cache() -> None:
    global _public_event_cache
    with _PUBLIC_EVENT_CACHE_LOCK:
        _public_event_cache = None


class PublicEventView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        global _public_event_cache
        now = time.monotonic()
        with _PUBLIC_EVENT_CACHE_LOCK:
            if _public_event_cache is not None and (now - _public_event_cache[0]) < _PUBLIC_EVENT_CACHE_TTL_SECONDS:
                data = _public_event_cache[1]
            else:
                data = None

        if data is None:
            event = Event.get_current()
            data = PublicEventSerializer(event).data
            with _PUBLIC_EVENT_CACHE_LOCK:
                _public_event_cache = (time.monotonic(), data)

        resp = Response(data)
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
            transaction.on_commit(invalidate_public_event_cache)
        return Response(serializer.data)
