from django.db.models import Q
from rest_framework.generics import ListAPIView

from apps.accounts.permissions import IsSuperAdmin

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogListView(ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        qs = AuditLog.objects.select_related("actor").all()
        action_type = self.request.query_params.get("action_type", "").strip()
        target_type = self.request.query_params.get("target_type", "").strip()
        search = self.request.query_params.get("search", "").strip()
        if action_type:
            qs = qs.filter(action_type=action_type)
        if target_type:
            qs = qs.filter(target_type=target_type)
        if search:
            qs = qs.filter(
                Q(actor_email__icontains=search)
                | Q(action_type__icontains=search)
                | Q(target_id__icontains=search)
            )
        return qs
