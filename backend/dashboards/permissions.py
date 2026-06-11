from rest_framework.permissions import BasePermission

from accounts.models import User


class HasDashboardRole(BasePermission):
    """Base Permission for dashboard role"""

    allowed_roles = []

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in self.allowed_roles
        )


class IsFan(HasDashboardRole):
    allowed_roles = [User.Role.FAN]


class IsClubAdmin(HasDashboardRole):
    allowed_roles = [User.Role.CLUB_ADMIN]


class IsLeagueAdmin(HasDashboardRole):
    allowed_roles = [User.Role.LEAGUE_ADMIN]


class IsUnionAdmin(HasDashboardRole):
    allowed_roles = [User.Role.UNION_ADMIN]


class IsSuperAdmin(HasDashboardRole):
    allowed_roles = [User.Role.SUPER_ADMIN]


class IsReferee(HasDashboardRole):
    allowed_roles = [User.Role.REFEREE]


class IsTicketingOfficer(HasDashboardRole):
    allowed_roles = [User.Role.TICKETING_OFFICER]


class IsSponsor(HasDashboardRole):
    allowed_roles = [User.Role.SPONSOR]
