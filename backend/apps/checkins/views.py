from __future__ import annotations

import csv
import io

from django.db import connection
from django.db.models import OuterRef, Q, Subquery
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsActiveAdmin, IsSuperAdmin
from apps.accounts.rate_limit import enforce_rate_limit
from apps.audit.services import log_audit_event
from apps.communications.models import EmailDelivery, EmailStatus
from apps.events.models import Event
from apps.invitations.models import GuestGender, Invitation, InvitationStatus
from apps.invitations.services import (
    get_master_reserved_unused_count,
    get_quota_usage,
    sanitize_csv_cell,
)

from .models import CheckIn
from .serializers import (
    AdmitGuestSerializer,
    CheckInSerializer,
    VerifyManualSerializer,
    VerifyQrSerializer,
)
from .services import admit_guest, verify_manual_reference, verify_qr_payload


class VerifyQrView(APIView):
    permission_classes = [IsActiveAdmin]

    def post(self, request):
        enforce_rate_limit(
            request,
            scope="admin_verify_qr",
            key=str(request.user.id),
            limit=90,
            window_seconds=60,
        )
        serializer = VerifyQrSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = verify_qr_payload(raw_payload=serializer.validated_data["qr_payload"])
        return Response(result)


class VerifyManualView(APIView):
    permission_classes = [IsActiveAdmin]

    def post(self, request):
        enforce_rate_limit(
            request,
            scope="admin_verify_manual",
            key=str(request.user.id),
            limit=45,
            window_seconds=60,
        )
        serializer = VerifyManualSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = verify_manual_reference(reference=serializer.validated_data["reference"])
        return Response(result)


class CheckInCreateView(APIView):
    permission_classes = [IsActiveAdmin]

    def post(self, request):
        serializer = AdmitGuestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        checkin = admit_guest(
            actor=request.user,
            verification_method=serializer.validated_data["verification_method"],
            qr_payload=serializer.validated_data.get("qr_payload", ""),
            reference=serializer.validated_data.get("reference", ""),
            confirm_manual=serializer.validated_data.get("confirm_manual", False),
            notes=serializer.validated_data.get("notes", ""),
            request=request,
        )
        return Response(CheckInSerializer(checkin).data, status=status.HTTP_201_CREATED)


class CheckInListView(ListAPIView):
    permission_classes = [IsActiveAdmin]
    serializer_class = CheckInSerializer

    def get_queryset(self):
        qs = CheckIn.objects.select_related("invitation", "verified_by").all()
        search = self.request.query_params.get("search", "").strip()
        method = self.request.query_params.get("method", "").strip().upper()
        gender = self.request.query_params.get("gender", "").strip().upper()
        if search:
            qs = qs.filter(
                Q(invitation__reference__icontains=search)
                | Q(invitation__nickname__icontains=search)
                | Q(invitation__guest_email__icontains=search)
            )
        if method in {"QR", "MANUAL"}:
            qs = qs.filter(verification_method=method)
        if gender in GuestGender.values:
            qs = qs.filter(invitation__gender=gender)
        elif gender == "UNSPECIFIED":
            qs = qs.filter(invitation__gender="")
        return qs


class CheckInExportCsvView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        qs = CheckIn.objects.select_related("invitation", "verified_by").order_by("-checked_in_at")
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "Invitation Reference",
                "Guest Nickname",
                "Guest Email",
                "Gender",
                "Verification Method",
                "Verified By",
                "Checked In At",
                "Notes",
            ]
        )
        for ci in qs.iterator():
            writer.writerow(
                [
                    sanitize_csv_cell(ci.invitation.reference),
                    sanitize_csv_cell(ci.invitation.nickname),
                    sanitize_csv_cell(ci.invitation.guest_email),
                    sanitize_csv_cell(ci.invitation.get_gender_display() if ci.invitation.gender else ""),
                    sanitize_csv_cell(ci.verification_method),
                    sanitize_csv_cell(ci.verified_by.display_name),
                    sanitize_csv_cell(ci.checked_in_at.isoformat()),
                    sanitize_csv_cell(ci.notes),
                ]
            )

        log_audit_event(
            actor=request.user,
            action_type="CHECKINS_EXPORTED_CSV",
            target_type="CheckIn",
            target_id="export",
            request=request,
        )
        resp = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="drip-and-rhythm-checkins.csv"'
        resp["Cache-Control"] = "no-store, max-age=0, private"
        return resp


