from rest_framework.permissions import BasePermission, IsAuthenticated

from .rbac import has_role_permission, log_access_violation


class IsAuthenticatedAudit(IsAuthenticated):
    def has_permission(self, request, view):
        allowed = super().has_permission(request, view)

        if not allowed:
            status_code = 401
            if getattr(request.user, "is_authenticated", False):
                status_code = 403

            log_access_violation(
                request,
                status_code=status_code,
                detail={"permission": "authenticated"},
            )

        return allowed


class HasRolePermission(BasePermission):
    permission_name = None

    def has_permission(self, request, view):
        user = getattr(request, "user", None)

        if not user or not getattr(user, "is_authenticated", False):
            log_access_violation(
                request,
                status_code=401,
                detail={"permission": self.permission_name},
            )
            return False

        if not self.permission_name:
            return False

        allowed = has_role_permission(user, self.permission_name)

        if not allowed:
            log_access_violation(
                request,
                status_code=403,
                detail={"permission": self.permission_name},
            )

        return allowed


class IsFan(HasRolePermission):
    permission_name = "dashboard.fan"


class IsClubAdmin(HasRolePermission):
    permission_name = "dashboard.club_admin"


class IsLeagueAdmin(HasRolePermission):
    permission_name = "dashboard.league_admin"


class IsUnionAdmin(HasRolePermission):
    permission_name = "dashboard.union_admin"


class IsSuperAdmin(HasRolePermission):
    permission_name = "dashboard.super_admin"


class IsReferee(HasRolePermission):
    permission_name = "dashboard.referee"


class IsTicketingOfficer(HasRolePermission):
    permission_name = "dashboard.ticketing_officer"


class IsSponsor(HasRolePermission):
    permission_name = "dashboard.sponsor"
