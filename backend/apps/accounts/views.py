from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.sessions.models import Session
from django.db import transaction
from django.db.models import Count, Q
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.exceptions import ApplicationError
from apps.audit.services import log_audit_event

from .models import AdminRole, PasswordResetToken, User
from .permissions import IsActiveAdmin, IsSuperAdmin
from .rate_limit import enforce_rate_limit
from .serializers import (
    AdminMeSerializer,
    AdminUserCreateSerializer,
    AdminUserUpdateSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    ResetPasswordSerializer,
)


def _invalidate_user_sessions(user_id: str) -> None:
    now = timezone.now()
    target_id = str(user_id)
    matching_keys: list[str] = []
    for session in Session.objects.filter(expire_date__gt=now).only("session_key", "session_data").iterator(chunk_size=100):
        data = session.get_decoded()
        if str(data.get("_auth_user_id")) == target_id:
            matching_keys.append(session.session_key)
    if matching_keys:
        Session.objects.filter(session_key__in=matching_keys).delete()


def _with_generated_count(user: User) -> User:
    from apps.events.models import Event
    from apps.invitations.services import get_quota_usage

    user.invitations_generated_count = get_quota_usage(event=Event.get_current(), actor=user)
    return user


def _assert_not_last_super_admin(target_user: User, *, demoting: bool = False, deactivating: bool = False) -> None:
    if target_user.role != AdminRole.SUPER_ADMIN or not target_user.is_active:
        return
    if not (demoting or deactivating):
        return
    active_supers = list(
        User.objects.select_for_update()
        .filter(role=AdminRole.SUPER_ADMIN, is_active=True)
        .values_list("id", flat=True)
    )
    if len(active_supers) <= 1 and target_user.id in active_supers:
        raise ApplicationError(
            code="LAST_SUPER_ADMIN",
            message="Cannot deactivate or demote the final active super administrator.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfBootstrapView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        token = get_token(request)
        return Response({"csrfToken": token})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        enforce_rate_limit(request, scope="auth_login_ip", limit=15, window_seconds=300)
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        password = serializer.validated_data["password"]
        enforce_rate_limit(request, scope="auth_login_email", key=email, limit=8, window_seconds=600)

        candidate = User.objects.filter(email__iexact=email).first()
        if candidate is not None and not candidate.is_active and candidate.check_password(password):
            log_audit_event(
                actor=None,
                action_type="ADMIN_LOGIN_BLOCKED_PAUSED",
                target_type="User",
                target_id=str(candidate.id),
                metadata={"email": email},
                request=request,
            )
            raise ApplicationError(
                code="ACCOUNT_PAUSED",
                message="Your administrator account has been temporarily paused. Please contact the Super Admin to restore your access.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        user = authenticate(request, email=email, password=password)
        if user is None or not user.is_active:
            log_audit_event(
                actor=None,
                action_type="ADMIN_LOGIN_FAILED",
                target_type="User",
                target_id="",
                metadata={"email": email},
                request=request,
            )
            raise ApplicationError(
                code="INVALID_CREDENTIALS",
                message="Invalid email address or password.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        get_token(request)
        log_audit_event(
            actor=user,
            action_type="ADMIN_LOGIN",
            target_type="User",
            target_id=str(user.id),
            metadata={"role": user.role},
            request=request,
        )
        return Response(AdminMeSerializer(_with_generated_count(user)).data)


class LogoutView(APIView):
    permission_classes = [IsActiveAdmin]

    def post(self, request):
        log_audit_event(
            actor=request.user,
            action_type="ADMIN_LOGOUT",
            target_type="User",
            target_id=str(request.user.id),
            request=request,
        )
        logout(request)
        return Response({"status": "logged_out"})


class MeView(APIView):
    permission_classes = [IsActiveAdmin]

    def get(self, request):
        return Response(AdminMeSerializer(_with_generated_count(request.user)).data)

    def patch(self, request):
        display_name = str(request.data.get("display_name", "")).strip()
        if not display_name or len(display_name) > 120:
            raise ApplicationError(
                code="VALIDATION_ERROR",
                message="Display name must be between 1 and 120 characters.",
            )
        request.user.display_name = display_name
        request.user.save(update_fields=["display_name", "updated_at"])
        log_audit_event(
            actor=request.user,
            action_type="ADMIN_PROFILE_UPDATED",
            target_type="User",
            target_id=str(request.user.id),
            request=request,
        )
        return Response(AdminMeSerializer(_with_generated_count(request.user)).data)


class PasswordChangeView(APIView):
    permission_classes = [IsActiveAdmin]

    def post(self, request):
        enforce_rate_limit(
            request,
            scope="auth_password_change",
            key=str(request.user.id),
            limit=6,
            window_seconds=600,
        )
        serializer = PasswordChangeSerializer(data=request.data, context={"user": request.user})
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["current_password"]):
            raise ApplicationError(
                code="INVALID_CURRENT_PASSWORD",
                message="Current password is incorrect.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password", "updated_at"])
        update_session_auth_hash(request, request.user)
        log_audit_event(
            actor=request.user,
            action_type="ADMIN_PASSWORD_CHANGED",
            target_type="User",
            target_id=str(request.user.id),
            request=request,
        )
        return Response({"status": "password_changed"})


@method_decorator(csrf_protect, name="dispatch")
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        enforce_rate_limit(request, scope="auth_forgot_password_ip", limit=6, window_seconds=900)
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        enforce_rate_limit(request, scope="auth_forgot_password_email", key=email, limit=4, window_seconds=900)

        with transaction.atomic():
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            if user is not None:
                raw_token = secrets.token_urlsafe(32)
                digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
                reset_record = PasswordResetToken.objects.create(
                    user=user,
                    token_digest=digest,
                    expires_at=timezone.now() + timedelta(hours=1),
                )
                from apps.communications.services import enqueue_password_reset_email

                reset_url = f"{settings.APP_BASE_URL}/admin/reset-password?token={raw_token}"
                enqueue_password_reset_email(user=user, reset_url=reset_url, reset_id=str(reset_record.id))
                log_audit_event(
                    actor=None,
                    action_type="ADMIN_PASSWORD_RESET_REQUESTED",
                    target_type="User",
                    target_id=str(user.id),
                    request=request,
                )

        return Response(
            {
                "status": "reset_requested",
                "message": "If an active administrator account matches that email, password reset instructions have been queued.",
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        enforce_rate_limit(request, scope="auth_reset_password_ip", limit=8, window_seconds=900)
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_token = serializer.validated_data["token"].strip()
        digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        now = timezone.now()

        with transaction.atomic():
            reset_token = (
                PasswordResetToken.objects.select_for_update()
                .select_related("user")
                .filter(token_digest=digest)
                .first()
            )
            if (
                reset_token is None
                or reset_token.used_at is not None
                or reset_token.expires_at <= now
                or not reset_token.user.is_active
            ):
                raise ApplicationError(
                    code="INVALID_RESET_TOKEN",
                    message="This password reset link is invalid or has expired.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            user = reset_token.user
            user.set_password(serializer.validated_data["new_password"])
            user.save(update_fields=["password", "updated_at"])
            reset_token.used_at = now
            reset_token.save(update_fields=["used_at"])
            PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(used_at=now)
            _invalidate_user_sessions(str(user.id))
            log_audit_event(
                actor=user,
                action_type="ADMIN_PASSWORD_RESET_COMPLETED",
                target_type="User",
                target_id=str(user.id),
                request=request,
            )

        return Response({"status": "password_reset"})


def _annotate_quota_usage(qs):
    from django.db.models import F, IntegerField, OuterRef, Subquery, Sum
    from django.db.models.functions import Coalesce

    from apps.invitations.models import MasterInvitationLink, MasterLinkStatus

    master_reserved_subq = (
        MasterInvitationLink.objects.filter(
            created_by=OuterRef("pk"),
            status__in=[MasterLinkStatus.ACTIVE, MasterLinkStatus.PAUSED],
        )
        .values("created_by")
        .annotate(total=Sum(F("max_tickets") - F("claimed_count")))
        .values("total")[:1]
    )
    return qs.annotate(
        _direct_count=Count("generated_invitations", distinct=True),
        _master_reserved=Coalesce(Subquery(master_reserved_subq, output_field=IntegerField()), 0),
        invitations_generated_count=F("_direct_count") + F("_master_reserved"),
    )


class AdminUserListCreateView(ListCreateAPIView):
    permission_classes = [IsSuperAdmin]

    def get_queryset(self):
        qs = _annotate_quota_usage(User.objects.all()).order_by("display_name", "email")
        search = self.request.query_params.get("search", "").strip()
        is_active = self.request.query_params.get("is_active", "").strip().lower()
        if search:
            qs = qs.filter(Q(display_name__icontains=search) | Q(email__icontains=search))
        if is_active in {"true", "false"}:
            qs = qs.filter(is_active=(is_active == "true"))
        return qs

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminUserCreateSerializer
        return AdminMeSerializer

    def create(self, request, *args, **kwargs):
        serializer = AdminUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = serializer.save()
            log_audit_event(
                actor=request.user,
                action_type="ADMIN_USER_CREATED",
                target_type="User",
                target_id=str(user.id),
                metadata={
                    "created_email": user.email,
                    "role": user.role,
                    "invitation_limit": user.invitation_limit,
                },
                request=request,
            )
        return Response(AdminMeSerializer(_with_generated_count(user)).data, status=status.HTTP_201_CREATED)


class AdminUserDetailView(RetrieveUpdateAPIView):
    permission_classes = [IsSuperAdmin]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return _annotate_quota_usage(User.objects.all())

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return AdminUserUpdateSerializer
        return AdminMeSerializer

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            target = get_object_or_404(User.objects.select_for_update(), pk=kwargs["pk"])
            serializer = AdminUserUpdateSerializer(target, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)

            new_role = serializer.validated_data.get("role", target.role)
            if target.role == AdminRole.SUPER_ADMIN and new_role != AdminRole.SUPER_ADMIN:
                _assert_not_last_super_admin(target, demoting=True)

            password = serializer.validated_data.pop("password", None)
            for field, val in serializer.validated_data.items():
                setattr(target, field, val)
            if password:
                target.set_password(password)
                if target.id != request.user.id:
                    _invalidate_user_sessions(str(target.id))
            target.save()

            log_audit_event(
                actor=request.user,
                action_type="ADMIN_USER_UPDATED",
                target_type="User",
                target_id=str(target.id),
                metadata={
                    "role": target.role,
                    "invitation_limit": target.invitation_limit,
                    "password_updated": bool(password),
                },
                request=request,
            )

        return Response(AdminMeSerializer(_with_generated_count(target)).data)


class AdminUserActivateView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        with transaction.atomic():
            target = get_object_or_404(User.objects.select_for_update(), pk=pk)
            if not target.is_active:
                target.is_active = True
                target.save(update_fields=["is_active", "updated_at"])
                log_audit_event(
                    actor=request.user,
                    action_type="ADMIN_USER_RESUMED",
                    target_type="User",
                    target_id=str(target.id),
                    metadata={"email": target.email, "role": target.role},
                    request=request,
                )
        return Response(AdminMeSerializer(_with_generated_count(target)).data)


class AdminUserDeactivateView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        with transaction.atomic():
            target = get_object_or_404(User.objects.select_for_update(), pk=pk)
            if target.role == AdminRole.SUPER_ADMIN:
                raise ApplicationError(
                    code="SUPER_ADMIN_NOT_PAUSABLE",
                    message="Super Admin accounts cannot be paused.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            if target.is_active:
                target.is_active = False
                target.save(update_fields=["is_active", "updated_at"])
                _invalidate_user_sessions(str(target.id))
                log_audit_event(
                    actor=request.user,
                    action_type="ADMIN_USER_PAUSED",
                    target_type="User",
                    target_id=str(target.id),
                    metadata={"email": target.email, "role": target.role},
                    request=request,
                )
        return Response(AdminMeSerializer(_with_generated_count(target)).data)
