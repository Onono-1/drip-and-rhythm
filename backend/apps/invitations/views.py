from __future__ import annotations

import csv
import io

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Subquery
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsActiveAdmin, IsSuperAdmin
from apps.accounts.rate_limit import enforce_rate_limit
from apps.audit.exceptions import ApplicationError
from apps.audit.services import log_audit_event
from apps.checkins.models import CheckIn
from apps.communications.models import EmailDelivery
from apps.communications.serializers import EmailDeliverySerializer
from apps.communications.services import admin_resend_invitation_email
from apps.events.serializers import PublicEventSerializer

from .artwork import (
     FORMAT_SPECS,
    ArtworkRenderBusyError,
    build_artwork_cache_key,
    get_or_render_promotional_artwork,
)
from .crypto import hash_token
from .models import GuestGender, Invitation, InvitationStatus
from .serializers import (
    AdminInvitationDetailSerializer,
    AdminInvitationListSerializer,
    BulkGenerateInvitationSerializer,
    ClaimInvitationSerializer,
    CorrectGuestSerializer,
    GenerateInvitationSerializer,
    RevokeInvitationSerializer,
    SharingPreferenceSerializer,
    serialize_claim_receipt_payload,
)
from .services import (
    assert_can_manage_invitation,
    build_share_url,
    claim_invitation,
    correct_guest_information,
    generate_invitations,
    get_recoverable_claim_url,
    inspect_invitation_by_token,
    resolve_valid_claim_receipt,
    revoke_invitation,
    sanitize_csv_cell,
)


def _filtered_invitations_queryset(params):
    latest_email_subq = (
        EmailDelivery.objects.filter(invitation=OuterRef("pk"))
        .order_by("-created_at")
        .values("status")[:1]
    )
    admitted_exists = CheckIn.objects.filter(invitation=OuterRef("pk"))

    qs = (
        Invitation.objects.select_related("generated_by", "revoked_by", "checkin", "checkin__verified_by")
        .annotate(
            _prefetched_latest_delivery=Subquery(latest_email_subq),
            _is_admitted=Exists(admitted_exists),
        )
        .all()
    )

    search = params.get("search", "").strip()
    if search:
        qs = qs.filter(
            Q(reference__icontains=search)
            | Q(nickname__icontains=search)
            | Q(guest_email__icontains=search)
        )

    inv_status = params.get("status", "").strip().upper()
    now = timezone.now()
    if inv_status == InvitationStatus.EXPIRED:
        qs = qs.filter(
            Q(status=InvitationStatus.EXPIRED)
            | Q(status=InvitationStatus.UNUSED, expires_at__lte=now)
        )
    elif inv_status == InvitationStatus.UNUSED:
        qs = qs.filter(status=InvitationStatus.UNUSED).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    elif inv_status in InvitationStatus.values:
        qs = qs.filter(status=inv_status)

    email_status = params.get("email_status", "").strip().upper()
    if email_status == "NOT_SCHEDULED":
        qs = qs.filter(_prefetched_latest_delivery__isnull=True)
    elif email_status:
        qs = qs.filter(_prefetched_latest_delivery=email_status)

    admission = params.get("admission_status", "").strip().upper()
    if admission == "ADMITTED":
        qs = qs.filter(_is_admitted=True)
    elif admission == "NOT_ADMITTED":
        qs = qs.filter(_is_admitted=False)

    gender = params.get("gender", "").strip().upper()
    if gender in GuestGender.values:
        qs = qs.filter(gender=gender)
    elif gender == "UNSPECIFIED":
        qs = qs.filter(gender="")

    generated_by = params.get("generated_by", "").strip()
    if generated_by:
        qs = qs.filter(generated_by_id=generated_by)

    ordering = params.get("ordering", "-generated_at").strip()
    allowed_orderings = {
        "generated_at",
        "-generated_at",
        "claimed_at",
        "-claimed_at",
        "reference",
        "-reference",
    }
    if ordering in allowed_orderings:
        qs = qs.order_by(ordering)

    return qs


class InvitationListCreateView(ListCreateAPIView):
    permission_classes = [IsActiveAdmin]
    serializer_class = AdminInvitationListSerializer

    def get_queryset(self):
        return _filtered_invitations_queryset(self.request.query_params)

    def create(self, request, *args, **kwargs):
        enforce_rate_limit(
            request,
            scope="admin_generate_invitation",
            key=str(request.user.id),
            limit=40,
            window_seconds=60,
        )
        serializer = GenerateInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = generate_invitations(
            actor=request.user,
            quantity=1,
            expires_at=serializer.validated_data.get("expires_at"),
            request=request,
        )
        inv, claim_url = result.invitations[0]
        data = AdminInvitationDetailSerializer(inv, context={"request": request}).data
        data["claim_url"] = claim_url
        data["remaining_global_quota"] = result.remaining_global_quota
        data["remaining_admin_quota"] = result.remaining_admin_quota
        return Response(data, status=status.HTTP_201_CREATED)


