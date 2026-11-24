from rest_framework.permissions import BasePermission


class IsActiveAdmin(BasePermission):
    message = "Active administrator authentication is required."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_active)


class IsSuperAdmin(BasePermission):
    message = "Super administrator privileges are required."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_active and user.is_super_admin)
