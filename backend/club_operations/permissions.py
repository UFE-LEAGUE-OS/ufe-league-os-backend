from rest_framework import permissions


class IsClubAdminOrSuperAdmin(permissions.IsAuthenticated):
    """
    Allows access only to club administrators and super administrators.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.role in ["CLUB_ADMIN", "SUPER_ADMIN"]


class IsClubAdminOrSuperAdminReadOnly(permissions.IsAuthenticated):
    """
    Allows read-only access to authenticated users.
    Allows write access only to club administrators and super administrators.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return user.role in ["CLUB_ADMIN", "SUPER_ADMIN"]
