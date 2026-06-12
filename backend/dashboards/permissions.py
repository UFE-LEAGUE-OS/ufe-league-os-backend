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


class IsSponsor(BasePermission):
    """
    Allows access to users who either have the legacy SPONSOR role
    or belong to at least one active sponsor account.
    """

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.role == User.Role.SPONSOR:
            return True

        return user.sponsor_memberships.filter(is_active=True).exists()