class BulkInvitationCreateView(APIView):
    permission_classes = [IsActiveAdmin]

    def post(self, request):
        enforce_rate_limit(
            request,
            scope="admin_bulk_generate",
            key=str(request.user.id),
            limit=12,
            window_seconds=60,
        )
        serializer = BulkGenerateInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = generate_invitations(
            actor=request.user,
            quantity=serializer.validated_data["quantity"],
            expires_at=serializer.validated_data.get("expires_at"),
            request=request,
        )
        items = [
            {
                "id": str(inv.id),
                "reference": inv.reference,
                "claim_url": claim_url,
                "expires_at": inv.expires_at,
                "generated_at": inv.generated_at,
            }
            for inv, claim_url in result.invitations
        ]
        return Response(
            {
                "count": len(items),
                "items": items,
                "remaining_global_quota": result.remaining_global_quota,
                "remaining_admin_quota": result.remaining_admin_quota,
            },
            status=status.HTTP_201_CREATED,
        )


class InvitationDetailView(RetrieveAPIView):
    permission_classes = [IsActiveAdmin]
    serializer_class = AdminInvitationDetailSerializer

    def get_queryset(self):
        return Invitation.objects.select_related(
            "generated_by", "revoked_by", "checkin", "checkin__verified_by"
        ).all()


class InvitationClaimLinkView(APIView):
    permission_classes = [IsActiveAdmin]

    def get(self, request, pk):
        inv = get_object_or_404(Invitation, pk=pk)
        assert_can_manage_invitation(request.user, inv)
        claim_url = get_recoverable_claim_url(inv)
        if not claim_url:
            raise ApplicationError(
                code="CLAIM_LINK_UNAVAILABLE",
                message="Claim link is only available while the invitation remains unused.",
                status_code=status.HTTP_409_CONFLICT,
            )
        return Response({"id": str(inv.id), "reference": inv.reference, "claim_url": claim_url})


class InvitationRevokeView(APIView):
    permission_classes = [IsActiveAdmin]

    def post(self, request, pk):
        serializer = RevokeInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inv = revoke_invitation(
            actor=request.user,
            invitation_id=pk,
            reason=serializer.validated_data.get("reason", ""),
            request=request,
        )
        return Response(AdminInvitationDetailSerializer(inv, context={"request": request}).data)


class InvitationResendView(APIView):
    permission_classes = [IsActiveAdmin]

    def post(self, request, pk):
        enforce_rate_limit(
            request,
            scope="admin_resend_invitation",
            key=f"{request.user.id}:{pk}",
            limit=4,
            window_seconds=300,
        )
        delivery = admin_resend_invitation_email(actor=request.user, invitation_id=pk, request=request)
        return Response(EmailDeliverySerializer(delivery).data, status=status.HTTP_202_ACCEPTED)


class InvitationCorrectGuestView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        serializer = CorrectGuestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inv = correct_guest_information(
            actor=request.user,
            invitation_id=pk,
            new_nickname=serializer.validated_data.get("nickname"),
            new_email=serializer.validated_data.get("email"),
            new_gender=serializer.validated_data.get("gender"),
            resend_after_nickname_change=serializer.validated_data.get("resend_email", True),
            request=request,
        )
        return Response(AdminInvitationDetailSerializer(inv, context={"request": request}).data)


class InvitationDeliveriesView(APIView):
    permission_classes = [IsActiveAdmin]

    def get(self, request, pk):
        inv = get_object_or_404(Invitation, pk=pk)
        deliveries = inv.email_deliveries.order_by("-created_at")
        return Response(EmailDeliverySerializer(deliveries, many=True).data)


