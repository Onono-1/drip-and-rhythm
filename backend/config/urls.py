from django.conf import settings
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.accounts.permissions import IsActiveAdmin
from apps.accounts.urls import auth_urlpatterns, users_urlpatterns
from apps.checkins.views import (
    CheckInCreateView,
    CheckInExportCsvView,
    CheckInListView,
    DashboardStatsView,
    HealthCheckView,
    VerifyManualView,
    VerifyQrView,
)
from apps.communications.views import AdminProcessPendingEmailsView
from apps.invitations.urls import (
    admin_invitations_urlpatterns,
    claim_receipt_urlpatterns,
    guest_invite_urlpatterns,
    public_share_urlpatterns,
)

schema_perms = [] if settings.DEBUG else [IsActiveAdmin]

urlpatterns = [
    path("api/health/", HealthCheckView.as_view(), name="api-health"),
    path("api/auth/", include((auth_urlpatterns, "auth"))),
    path("api/event/", include("apps.events.urls")),
    path("api/users/", include((users_urlpatterns, "users"))),
    path("api/invitations/", include((admin_invitations_urlpatterns, "invitations"))),
    path("api/invite/", include((guest_invite_urlpatterns, "guest-invite"))),
    path("api/claim-receipt/", include((claim_receipt_urlpatterns, "claim-receipt"))),
    path("api/share/", include((public_share_urlpatterns, "public-share"))),
    path("api/verify/", VerifyQrView.as_view(), name="verify-qr"),
    path("api/verify/manual/", VerifyManualView.as_view(), name="verify-manual"),
    path("api/check-in/", CheckInCreateView.as_view(), name="checkin-create"),
    path("api/check-ins/", CheckInListView.as_view(), name="checkin-list"),
    path("api/check-ins/export/", CheckInExportCsvView.as_view(), name="checkin-export"),
    path("api/dashboard/", DashboardStatsView.as_view(), name="admin-dashboard"),
    path("api/audit-logs/", include("apps.audit.urls")),
    path(
        "api/emails/process-pending/",
        AdminProcessPendingEmailsView.as_view(),
        name="emails-process-pending",
    ),
    path("api/webhooks/", include("apps.communications.urls")),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=schema_perms),
        name="api-schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema", permission_classes=schema_perms),
        name="api-docs",
    ),
]
