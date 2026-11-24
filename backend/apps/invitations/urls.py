from django.urls import path

from .views import (
    BulkInvitationCreateView,
    ClaimReceiptSharingView,
    ClaimReceiptView,
    GuestInviteClaimView,
    GuestInviteInspectView,
    InvitationClaimLinkView,
    InvitationCorrectGuestView,
    InvitationDeliveriesView,
    InvitationDetailView,
    InvitationExportCsvView,
    InvitationListCreateView,
    InvitationResendView,
    InvitationRevokeView,
    PublicShareDetailView,
    PublicShareImageView,
)

admin_invitations_urlpatterns = [
    path("", InvitationListCreateView.as_view(), name="invitations-list-create"),
    path("bulk/", BulkInvitationCreateView.as_view(), name="invitations-bulk"),
    path("export/", InvitationExportCsvView.as_view(), name="invitations-export"),
    path("<uuid:pk>/", InvitationDetailView.as_view(), name="invitations-detail"),
    path("<uuid:pk>/claim-link/", InvitationClaimLinkView.as_view(), name="invitations-claim-link"),
    path("<uuid:pk>/revoke/", InvitationRevokeView.as_view(), name="invitations-revoke"),
    path("<uuid:pk>/resend/", InvitationResendView.as_view(), name="invitations-resend"),
    path("<uuid:pk>/correct-guest/", InvitationCorrectGuestView.as_view(), name="invitations-correct-guest"),
    path("<uuid:pk>/deliveries/", InvitationDeliveriesView.as_view(), name="invitations-deliveries"),
]

guest_invite_urlpatterns = [
    path("<str:token>/", GuestInviteInspectView.as_view(), name="guest-invite-inspect"),
    path("<str:token>/claim/", GuestInviteClaimView.as_view(), name="guest-invite-claim"),
]

claim_receipt_urlpatterns = [
    path("", ClaimReceiptView.as_view(), name="claim-receipt-detail"),
    path("sharing/", ClaimReceiptSharingView.as_view(), name="claim-receipt-sharing"),
]

public_share_urlpatterns = [
    path("<str:token>/", PublicShareDetailView.as_view(), name="public-share-detail"),
    path("<str:token>/image/", PublicShareImageView.as_view(), name="public-share-image"),
]
