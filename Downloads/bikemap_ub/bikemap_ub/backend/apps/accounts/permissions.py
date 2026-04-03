from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsCyclistOrAbove(BasePermission):
    """Authenticated non-banned cyclist, moderator, or admin."""
    def has_permission(self, request, view):
        return (request.user and request.user.is_authenticated
                and not request.user.is_banned)


class IsModeratorOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return (request.user and request.user.is_authenticated
                and request.user.is_admin_or_mod
                and not request.user.is_banned)


class IsAdminOnly(BasePermission):
    def has_permission(self, request, view):
        return (request.user and request.user.is_authenticated
                and request.user.role == "admin")


class IsOwnerOrMod(BasePermission):
    """Owner can edit; moderator/admin can always edit."""
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        owner = getattr(obj, "user", getattr(obj, "author", None))
        return (request.user == owner or request.user.is_admin_or_mod)