from django.urls import path

from .views import (
    AdminUserActivateView,
    AdminUserDeactivateView,
    AdminUserDetailView,
    AdminUserListCreateView,
    CsrfBootstrapView,
    ForgotPasswordView,
    LoginView,
    LogoutView,
    MeView,
    PasswordChangeView,
    ResetPasswordView,
)

auth_urlpatterns = [
    path("csrf/", CsrfBootstrapView.as_view(), name="auth-csrf"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("password/change/", PasswordChangeView.as_view(), name="auth-password-change"),
    path("password/forgot/", ForgotPasswordView.as_view(), name="auth-password-forgot"),
    path("password/reset/", ResetPasswordView.as_view(), name="auth-password-reset"),
]

users_urlpatterns = [
    path("", AdminUserListCreateView.as_view(), name="users-list-create"),
    path("<uuid:pk>/", AdminUserDetailView.as_view(), name="users-detail"),
    path("<uuid:pk>/activate/", AdminUserActivateView.as_view(), name="users-activate"),
    path("<uuid:pk>/deactivate/", AdminUserDeactivateView.as_view(), name="users-deactivate"),
]