class InvitationExportCsvView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        qs = _filtered_invitations_queryset(request.query_params)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "Reference",
                "Status",
                "Nickname",
                "Guest Email",
                "Gender",
                "Email Delivery Status",
                "Admitted",
                "Checked In At",
                "Generated By",
                "Generated At",
                "Claimed At",
                "Revoked At",
            ]
        )
        for inv in qs.iterator():
            writer.writerow(
                [
                    sanitize_csv_cell(inv.reference),
                    sanitize_csv_cell(inv.effective_status),
                    sanitize_csv_cell(inv.nickname),
                    sanitize_csv_cell(inv.guest_email),
                    sanitize_csv_cell(inv.get_gender_display() if inv.gender else ""),
                    sanitize_csv_cell(getattr(inv, "_prefetched_latest_delivery", None) or "NOT_SCHEDULED"),
                    sanitize_csv_cell("YES" if hasattr(inv, "checkin") else "NO"),
                    sanitize_csv_cell(inv.checkin.checked_in_at.isoformat() if hasattr(inv, "checkin") else ""),
                    sanitize_csv_cell(inv.generated_by.display_name),
                    sanitize_csv_cell(inv.generated_at.isoformat()),
                    sanitize_csv_cell(inv.claimed_at.isoformat() if inv.claimed_at else ""),
                    sanitize_csv_cell(inv.revoked_at.isoformat() if inv.revoked_at else ""),
                ]
            )

        log_audit_event(
            actor=request.user,
            action_type="INVITATIONS_EXPORTED_CSV",
            target_type="Invitation",
            target_id="export",
            request=request,
        )
        resp = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="drip-and-rhythm-invitations.csv"'
        resp["Cache-Control"] = "no-store, max-age=0, private"
        return resp


class GuestInviteInspectView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token: str):
        enforce_rate_limit(request, scope="guest_invite_inspect", limit=45, window_seconds=60)
        info = inspect_invitation_by_token(token)
        event = info.pop("event")
        info["event"] = PublicEventSerializer(event).data
        resp = Response(info)
        resp["Cache-Control"] = "no-store, max-age=0, private"
        return resp


@method_decorator(csrf_protect, name="dispatch")
class GuestInviteClaimView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, token: str):
        enforce_rate_limit(request, scope="guest_invite_claim_ip", limit=12, window_seconds=300)
        serializer = ClaimInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = claim_invitation(
            raw_token=token,
            raw_nickname=serializer.validated_data["nickname"],
            raw_email=serializer.validated_data["email"],
            raw_gender=serializer.validated_data["gender"],
        )

        payload = serialize_claim_receipt_payload(result.invitation)
        resp = Response(payload, status=status.HTTP_201_CREATED)
        max_age = max(60, int((result.receipt_expires_at - timezone.now()).total_seconds()))
        resp.set_cookie(
            key=settings.CLAIM_RECEIPT_COOKIE_NAME,
            value=result.raw_receipt_token,
            max_age=max_age,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="Lax",
            path="/",
        )
        resp["Cache-Control"] = "no-store, max-age=0, private"
        return resp


class ClaimReceiptView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        raw_cookie = request.COOKIES.get(settings.CLAIM_RECEIPT_COOKIE_NAME)
        receipt = resolve_valid_claim_receipt(raw_cookie)
        resp = Response(serialize_claim_receipt_payload(receipt.invitation))
        resp["Cache-Control"] = "no-store, max-age=0, private"
        return resp


@method_decorator(csrf_protect, name="dispatch")
class ClaimReceiptSharingView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        raw_cookie = request.COOKIES.get(settings.CLAIM_RECEIPT_COOKIE_NAME)
        receipt = resolve_valid_claim_receipt(raw_cookie)
        resp = Response(serialize_claim_receipt_payload(receipt.invitation))
        resp["Cache-Control"] = "no-store, max-age=0, private"
        return resp

    def _update_preferences(self, request):
        enforce_rate_limit(request, scope="guest_sharing_pref", limit=25, window_seconds=300)
        raw_cookie = request.COOKIES.get(settings.CLAIM_RECEIPT_COOKIE_NAME)
        receipt = resolve_valid_claim_receipt(raw_cookie)
        serializer = SharingPreferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            inv = Invitation.objects.select_for_update().select_related("event").get(pk=receipt.invitation_id)
            if inv.status != InvitationStatus.CLAIMED:
                raise ApplicationError(
                    code="CLAIM_RECEIPT_INVALID",
                    message="Invitation is no longer active.",
                    status_code=status.HTTP_403_FORBIDDEN,
                )
            if "public_sharing_enabled" in serializer.validated_data:
                inv.public_sharing_enabled = serializer.validated_data["public_sharing_enabled"]
            inv.show_nickname_publicly = True
            inv.sharing_version += 1
            inv.save(update_fields=["show_nickname_publicly", "public_sharing_enabled", "sharing_version", "updated_at"])

        resp = Response(serialize_claim_receipt_payload(inv))
        resp["Cache-Control"] = "no-store, max-age=0, private"
        return resp

    def post(self, request):
        return self._update_preferences(request)

    def patch(self, request):
        return self._update_preferences(request)


