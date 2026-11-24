from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsActiveAdmin
from apps.accounts.rate_limit import enforce_rate_limit

from .services import admin_process_pending_emails, process_resend_webhook


@method_decorator(csrf_exempt, name="dispatch")
class ResendWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw_body: bytes = request.body
        headers = {
            "svix-id": request.META.get("HTTP_SVIX_ID", ""),
            "svix-timestamp": request.META.get("HTTP_SVIX_TIMESTAMP", ""),
            "svix-signature": request.META.get("HTTP_SVIX_SIGNATURE", ""),
        }
        result = process_resend_webhook(raw_body=raw_body, headers=headers)
        return Response(result)


class AdminProcessPendingEmailsView(APIView):
    permission_classes = [IsActiveAdmin]

    def post(self, request):
        enforce_rate_limit(
            request,
            scope="admin_process_emails",
            key=str(request.user.id),
            limit=6,
            window_seconds=300,
        )
        include_failed = bool(request.data.get("include_failed", True))
        try:
            max_jobs = int(request.data.get("max_jobs", 10))
        except (TypeError, ValueError):
            max_jobs = 10
        result = admin_process_pending_emails(
            actor=request.user,
            max_jobs=max_jobs,
            include_failed=include_failed,
            request=request,
        )
        return Response(result)