class DashboardStatsView(APIView):
    permission_classes = [IsActiveAdmin]

    def get(self, request):
        event = Event.get_current()
        now = timezone.now()
        inv_qs = Invitation.objects.filter(event=event)

        master_reserved_unused = get_master_reserved_unused_count(event=event)
        total_generated = inv_qs.count() + master_reserved_unused
        available_unused = (
            inv_qs.filter(status=InvitationStatus.UNUSED)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            .count()
            + master_reserved_unused
        )
        claimed_count = inv_qs.filter(status=InvitationStatus.CLAIMED).count()
        expired_count = inv_qs.filter(
            Q(status=InvitationStatus.EXPIRED) | Q(status=InvitationStatus.UNUSED, expires_at__lte=now)
        ).count()
        revoked_count = inv_qs.filter(status=InvitationStatus.REVOKED).count()

        latest_email_subq = (
            EmailDelivery.objects.filter(invitation=OuterRef("pk"))
            .order_by("-created_at")
            .values("status")[:1]
        )
        claimed_with_email = inv_qs.filter(status=InvitationStatus.CLAIMED).annotate(
            latest_email=Subquery(latest_email_subq)
        )
        emails_pending = claimed_with_email.filter(
            latest_email__in=[EmailStatus.PENDING, EmailStatus.PROCESSING]
        ).count()
        emails_sent = claimed_with_email.filter(latest_email=EmailStatus.SENT).count()
        emails_delivered = claimed_with_email.filter(latest_email=EmailStatus.DELIVERED).count()
        emails_failed = claimed_with_email.filter(
            latest_email__in=[EmailStatus.FAILED, EmailStatus.BOUNCED]
        ).count()

        admitted_qs = CheckIn.objects.filter(invitation__event=event)
        admitted_count = admitted_qs.count()
        awaiting_admission = max(0, claimed_count - admitted_count)

        claimed_qs = inv_qs.filter(status=InvitationStatus.CLAIMED)
        claimed_male = claimed_qs.filter(gender=GuestGender.MALE).count()
        claimed_female = claimed_qs.filter(gender=GuestGender.FEMALE).count()
        admitted_male = admitted_qs.filter(invitation__gender=GuestGender.MALE).count()
        admitted_female = admitted_qs.filter(invitation__gender=GuestGender.FEMALE).count()

        def _pct(part: int, total: int) -> float:
            return round((part / total) * 100, 1) if total > 0 else 0.0

        # Documented denominators:
        # claim_rate = claimed / total_generated; attendance_rate = admitted / eligible_claimed
        claim_rate = _pct(claimed_count, total_generated)
        attendance_rate = _pct(admitted_count, claimed_count)

        admin_generated = get_quota_usage(event=event, actor=request.user)

        return Response(
            {
                "total_generated": total_generated,
                "available_unused": available_unused,
                "claimed": claimed_count,
                "expired": expired_count,
                "revoked": revoked_count,
                "emails_pending": emails_pending,
                "emails_sent": emails_sent,
                "emails_delivered": emails_delivered,
                "emails_failed": emails_failed,
                "guests_admitted": admitted_count,
                "guests_awaiting_admission": awaiting_admission,
                "claim_rate_percent": claim_rate,
                "attendance_rate_percent": attendance_rate,
                "gender_breakdown": {
                    "claimed": {
                        "male": claimed_male,
                        "female": claimed_female,
                        "male_percent": _pct(claimed_male, claimed_count),
                        "female_percent": _pct(claimed_female, claimed_count),
                    },
                    "admitted": {
                        "male": admitted_male,
                        "female": admitted_female,
                        "male_percent": _pct(admitted_male, admitted_count),
                        "female_percent": _pct(admitted_female, admitted_count),
                    },
                },
                "quota": {
                    "global_limit": event.global_invitation_limit,
                    "global_used": total_generated,
                    "global_remaining": (
                        max(0, event.global_invitation_limit - total_generated)
                        if event.global_invitation_limit is not None
                        else None
                    ),
                    "admin_limit": request.user.invitation_limit,
                    "admin_used": admin_generated,
                    "admin_remaining": (
                        max(0, request.user.invitation_limit - admin_generated)
                        if request.user.invitation_limit is not None
                        else None
                    ),
                    "max_bulk_quantity": event.max_bulk_quantity,
                },
                "event_flags": {
                    "claiming_enabled": event.claiming_enabled,
                    "admission_enabled": event.admission_enabled,
                    "public_sharing_enabled": event.public_sharing_enabled,
                },
            }
        )


class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        return Response({"status": "ok", "service": "drip-and-rhythm-api"})