def _resolve_public_share_invitation(raw_share_token: str, *, allow_receipt_preview_cookie: str | None = None) -> Invitation:
    digest = hash_token(raw_share_token)
    inv = Invitation.objects.select_related("event").filter(share_token_digest=digest).first()
    if inv is None or inv.status != InvitationStatus.CLAIMED:
        raise ApplicationError(
            code="SHARING_UNAVAILABLE",
            message="This shared invitation experience is unavailable.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Allow the claimant's own valid receipt cookie to preview artwork on /invitation/success even if public sharing is toggled off
    if allow_receipt_preview_cookie:
        try:
            receipt = resolve_valid_claim_receipt(allow_receipt_preview_cookie)
            if receipt.invitation_id == inv.id:
                return inv
        except ApplicationError:
            pass

    if not inv.event.public_sharing_enabled or not inv.public_sharing_enabled:
        raise ApplicationError(
            code="SHARING_UNAVAILABLE",
            message="Public sharing has been disabled for this invitation.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return inv


class PublicShareDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token: str):
        enforce_rate_limit(request, scope="public_share_detail", limit=60, window_seconds=60)
        inv = _resolve_public_share_invitation(token)
        v = inv.sharing_version
        data = {
            "event": PublicEventSerializer(inv.event).data,
            "nickname": inv.nickname,
            "show_nickname_publicly": True,
            "sharing_version": v,
            "share_url": build_share_url(token),
            "artwork_urls": {
                fmt: f"/api/share/{token}/image/?format={fmt}&v={v}"
                for fmt in ("story", "square", "portrait", "preview")
            },
        }
        resp = Response(data)
        resp["Cache-Control"] = "no-store, max-age=0, must-revalidate"
        return resp


class PublicShareImageView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token: str):
        enforce_rate_limit(request, scope="public_share_image", limit=120, window_seconds=60)
        fmt = request.query_params.get("format", "story").strip().lower()
        if fmt not in FORMAT_SPECS:
            raise ApplicationError(
                code="VALIDATION_ERROR",
                message="Invalid artwork format. Choose story, square, portrait, or preview.",
            )
        raw_receipt = request.COOKIES.get(settings.CLAIM_RECEIPT_COOKIE_NAME)
        # Always verify authorization, revocation, and sharing preferences BEFORE serving cache/ETag
        inv = _resolve_public_share_invitation(token, allow_receipt_preview_cookie=raw_receipt)

        expected_key = build_artwork_cache_key(
            event=inv.event,
            format_name=fmt,
            nickname=inv.nickname,
            show_nickname=True,
            invitation_id=str(inv.id),
            sharing_version=inv.sharing_version,
        )
        etag_value = f'"{expected_key}"'
        download = request.query_params.get("download", "").strip() in {"1", "true"}
        inm = request.META.get("HTTP_IF_NONE_MATCH", "")
        if not download and inm and etag_value in inm:
            not_modified = HttpResponse(status=status.HTTP_304_NOT_MODIFIED)
            not_modified["ETag"] = etag_value
            not_modified["Cache-Control"] = "private, no-cache, must-revalidate"
            return not_modified

        try:
            rendered = get_or_render_promotional_artwork(
                event=inv.event,
                format_name=fmt,
                nickname=inv.nickname,
                show_nickname=True,
                invitation_id=str(inv.id),
                sharing_version=inv.sharing_version,
            )
        except ArtworkRenderBusyError as exc:
            busy_resp = JsonResponse(
                {
                    "error": {
                        "code": "ARTWORK_BUSY",
                        "message": "Artwork renderer is momentarily busy. Please retry shortly.",
                        "details": {"retry_after": exc.retry_after_seconds},
                    }
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
            busy_resp["Retry-After"] = str(exc.retry_after_seconds)
            busy_resp["Cache-Control"] = "no-store, max-age=0, private"
            return busy_resp

        resp = HttpResponse(rendered.png_bytes, content_type="image/png")
        resp["ETag"] = f'"{rendered.cache_key}"'
        resp["Content-Length"] = str(len(rendered.png_bytes))
        if download:
            resp["Content-Disposition"] = f'attachment; filename="drip-and-rhythm-{fmt}.png"'
        resp["Cache-Control"] = "private, no-cache, must-revalidate"
        return resp
