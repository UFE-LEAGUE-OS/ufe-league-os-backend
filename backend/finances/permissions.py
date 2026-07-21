from rest_framework.permissions import BasePermission

from accounts.models import User


class CanAccessClubFinance(BasePermission):
    """
    Grants access to users who are:
    - Club Administrator (CLUB_ADMIN)
    - Club Admin Scope roles (CHAIRMAN, TREASURER, etc.)
    - League Admin (LEAGUE_ADMIN)
    - Union Admin (UNION_ADMIN)
    - Super Admin (SUPER_ADMIN)
    - Finance Officer (via union workspace)
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.role in {
            User.Role.CLUB_ADMIN,
            User.Role.LEAGUE_ADMIN,
            User.Role.UNION_ADMIN,
            User.Role.SUPER_ADMIN,
        }:
            return True

        # Check if user has a club admin scope with finance-relevant role
        if hasattr(user, "club_admin_scopes"):
            scope_roles = user.club_admin_scopes.filter(
                is_active=True,
            ).values_list("role", flat=True)
            for role in scope_roles:
                if role in (
                    "CLUB_ADMIN",
                    "CHAIRMAN",
                    "TREASURER",
                    "TEAM_MANAGER",
                ):
                    return True

        # Check if user is finance officer in a union workspace
        if hasattr(user, "union_workspace_memberships"):
            if user.union_workspace_memberships.filter(
                is_active=True,
                role__in=("FINANCE_OFFICER", "OWNER", "UNION_ADMIN"),
            ).exists():
                return True

        return False

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role == User.Role.SUPER_ADMIN:
            return True

        # Check if the object belongs to the user's club
        obj_club = getattr(obj, "club", None)
        if obj_club is None:
            return True

        user_club = getattr(user, "club", None)
        if user_club and obj_club == user_club:
            return True

        # Check via club admin scopes
        if hasattr(user, "club_admin_scopes"):
            if user.club_admin_scopes.filter(club=obj_club, is_active=True).exists():
                return True

        return False


class IsFinanceAuditor(BasePermission):
    """
    Grants audit log view access to authorized users.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.role in {
            User.Role.CLUB_ADMIN,
            User.Role.SUPER_ADMIN,
            User.Role.LEAGUE_ADMIN,
            User.Role.UNION_ADMIN,
        }:
            return True

        # Check if user has a club assigned directly
        if user.role == User.Role.CLUB_ADMIN and user.club_id:
            return True

        if hasattr(user, "club_admin_scopes"):
            if user.club_admin_scopes.filter(
                is_active=True,
                role__in=("CLUB_ADMIN", "CHAIRMAN", "TREASURER"),
            ).exists():
                return True

        if hasattr(user, "union_workspace_memberships"):
            if user.union_workspace_memberships.filter(
                is_active=True,
                role__in=("FINANCE_OFFICER", "OWNER", "UNION_ADMIN"),
            ).exists():
                return True

        return False
