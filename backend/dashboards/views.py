from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.models import Club, User
from accounts.dashboard_entitlements import resolve_dashboard_access
from accounts.rbac import (
    get_club_admin_sub_role,
    get_user_permissions,
    log_access_violation,
)
from accounts.permissions import IsAuthenticatedAudit
from accounts.serializers import (
    CurrentUserSerializer,
    entitlement_legacy_role,
    present_dashboard_access,
    select_dashboard_route_for_role,
)

from .models import (
    Competition,
    League,
    LeagueClubMembership,
    FixtureOfficialAssignment,
    Match,
    NationalTeam,
    Standing,
    UnionMatchOfficial,
    UnionRegistrationApplication,
    Union,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
from accounts.models import ClubAdminScope
from .serializers import (
    ClubListSerializer,
    CompetitionSerializer,
    LeagueSerializer,
    MatchDetailSerializer,
    MatchListSerializer,
    StandingSerializer,
    UnionSerializer,
    UnionWorkspaceMembershipSerializer,
    UnionWorkspaceUserSerializer,
)
from .services import recalculate_standings
from monitoring.models import PaymentAudit, TransactionReconciliation

# Create your views here.

DASHBOARD_CONTENT = {
    User.Role.FAN: {
        "title": "Fan Dashboard",
        "description": "Follow teams, view fixtures, buy tickets, and manage memberships.",
        "summary_cards": [
            {"label": "Followed Teams", "value": 0},
            {"label": "Upcoming Fixtures", "value": 0},
            {"label": "Active Memberships", "value": 0},
            {"label": "Tickets", "value": 0},
        ],
        "modules": [
            "Fixtures",
            "Results",
            "Standings",
            "Tickets",
            "Memberships",
            "Fantasy League",
            "Polls",
            "News",
        ],
        "quick_actions": [
            "Follow a team",
            "Browse fixtures",
            "Buy a ticket",
            "Join membership",
        ],
    },
    User.Role.CLUB_ADMIN: {
        "title": "Club Admin Dashboard",
        "description": "Manage club profile, fans, memberships, ticketing, and club content.",
        "summary_cards": [
            {"label": "Club Fans", "value": 0},
            {"label": "Memberships", "value": 0},
            {"label": "Ticket Sales", "value": 0},
            {"label": "Club Posts", "value": 0},
        ],
        "modules": [
            "Club Profile",
            "Squad",
            "Fixtures",
            "Memberships",
            "Ticketing",
            "Fan Engagement",
            "Club Reports",
        ],
        "quick_actions": [
            "Update club profile",
            "Create club post",
            "Review memberships",
            "View ticket sales",
        ],
    },
    User.Role.LEAGUE_ADMIN: {
        "title": "League Admin Dashboard",
        "description": "Manage competitions, fixtures, results, standings, and match officials.",
        "summary_cards": [
            {"label": "Competitions", "value": 0},
            {"label": "Fixtures", "value": 0},
            {"label": "Registered Clubs", "value": 0},
            {"label": "Match Officials", "value": 0},
        ],
        "modules": [
            "Competitions",
            "Fixtures",
            "Results",
            "Standings",
            "Disciplinary",
            "Match Officials",
            "League Reports",
        ],
        "quick_actions": [
            "Create fixture",
            "Update result",
            "Review standings",
            "Assign official",
        ],
    },
    User.Role.UNION_ADMIN: {
        "title": "Union Admin Dashboard",
        "description": "Oversee leagues, competitions, clubs, referees, and player registration approvals.",
        "summary_cards": [
            {"label": "Leagues", "value": 0},
            {"label": "Competitions", "value": 0},
            {"label": "Clubs", "value": 0},
            {"label": "Pending Approvals", "value": 0},
        ],
        "modules": [
            "Leagues",
            "Competitions",
            "Club Registration",
            "Player Approvals",
            "Referees",
            "Union Reports",
        ],
        "quick_actions": [
            "Create competition",
            "Approve registration",
            "Register referee",
            "Review union activity",
        ],
    },
    User.Role.REFEREE: {
        "title": "Match Official Dashboard",
        "description": "Manage match appointments, assigned responsibilities, reports, and availability.",
        "summary_cards": [
            {"label": "Match Appointments", "value": 0},
            {"label": "Upcoming Matches", "value": 0},
            {"label": "Reports Due", "value": 0},
            {"label": "Payments", "value": 0},
        ],
        "modules": [
            "Assigned Responsibilities",
            "Match Reports",
            "Availability",
            "Documents and Certification",
            "Allowances and Payments",
        ],
        "quick_actions": [
            "View match appointment",
            "Submit match report",
            "Update availability",
        ],
    },
    User.Role.TICKETING_OFFICER: {
        "title": "Ticketing Officer Dashboard",
        "description": "Manage match tickets, ticket validation, and gate operations.",
        "summary_cards": [
            {"label": "Active Events", "value": 0},
            {"label": "Tickets Sold", "value": 0},
            {"label": "Tickets Checked In", "value": 0},
            {"label": "Pending Issues", "value": 0},
        ],
        "modules": [
            "Ticket Events",
            "QR Validation",
            "Gate Check-in",
            "Ticket Reports",
        ],
        "quick_actions": [
            "Validate ticket",
            "View event tickets",
            "Review gate report",
        ],
    },
    User.Role.SPONSOR: {
        "title": "Sponsor Dashboard",
        "description": "Track sponsorship placements, campaigns, engagement, and return on visibility.",
        "summary_cards": [
            {"label": "Campaigns", "value": 0},
            {"label": "Brand Placements", "value": 0},
            {"label": "Engagements", "value": 0},
            {"label": "Reports", "value": 0},
        ],
        "modules": [
            "Campaigns",
            "Brand Placements",
            "Engagement Analytics",
            "Sponsor Reports",
        ],
        "quick_actions": [
            "View campaign",
            "Review placements",
            "Download report",
        ],
    },
}


def _dashboard_presentation(request):
    user_data = CurrentUserSerializer(
        request.user,
        context={"request": request},
    ).data
    dashboard_access = user_data["dashboard_access"]
    _default_dashboard, available_dashboards = present_dashboard_access(
        dashboard_access
    )
    return user_data, dashboard_access, available_dashboards


def _matching_dashboard_entries(available_dashboards, role):
    return [item for item in available_dashboards if item["role"] == role]


def _dashboard_access_denied(request, role):
    log_access_violation(
        request,
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"permission": f"dashboard.{str(role).lower()}"},
    )
    return Response(
        {"detail": "You do not have active access to this dashboard."},
        status=status.HTTP_403_FORBIDDEN,
    )


def build_dashboard_response(request, role, message=None, presentation=None):
    """Build a consistent dashboard response for the authenticated user's role."""

    user = request.user
    content = DASHBOARD_CONTENT.get(role)

    if content is None:
        return Response(
            {"detail": "No dashboard is configured for this user role."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if presentation is None:
        presentation = _dashboard_presentation(request)
    user_data, _dashboard_access, available_dashboards = presentation
    if not _matching_dashboard_entries(available_dashboards, role):
        return _dashboard_access_denied(request, role)

    frontend_dashboard_route, backend_dashboard_route = select_dashboard_route_for_role(
        available_dashboards, role
    )

    success_message = message or f"{content['title']} loaded successfully."

    return Response(
        {
            "message": success_message,
            "role": user.role,
            "role_display": user.get_role_display(),
            "dashboard_role": role,
            "frontend_dashboard_route": frontend_dashboard_route,
            "backend_dashboard_route": backend_dashboard_route,
            "available_dashboards": available_dashboards,
            "dashboard": content,
            "user": user_data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def my_dashboard_view(request):
    """Return dashboard content selected by the user's default entitlement."""

    user = request.user
    user_data = CurrentUserSerializer(user, context={"request": request}).data
    dashboard_access = user_data["dashboard_access"]
    default_dashboard, available_dashboards = present_dashboard_access(dashboard_access)
    default_id = dashboard_access["default_entitlement_id"]
    default_entitlement = next(
        (item for item in dashboard_access["entitlements"] if item["id"] == default_id),
        None,
    )

    dashboard_role = None
    if default_entitlement:
        dashboard_role = {
            "FAN": User.Role.FAN,
            "SPONSOR": User.Role.SPONSOR,
            "SUPER_ADMIN": User.Role.SUPER_ADMIN,
            "LEAGUE_ADMIN": User.Role.LEAGUE_ADMIN,
            "CLUB_ADMIN": User.Role.CLUB_ADMIN,
            "TICKETING_OFFICER": User.Role.TICKETING_OFFICER,
        }.get(default_entitlement["dashboard"])
        if default_entitlement["dashboard"] == "UNION_WORKSPACE":
            if default_entitlement["workspace_role"] == "MATCH_OFFICIAL":
                dashboard_role = User.Role.REFEREE
            elif default_entitlement["workspace_role"] == "TICKETING_OFFICER":
                dashboard_role = User.Role.TICKETING_OFFICER
            else:
                dashboard_role = User.Role.UNION_ADMIN

    # Build dashboard content - use dynamic stats for Super Admin
    dashboard_content = None
    if dashboard_role == User.Role.SUPER_ADMIN:
        from accounts.models import AuditLog

        # Fetch real platform statistics from the database
        total_users = User.objects.count()
        total_unions = Union.objects.count()
        total_leagues = League.objects.count()
        total_clubs = Club.objects.count()
        total_audit_events = AuditLog.objects.count()

        dashboard_content = {
            "title": "Super Admin Dashboard",
            "description": "Monitor the full League OS platform, users, roles, tenants, and audit activity.",
            "summary_cards": [
                {"label": "Users", "value": total_users},
                {
                    "label": "Organizations",
                    "value": total_unions + total_leagues + total_clubs,
                },
                {"label": "Roles", "value": total_users},  # Users with roles
                {"label": "Audit Events", "value": total_audit_events},
            ],
            "modules": [
                "Users",
                "Roles",
                "Organizations",
                "Platform Settings",
                "Audit Logs",
                "System Health",
            ],
            "quick_actions": [
                "Review users",
                "Monitor system health",
                "View audit activity",
                "Manage platform settings",
            ],
        }
    else:
        dashboard_content = DASHBOARD_CONTENT.get(dashboard_role)

    return Response(
        {
            "message": (
                "Dashboard resolved successfully."
                if dashboard_role
                else "Dashboard access is unavailable."
            ),
            "role": user.role,
            "role_display": user.get_role_display(),
            "dashboard_role": dashboard_role,
            "frontend_dashboard_route": (
                default_dashboard["route"] if default_dashboard else None
            ),
            "backend_dashboard_route": (
                default_dashboard["backend_route"] if default_dashboard else None
            ),
            "available_dashboards": available_dashboards,
            "dashboard": dashboard_content,
            "user": user_data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def fan_dashboard_view(request):
    return build_dashboard_response(request, User.Role.FAN)


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def club_admin_dashboard_view(request):
    user = request.user
    presentation = _dashboard_presentation(request)
    user_data, dashboard_access, available_dashboards = presentation
    matching_entries = _matching_dashboard_entries(
        available_dashboards,
        User.Role.CLUB_ADMIN,
    )
    if not matching_entries:
        return _dashboard_access_denied(request, User.Role.CLUB_ADMIN)

    if len(matching_entries) != 1:
        return build_dashboard_response(
            request,
            User.Role.CLUB_ADMIN,
            presentation=presentation,
        )

    entitlement = next(
        (
            item
            for item in dashboard_access["entitlements"]
            if item["id"] == matching_entries[0]["entitlement_id"]
        ),
        None,
    )
    scope = (
        ClubAdminScope.objects.filter(
            user=user,
            is_active=True,
            club_id=entitlement["scope_id"] if entitlement else None,
        )
        .select_related("club")
        .first()
    )

    if not scope:
        return build_dashboard_response(
            request,
            User.Role.CLUB_ADMIN,
            presentation=presentation,
        )

    # Get all permissions (base role + club scope)
    permissions = get_user_permissions(user)

    # Get sub-role info
    sub_role_info = get_club_admin_sub_role(user)

    # Define menu items based on permissions
    menu_items = []

    if "club.profile.view" in permissions:
        menu_items.append(
            {
                "id": "club-profile",
                "label": "Club Profile",
                "icon": "club",
                "path": "/dashboard/club-admin/profile",
                "permissions": ["club.profile.view"],
            }
        )

    if "club.squad.manage" in permissions:
        menu_items.append(
            {
                "id": "squad",
                "label": "Squad Management",
                "icon": "people",
                "path": "/dashboard/club-admin/squad",
                "permissions": ["club.squad.manage"],
            }
        )

    if "club.members.manage" in permissions:
        menu_items.append(
            {
                "id": "members",
                "label": "Memberships",
                "icon": "membership",
                "path": "/dashboard/club-admin/members",
                "permissions": ["club.members.manage"],
            }
        )

    if "club.ticketing.manage" in permissions:
        menu_items.append(
            {
                "id": "ticketing",
                "label": "Ticketing",
                "icon": "ticket",
                "path": "/dashboard/club-admin/ticketing",
                "permissions": ["club.ticketing.manage"],
            }
        )

    if "club.events.manage" in permissions:
        menu_items.append(
            {
                "id": "events",
                "label": "Events & Matchday",
                "icon": "event",
                "path": "/dashboard/club-admin/events",
                "permissions": ["club.events.manage"],
            }
        )

    if "club.reports.view" in permissions:
        menu_items.append(
            {
                "id": "reports",
                "label": "Reports",
                "icon": "analytics",
                "path": "/dashboard/club-admin/reports",
                "permissions": ["club.reports.view"],
            }
        )

    if "club.finance.view" in permissions or "club.finance.manage" in permissions:
        menu_items.append(
            {
                "id": "finance",
                "label": "Finance",
                "icon": "finance",
                "path": "/dashboard/club-admin/finance",
                "permissions": ["club.finance.view", "club.finance.manage"],
            }
        )

    if "club.admin.manage" in permissions or "club.settings.manage" in permissions:
        menu_items.append(
            {
                "id": "settings",
                "label": "Club Settings",
                "icon": "settings",
                "path": "/dashboard/club-admin/settings",
                "permissions": ["club.admin.manage", "club.settings.manage"],
            }
        )

    # Dynamically build dashboard content based on permissions
    dashboard_content = {
        "title": f"{scope.club.name} Admin",
        "description": f"Manage operations for {scope.club.name}.",
        "sub_role": sub_role_info,
        "summary_cards": [],
        "modules": [item["label"] for item in menu_items],
        "quick_actions": [
            item["label"] for item in menu_items[:4]
        ],  # First 4 as quick actions
        "menu_items": menu_items,
        "permissions": sorted(list(permissions)),
    }

    frontend_dashboard_route, backend_dashboard_route = select_dashboard_route_for_role(
        available_dashboards,
        User.Role.CLUB_ADMIN,
    )

    return Response(
        {
            "message": f"{dashboard_content['title']} loaded successfully.",
            "role": user.role,
            "role_display": user.get_role_display(),
            "dashboard_role": User.Role.CLUB_ADMIN,
            "frontend_dashboard_route": frontend_dashboard_route,
            "backend_dashboard_route": backend_dashboard_route,
            "available_dashboards": available_dashboards,
            "dashboard": dashboard_content,
            "user": user_data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def league_admin_dashboard_view(request):
    return build_dashboard_response(request, User.Role.LEAGUE_ADMIN)


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_dashboard_view(request):
    presentation = _dashboard_presentation(request)
    _user_data, dashboard_access, _available_dashboards = presentation
    union_roles = {
        entitlement_legacy_role(item)
        for item in dashboard_access["entitlements"]
        if item["dashboard"] == "UNION_WORKSPACE"
    }
    if len(union_roles) != 1:
        return _dashboard_access_denied(request, User.Role.UNION_ADMIN)
    return build_dashboard_response(
        request,
        union_roles.pop(),
        presentation=presentation,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def super_admin_dashboard_view(request):
    """Return Super Admin dashboard with actual platform statistics."""
    from accounts.models import AuditLog

    # Fetch real platform statistics from the database
    total_users = User.objects.count()
    total_unions = Union.objects.count()
    total_leagues = League.objects.count()
    total_clubs = Club.objects.count()
    total_audit_events = AuditLog.objects.count()

    # Build dynamic dashboard content with real data
    dashboard_content = {
        "title": "Super Admin Dashboard",
        "description": "Monitor the full League OS platform, users, roles, tenants, and audit activity.",
        "summary_cards": [
            {"label": "Users", "value": total_users},
            {
                "label": "Organizations",
                "value": total_unions + total_leagues + total_clubs,
            },
            {"label": "Roles", "value": total_users},  # Users with roles
            {"label": "Audit Events", "value": total_audit_events},
        ],
        "modules": [
            "Users",
            "Roles",
            "Organizations",
            "Platform Settings",
            "Audit Logs",
            "System Health",
        ],
        "quick_actions": [
            "Review users",
            "Monitor system health",
            "View audit activity",
            "Manage platform settings",
        ],
    }

    user = request.user
    presentation = _dashboard_presentation(request)
    user_data, _dashboard_access, available_dashboards = presentation

    if not _matching_dashboard_entries(available_dashboards, User.Role.SUPER_ADMIN):
        return _dashboard_access_denied(request, User.Role.SUPER_ADMIN)

    frontend_dashboard_route, backend_dashboard_route = select_dashboard_route_for_role(
        available_dashboards, User.Role.SUPER_ADMIN
    )

    return Response(
        {
            "message": f"{dashboard_content['title']} loaded successfully.",
            "role": user.role,
            "role_display": user.get_role_display(),
            "dashboard_role": User.Role.SUPER_ADMIN,
            "frontend_dashboard_route": frontend_dashboard_route,
            "backend_dashboard_route": backend_dashboard_route,
            "available_dashboards": available_dashboards,
            "dashboard": dashboard_content,
            "user": user_data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def referee_dashboard_view(request):
    return build_dashboard_response(request, User.Role.REFEREE)


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def ticketing_officer_dashboard_view(request):
    return build_dashboard_response(request, User.Role.TICKETING_OFFICER)


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def sponsor_dashboard_view(request):
    return build_dashboard_response(request, User.Role.SPONSOR)


# ---------------------------------------------------------------------------
# Club Admin Sub-Role Detection & Menu APIs
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def club_admin_role_detection_view(request):
    """
    Return the current user's club admin sub-role information.
    This helps the frontend understand which sub-role the user has
    and personalize the UI accordingly.
    """
    sub_role_info = get_club_admin_sub_role(request.user)

    if not sub_role_info:
        return Response(
            {"detail": "No active club admin scope found for this user."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get permissions for this sub-role
    permissions = get_user_permissions(request.user)

    return Response(
        {
            "sub_role": sub_role_info,
            "permissions": sorted(list(permissions)),
            "role_display": sub_role_info["role_display"],
            "club_id": sub_role_info["club_id"],
            "club_name": sub_role_info["club_name"],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def club_admin_menu_items_view(request):
    """
    Return menu items for the club admin dashboard based on the user's
    sub-role permissions. This allows the frontend to dynamically build
    the navigation menu.
    """
    sub_role_info = get_club_admin_sub_role(request.user)

    if not sub_role_info:
        return Response(
            {"detail": "No active club admin scope found for this user."},
            status=status.HTTP_404_NOT_FOUND,
        )

    permissions = get_user_permissions(request.user)

    # Define menu items based on permissions
    menu_items = []

    if "club.profile.view" in permissions:
        menu_items.append(
            {
                "id": "club-profile",
                "label": "Club Profile",
                "icon": "club",
                "path": "/dashboard/club-admin/profile",
                "permissions": ["club.profile.view"],
            }
        )

    if "club.squad.manage" in permissions:
        menu_items.append(
            {
                "id": "squad",
                "label": "Squad Management",
                "icon": "people",
                "path": "/dashboard/club-admin/squad",
                "permissions": ["club.squad.manage"],
            }
        )

    if "club.members.manage" in permissions:
        menu_items.append(
            {
                "id": "members",
                "label": "Memberships",
                "icon": "membership",
                "path": "/dashboard/club-admin/members",
                "permissions": ["club.members.manage"],
            }
        )

    if "club.ticketing.manage" in permissions:
        menu_items.append(
            {
                "id": "ticketing",
                "label": "Ticketing",
                "icon": "ticket",
                "path": "/dashboard/club-admin/ticketing",
                "permissions": ["club.ticketing.manage"],
            }
        )

    if "club.events.manage" in permissions:
        menu_items.append(
            {
                "id": "events",
                "label": "Events & Matchday",
                "icon": "event",
                "path": "/dashboard/club-admin/events",
                "permissions": ["club.events.manage"],
            }
        )

    if "club.reports.view" in permissions:
        menu_items.append(
            {
                "id": "reports",
                "label": "Reports",
                "icon": "analytics",
                "path": "/dashboard/club-admin/reports",
                "permissions": ["club.reports.view"],
            }
        )

    if "club.finance.view" in permissions or "club.finance.manage" in permissions:
        menu_items.append(
            {
                "id": "finance",
                "label": "Finance",
                "icon": "finance",
                "path": "/dashboard/club-admin/finance",
                "permissions": ["club.finance.view", "club.finance.manage"],
            }
        )

    if "club.admin.manage" in permissions or "club.settings.manage" in permissions:
        menu_items.append(
            {
                "id": "settings",
                "label": "Club Settings",
                "icon": "settings",
                "path": "/dashboard/club-admin/settings",
                "permissions": ["club.admin.manage", "club.settings.manage"],
            }
        )

    if "club.transfers.manage" in permissions:
        menu_items.append(
            {
                "id": "transfers",
                "label": "Transfers",
                "icon": "transfer",
                "path": "/dashboard/club-admin/transfers",
                "permissions": ["club.transfers.manage"],
            }
        )

    if (
        "club.sponsorship.view" in permissions
        or "club.sponsorship.manage" in permissions
    ):
        menu_items.append(
            {
                "id": "sponsorship",
                "label": "Sponsorship",
                "icon": "sponsor",
                "path": "/dashboard/club-admin/sponsorship",
                "permissions": ["club.sponsorship.view", "club.sponsorship.manage"],
            }
        )

    if "club.training.manage" in permissions:
        menu_items.append(
            {
                "id": "training",
                "label": "Training",
                "icon": "training",
                "path": "/dashboard/club-admin/training",
                "permissions": ["club.training.manage"],
            }
        )

    if "club.matches.manage" in permissions:
        menu_items.append(
            {
                "id": "matches",
                "label": "Matches",
                "icon": "match",
                "path": "/dashboard/club-admin/matches",
                "permissions": ["club.matches.manage"],
            }
        )

    if "club.ticketing.validate" in permissions:
        menu_items.append(
            {
                "id": "validation",
                "label": "Ticket Validation",
                "icon": "qr-code",
                "path": "/dashboard/club-admin/validation",
                "permissions": ["club.ticketing.validate"],
            }
        )

    return Response(
        {
            "sub_role": sub_role_info,
            "menu_items": menu_items,
            "total_items": len(menu_items),
            "permissions": sorted(list(permissions)),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def club_admin_workspace_context_view(request):
    """
    Return the workspace context for the club admin user.
    This includes club information, sub-role, and available permissions.
    """
    sub_role_info = get_club_admin_sub_role(request.user)

    if not sub_role_info:
        return Response(
            {"detail": "No active club admin scope found for this user."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get the club details
    club = Club.objects.filter(id=sub_role_info["club_id"]).first()

    if not club:
        return Response(
            {"detail": "Club not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get all active scopes for this user
    active_scopes = request.user.club_admin_scopes.filter(is_active=True)

    permissions = get_user_permissions(request.user)

    return Response(
        {
            "workspace": {
                "type": "club",
                "club": {
                    "id": club.id,
                    "name": club.name,
                    "slug": club.slug,
                    "short_name": club.short_name,
                    "sport": club.sport,
                    "logo": (
                        request.build_absolute_uri(club.logo.url) if club.logo else None
                    ),
                    "banner": (
                        request.build_absolute_uri(club.banner.url)
                        if club.banner
                        else None
                    ),
                    "primary_color": club.primary_color,
                    "secondary_color": club.secondary_color,
                },
            },
            "sub_role": sub_role_info,
            "permissions": sorted(list(permissions)),
            "active_scopes": [
                {
                    "id": scope.id,
                    "role": scope.role,
                    "role_display": scope.get_role_display(),
                    "club_id": scope.club.id,
                    "club_name": scope.club.name,
                    "is_active": scope.is_active,
                }
                for scope in active_scopes
            ],
            "dashboard_route": "/dashboard/club-admin",
            "backend_route": "/api/dashboards/club-admin/",
        }
    )


# ---------------------------------------------------------------------------
# Public / No-Auth Endpoints
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([AllowAny])
def public_fixtures_view(request):
    """
    Public endpoint: return upcoming/pending fixtures.
    No authentication required.
    """
    now = timezone.now()
    competition_id = request.query_params.get("competition")
    club_id = request.query_params.get("club")

    queryset = Match.objects.filter(
        status__in=[Match.Status.SCHEDULED, Match.Status.POSTPONED],
        match_date__gte=now,
    ).select_related("competition", "home_club", "away_club")

    if competition_id:
        queryset = queryset.filter(competition_id=competition_id)
    if club_id:
        queryset = queryset.filter(home_club_id=club_id) | queryset.filter(
            away_club_id=club_id
        )

    queryset = queryset.order_by("match_date")
    serializer = MatchListSerializer(queryset, many=True, context={"request": request})
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_results_view(request):
    """
    Public endpoint: return completed match results.
    No authentication required.
    """
    competition_id = request.query_params.get("competition")
    club_id = request.query_params.get("club")
    limit_param = request.query_params.get("limit", 50)
    try:
        limit = int(limit_param)
    except (ValueError, TypeError):
        limit = 50

    queryset = Match.objects.filter(status=Match.Status.COMPLETED).select_related(
        "competition", "home_club", "away_club"
    )

    if competition_id:
        queryset = queryset.filter(competition_id=competition_id)
    if club_id:
        queryset = queryset.filter(home_club_id=club_id) | queryset.filter(
            away_club_id=club_id
        )

    queryset = queryset.order_by("-match_date")[:limit]
    serializer = MatchListSerializer(queryset, many=True, context={"request": request})
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_standings_view(request):
    """
    Public endpoint: return standings/table for a competition.
    No authentication required.
    """
    competition_id = request.query_params.get("competition")

    if not competition_id:
        return Response(
            {"detail": "The 'competition' query parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    queryset = Standing.objects.filter(competition_id=competition_id).select_related(
        "club", "competition"
    )
    queryset = queryset.order_by("position")
    serializer = StandingSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_clubs_view(request):
    """
    Public endpoint: return a list of all clubs.
    No authentication required.
    """
    queryset = Club.objects.all().order_by("name")
    serializer = ClubListSerializer(queryset, many=True, context={"request": request})
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_unions_view(request):
    """
    Public endpoint: return a list of all unions/federations.
    No authentication required.
    """
    queryset = Union.objects.all().order_by("name")
    serializer = UnionSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_leagues_view(request):
    """
    Public endpoint: return a list of all leagues.
    No authentication required.
    """
    union_id = request.query_params.get("union")
    queryset = League.objects.all().select_related("union")
    if union_id:
        queryset = queryset.filter(union_id=union_id)
    queryset = queryset.order_by("name")
    serializer = LeagueSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_competitions_view(request):
    """
    Public endpoint: return a list of all competitions.
    No authentication required.
    """
    league_id = request.query_params.get("league")
    is_active = request.query_params.get("is_active")
    queryset = Competition.objects.all().select_related("league")
    if league_id:
        queryset = queryset.filter(league_id=league_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=(is_active.lower() == "true"))
    queryset = queryset.order_by("-start_date")
    serializer = CompetitionSerializer(queryset, many=True)
    return Response(serializer.data)


# ---------------------------------------------------------------------------
# Match Detail Endpoint
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([AllowAny])
def public_match_detail_view(request, match_id):
    """
    Public endpoint: return detailed info about a single match.
    No authentication required.
    """
    try:
        match = Match.objects.select_related(
            "competition", "home_club", "away_club"
        ).get(id=match_id)
    except Match.DoesNotExist:
        return Response(
            {"detail": "Match not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = MatchDetailSerializer(match, context={"request": request})
    return Response(serializer.data)


# ---------------------------------------------------------------------------
# Standings Calculation Endpoint
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([AllowAny])
def public_standings_calculation_view(request):
    """
    Public endpoint: trigger recalculation of standings for a competition
    and return the computed table. No authentication required.

    Query params:
        competition (required) -- ID of the competition to recalculate.
    """
    competition_id = request.query_params.get("competition")

    if not competition_id:
        return Response(
            {"detail": "The 'competition' query parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        competition = Competition.objects.get(id=competition_id)
    except Competition.DoesNotExist:
        return Response(
            {"detail": "Competition not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    updated_standings = recalculate_standings(competition_id)
    serializer = StandingSerializer(
        sorted(updated_standings, key=lambda s: s.position), many=True
    )
    return Response(
        {
            "competition_id": competition.id,
            "competition_name": competition.name,
            "entries": serializer.data,
        }
    )


def _get_active_union_workspace_memberships(user):
    return (
        UnionWorkspaceMembership.objects.filter(
            user=user,
            is_active=True,
            workspace__status=UnionWorkspace.Status.ACTIVE,
        )
        .select_related("workspace", "workspace__related_union")
        .order_by("workspace__name")
    )


def _get_union_membership_for_request(user, workspace_value=None):
    queryset = _get_active_union_workspace_memberships(user)

    if workspace_value:
        queryset = queryset.filter(
            models.Q(workspace__slug=workspace_value)
            | models.Q(workspace__acronym__iexact=workspace_value)
        )

    return queryset.first()


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_workspaces_me_view(request):
    """Return union/federation workspaces attached to the logged-in user."""

    memberships = _get_active_union_workspace_memberships(request.user)

    serializer = UnionWorkspaceMembershipSerializer(
        memberships,
        many=True,
        context={"request": request},
    )

    return Response(
        {
            "count": memberships.count(),
            "results": serializer.data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_switch_workspace_view(request):
    """Validate and return the selected union workspace membership."""

    workspace_value = request.data.get("workspace") or request.data.get(
        "workspace_slug"
    )

    if not workspace_value:
        return Response(
            {"detail": "workspace is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_union_membership_for_request(request.user, workspace_value)

    if membership is None:
        return Response(
            {"detail": "You do not have access to this union workspace."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = UnionWorkspaceMembershipSerializer(
        membership,
        context={"request": request},
    )

    dashboard_access = resolve_dashboard_access(request.user)
    entitlement_id = f"union-workspace-{membership.workspace_id}"
    selected_entitlement_id = (
        entitlement_id
        if any(
            item["id"] == entitlement_id for item in dashboard_access["entitlements"]
        )
        else None
    )

    if selected_entitlement_id is None:
        return Response(
            {"detail": "You do not have active dashboard access to this workspace."},
            status=status.HTTP_403_FORBIDDEN,
        )

    return Response(
        {
            **serializer.data,
            "selected_entitlement_id": selected_entitlement_id,
            "dashboard_access": dashboard_access,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_workspace_dashboard_view(request):
    """Workspace-aware dashboard summary for the Union Admin portal."""

    workspace_value = request.query_params.get("workspace")
    membership = _get_union_membership_for_request(request.user, workspace_value)

    if membership is None:
        return Response(
            {"detail": "No active union workspace access found for this user."},
            status=status.HTTP_403_FORBIDDEN,
        )

    workspace = membership.workspace
    related_union = workspace.related_union

    if related_union:
        leagues = League.objects.filter(union=related_union)
        competitions = Competition.objects.filter(league__union=related_union)
        matches = Match.objects.filter(competition__league__union=related_union)

        member_clubs = (
            Club.objects.filter(
                models.Q(league_memberships__league__union=related_union)
                | models.Q(home_matches__competition__league__union=related_union)
                | models.Q(away_matches__competition__league__union=related_union)
                | models.Q(standings__competition__league__union=related_union)
            )
            .distinct()
            .count()
        )
    else:
        leagues = League.objects.none()
        competitions = Competition.objects.none()
        matches = Match.objects.none()
        member_clubs = 0

    return Response(
        {
            "workspace": UnionWorkspaceMembershipSerializer(
                membership,
                context={"request": request},
            ).data,
            "summary": {
                "leagues": leagues.count(),
                "active_competitions": competitions.filter(is_active=True).count(),
                "member_clubs": member_clubs,
                "national_teams": NationalTeam.objects.filter(
                    workspace=workspace, is_active=True
                ).count(),
                "pending_approvals": UnionRegistrationApplication.objects.filter(
                    workspace=workspace,
                    status__in=[
                        UnionRegistrationApplication.Status.PENDING,
                        UnionRegistrationApplication.Status.UNDER_REVIEW,
                        UnionRegistrationApplication.Status.DOCUMENTS_REQUIRED,
                    ],
                ).count(),
                "referees": (
                    UnionMatchOfficial.objects.filter(union=related_union).count()
                    if related_union
                    else 0
                ),
                "upcoming_matches": matches.filter(
                    status=Match.Status.SCHEDULED
                ).count(),
            },
            "permissions": membership.effective_permissions,
        }
    )


def _get_union_workspace_by_value(workspace_value):
    if not workspace_value:
        return None

    return (
        UnionWorkspace.objects.filter(
            models.Q(slug=workspace_value)
            | models.Q(acronym__iexact=workspace_value)
            | models.Q(name__iexact=workspace_value)
        )
        .select_related("related_union")
        .first()
    )


def _is_super_admin_user(user):
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and (
            getattr(user, "is_superuser", False)
            or getattr(user, "role", None) == User.Role.SUPER_ADMIN
        )
    )


def _get_membership_for_workspace(user, workspace):
    if not user or not getattr(user, "is_authenticated", False) or workspace is None:
        return None

    return (
        UnionWorkspaceMembership.objects.filter(
            user=user,
            workspace=workspace,
            is_active=True,
        )
        .select_related("workspace")
        .first()
    )


def _can_manage_workspace_users(user, workspace):
    if _is_super_admin_user(user):
        return True

    membership = _get_membership_for_workspace(user, workspace)

    if membership is None:
        return False

    return "union.users.manage" in membership.effective_permissions


def _validate_workspace_role(role):
    valid_roles = {choice[0] for choice in UnionWorkspaceMembership.Role.choices}

    if role not in valid_roles:
        return False

    return True


def _workspace_sport_value(workspace):
    return (workspace.sport or "").strip().upper().replace(" ", "_") or "OTHER"


def _competition_format_label(competition):
    name = competition.name.lower()

    if "cup" in name:
        return "Knockout"

    if "7s" in name or "sevens" in name:
        return "Sevens series"

    if "basketball" in name:
        return "Basketball league"

    if "premier" in name:
        return "Premier league"

    return "League"


def _competition_type_label(competition):
    name = competition.name.lower()

    if "cup" in name:
        return "Cup"

    if "7s" in name or "sevens" in name or "series" in name:
        return "Series"

    if "super 8" in name or "playoffs" in name:
        return "Tournament"

    return "League"


def _competition_phase_label(competition):
    today = timezone.localdate()

    if not competition.is_active:
        return "Setup"

    if competition.start_date and competition.start_date > today:
        return "Pre-season"

    if competition.end_date and competition.end_date < today:
        return "Completed"

    return "In season"


def _competition_entry_window_label(competition):
    phase = _competition_phase_label(competition)

    if phase in {"Setup", "Pre-season"}:
        return "Entries open"

    if phase == "In season":
        return "Entries closed"

    return "Closed"


def _competition_fixture_status(competition):
    fixture_count = Match.objects.filter(competition=competition).count()

    if fixture_count == 0:
        return "Needs fixtures"

    if fixture_count < 3:
        return "Partially generated"

    return "Fixtures ready"


def _next_fixture_label(competition):
    match = (
        Match.objects.filter(
            competition=competition,
            match_date__gte=timezone.now(),
        )
        .select_related("home_club", "away_club")
        .order_by("match_date")
        .first()
    )

    if match is None:
        return "No upcoming fixture"

    return f"{match.home_club.name} vs {match.away_club.name}"


def _competition_officials_needed(competition):
    match_count = Match.objects.filter(
        competition=competition,
        match_date__gte=timezone.now(),
    ).count()

    return min(match_count, 3)


def _competition_reports_due(competition):
    return Match.objects.filter(
        competition=competition,
        status=Match.Status.COMPLETED,
    ).count()


def _workspace_competitions(workspace):
    if workspace.related_union:
        return (
            Competition.objects.filter(league__union=workspace.related_union)
            .select_related("league")
            .order_by("-is_active", "name")
        )

    return Competition.objects.none()


def _workspace_matches(workspace):
    if workspace.related_union:
        return (
            Match.objects.filter(competition__league__union=workspace.related_union)
            .select_related("competition", "home_club", "away_club")
            .order_by("match_date")
        )

    return Match.objects.none()


def _workspace_clubs(workspace):
    """
    Return clubs connected to this union through membership,
    fixtures or standings.

    Never fall back to all clubs sharing the workspace sport,
    because community leagues and national federations may use
    the same sport while remaining separate organisations.
    """
    if not workspace.related_union_id:
        return Club.objects.none()

    return (
        Club.objects.filter(
            models.Q(
                league_memberships__league__union=workspace.related_union,
                league_memberships__status__in=[
                    LeagueClubMembership.Status.ACTIVE,
                    LeagueClubMembership.Status.PROMOTED,
                    LeagueClubMembership.Status.INVITED,
                ],
            )
            | models.Q(home_matches__competition__league__union=workspace.related_union)
            | models.Q(away_matches__competition__league__union=workspace.related_union)
            | models.Q(standings__competition__league__union=workspace.related_union)
        )
        .distinct()
        .order_by("name")
    )


def _club_admin_label(club):
    if club.admin:
        return club.admin.get_full_name() or club.admin.email

    return "Workspace Admin"


def _workspace_referees(workspace, competitions):
    return []


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_operations_dashboard_view(request):
    """Workspace-scoped operations data for Union/Federation workspace pages."""

    workspace_value = request.query_params.get("workspace")
    membership = _get_union_membership_for_request(request.user, workspace_value)

    if membership is None:
        return Response(
            {"detail": "No active union workspace access found for this user."},
            status=status.HTTP_403_FORBIDDEN,
        )

    workspace = membership.workspace
    sport_value = _workspace_sport_value(workspace)

    competitions_qs = list(_workspace_competitions(workspace))
    clubs_qs = list(_workspace_clubs(workspace))
    matches_qs = list(_workspace_matches(workspace)[:12])
    current_official = None
    official_assignments = None

    if membership.role == UnionWorkspaceMembership.Role.MATCH_OFFICIAL:
        current_official = (
            UnionMatchOfficial.objects.filter(
                union=workspace.related_union,
                user=request.user,
            )
            .select_related("union", "user")
            .first()
        )

        if current_official is None:
            return Response(
                {
                    "detail": (
                        "No match official profile is linked to this "
                        "workspace account."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        official_assignments = (
            FixtureOfficialAssignment.objects.filter(
                official=current_official,
                match__competition__league__union=workspace.related_union,
            )
            .select_related(
                "match",
                "match__competition",
                "match__home_club",
                "match__away_club",
                "official",
            )
            .order_by("match__match_date")
        )

    competition_rows = []

    for competition in competitions_qs:
        competition_matches = Match.objects.filter(competition=competition)
        participating_clubs = (
            Club.objects.filter(
                models.Q(home_matches__competition=competition)
                | models.Q(away_matches__competition=competition)
                | models.Q(standings__competition=competition)
            )
            .distinct()
            .count()
        )

        if participating_clubs == 0:
            participating_clubs = len(clubs_qs)

        competition_rows.append(
            {
                "id": str(competition.id),
                "name": competition.name,
                "type": _competition_type_label(competition),
                "format": _competition_format_label(competition),
                "season": competition.season,
                "clubs": participating_clubs,
                "matches": competition_matches.count(),
                "status": "Active" if competition.is_active else "Draft",
                "phase": _competition_phase_label(competition),
                "entryWindow": _competition_entry_window_label(competition),
                "registrationStatus": _competition_entry_window_label(competition),
                "fixtureStatus": _competition_fixture_status(competition),
                "nextFixture": _next_fixture_label(competition),
                "officialsNeeded": _competition_officials_needed(competition),
                "reportsDue": _competition_reports_due(competition),
                "nextAction": (
                    "Generate fixtures"
                    if competition_matches.count() == 0
                    else "Assign officials"
                ),
            }
        )

    club_rows = [
        {
            "id": str(club.id),
            "name": club.name,
            "category": (
                club.get_sport_display()
                if hasattr(club, "get_sport_display")
                else sport_value.title()
            ),
            "teams": 0,
            "players": 0,
            "compliance": "Unknown",
            "admin": _club_admin_label(club),
        }
        for index, club in enumerate(clubs_qs[:20])
    ]

    if official_assignments is not None:
        appointment_rows = [
            {
                "id": assignment.id,
                "match": (
                    f"{assignment.match.home_club.name} vs "
                    f"{assignment.match.away_club.name}"
                ),
                "competition": assignment.match.competition.name,
                "date": assignment.match.match_date.strftime("%d %b %Y, %H:%M"),
                "venue": assignment.match.venue or "Venue TBC",
                "role": assignment.get_role_type_display(),
                "status": assignment.get_status_display(),
                "report": (
                    "Due after match"
                    if assignment.match.match_date >= timezone.now()
                    else "Report due"
                ),
            }
            for assignment in official_assignments[:20]
        ]
    else:
        appointment_rows = [
            {
                "match": (f"{match.home_club.name} vs " f"{match.away_club.name}"),
                "competition": match.competition.name,
                "date": match.match_date.strftime("%d %b %Y, %H:%M"),
                "venue": match.venue or "Venue TBC",
                "role": (
                    "Centre Referee"
                    if "BASKETBALL" not in sport_value
                    else "Crew Chief"
                ),
                "status": "Assignment required",
                "report": "Due after match",
            }
            for match in matches_qs[:8]
        ]

    registration_rows = []

    return Response(
        {
            "workspace": {
                "slug": workspace.slug,
                "acronym": workspace.acronym,
                "name": workspace.name,
                "sport": workspace.sport,
            },
            "competitions": (
                []
                if membership.role == UnionWorkspaceMembership.Role.MATCH_OFFICIAL
                else competition_rows
            ),
            "clubs": (
                []
                if membership.role == UnionWorkspaceMembership.Role.MATCH_OFFICIAL
                else club_rows
            ),
            "national_teams": (
                []
                if membership.role == UnionWorkspaceMembership.Role.MATCH_OFFICIAL
                else []
            ),
            "registrations": (
                []
                if membership.role == UnionWorkspaceMembership.Role.MATCH_OFFICIAL
                else registration_rows
            ),
            "referees": (
                []
                if membership.role == UnionWorkspaceMembership.Role.MATCH_OFFICIAL
                else _workspace_referees(
                    workspace,
                    competitions_qs,
                )
            ),
            "current_official": (
                {
                    "id": current_official.id,
                    "name": current_official.full_name,
                    "email": current_official.email,
                    "role": current_official.get_role_type_display(),
                    "grade": current_official.certification_level,
                    "status": current_official.get_status_display(),
                    "competitions": current_official.competitions,
                    "union": current_official.union.name,
                }
                if current_official is not None
                else None
            ),
            "appointments": appointment_rows,
            "player_positions": (
                []
                if membership.role == UnionWorkspaceMembership.Role.MATCH_OFFICIAL
                else []
            ),
        }
    )


def _format_ugx(amount):
    value = Decimal(str(amount or "0")).quantize(Decimal("0.01"))

    return {
        "raw": str(value),
        "display": f"UGX {value:,.0f}",
    }


def _finance_audits_for_workspace(workspace):
    return PaymentAudit.objects.filter(
        models.Q(metadata__workspace_slug=workspace.slug)
        | models.Q(metadata__workspace_acronym=workspace.acronym)
    ).order_by("-created_at")


def _finance_reconciliations_for_workspace(workspace):
    return TransactionReconciliation.objects.filter(
        models.Q(metadata__workspace_slug=workspace.slug)
        | models.Q(metadata__workspace_acronym=workspace.acronym)
    ).order_by("-transaction_date", "-created_at")


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_finance_dashboard_view(request):
    """Workspace-scoped finance dashboard summary for Union/Federation workspaces."""

    workspace_value = request.query_params.get("workspace")
    membership = _get_union_membership_for_request(request.user, workspace_value)

    if membership is None:
        return Response(
            {"detail": "No active union workspace access found for this user."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if (
        not _is_super_admin_user(request.user)
        and "union.finance.view" not in membership.effective_permissions
    ):
        return Response(
            {
                "detail": "You do not have permission to view finance for this workspace."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    workspace = membership.workspace
    audits = list(_finance_audits_for_workspace(workspace)[:200])
    reconciliations = list(_finance_reconciliations_for_workspace(workspace)[:50])

    completed_statuses = {"SETTLED", "SUCCESS", "SUCCESSFUL", "COMPLETED", "PAID"}
    pending_statuses = {"PENDING", "PENDING_REVIEW", "INITIATED", "RECONCILE"}
    failed_statuses = {"FAILED", "REFUNDED", "CHARGEBACK", "DISPUTED", "CANCELLED"}

    gross_receipts = Decimal("0.00")
    net_settled = Decimal("0.00")
    pending_payouts = Decimal("0.00")
    failed_reversed = Decimal("0.00")

    revenue_mix_totals = {}
    monthly_totals = {}

    for audit in audits:
        amount = audit.amount or Decimal("0.00")
        status_value = (audit.status or "").upper()
        event_value = (audit.event_type or "").upper()
        stream = (
            audit.metadata.get("revenue_stream") or audit.get_payment_source_display()
        )

        if status_value not in failed_statuses and event_value not in failed_statuses:
            gross_receipts += amount

        if status_value in completed_statuses or event_value == "COMPLETED":
            net_settled += amount
            revenue_mix_totals[stream] = (
                revenue_mix_totals.get(stream, Decimal("0.00")) + amount
            )

            month_key = audit.created_at.strftime("%b")
            monthly_totals[month_key] = (
                monthly_totals.get(month_key, Decimal("0.00")) + amount
            )

        if status_value in pending_statuses or event_value == "INITIATED":
            pending_payouts += amount

        if status_value in failed_statuses or event_value in failed_statuses:
            failed_reversed += amount

    for item in reconciliations:
        if item.status == TransactionReconciliation.Status.PENDING:
            pending_payouts += item.amount or Decimal("0.00")

    total_mix = sum(revenue_mix_totals.values(), Decimal("0.00"))

    revenue_mix = []
    for label, amount in sorted(revenue_mix_totals.items()):
        percent = 0
        if total_mix:
            percent = round((amount / total_mix) * 100)

        revenue_mix.append(
            {
                "label": label,
                "amount": _format_ugx(amount),
                "percent": percent,
            }
        )

    month_order = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    monthly_trend = [
        {
            "label": month,
            "value": float(monthly_totals.get(month, Decimal("0.00"))),
            "amount": _format_ugx(monthly_totals.get(month, Decimal("0.00"))),
        }
        for month in month_order
        if month in monthly_totals
    ]

    recent_transactions = [
        {
            "reference": audit.reference,
            "source": audit.metadata.get("source_label")
            or audit.get_payment_source_display(),
            "amount": _format_ugx(audit.amount),
            "status": audit.status,
            "date": audit.created_at.strftime("%d %b %Y, %H:%M"),
            "stream": audit.metadata.get("revenue_stream") or audit.payment_source,
        }
        for audit in audits[:8]
    ]

    payout_queue = [
        {
            "beneficiary": item.metadata.get("beneficiary") or item.source_system,
            "category": item.metadata.get("category") or "Reconciliation",
            "amount": _format_ugx(item.amount),
            "status": item.status,
            "reference": item.internal_reference,
        }
        for item in reconciliations[:8]
    ]

    return Response(
        {
            "workspace": {
                "slug": workspace.slug,
                "acronym": workspace.acronym,
                "name": workspace.name,
            },
            "currency": "UGX",
            "kpis": {
                "gross_receipts": _format_ugx(gross_receipts),
                "net_settled": _format_ugx(net_settled),
                "pending_payouts": _format_ugx(pending_payouts),
                "failed_reversed": _format_ugx(failed_reversed),
                "transaction_count": len(audits),
                "payout_count": len(reconciliations),
            },
            "monthly_trend": monthly_trend,
            "revenue_mix": revenue_mix,
            "recent_transactions": recent_transactions,
            "payout_queue": payout_queue,
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_workspace_users_view(request):
    """List workspace users or create/attach a user to a union workspace."""

    workspace_value = (
        request.query_params.get("workspace")
        if request.method == "GET"
        else request.data.get("workspace")
    )

    workspace = _get_union_workspace_by_value(workspace_value)

    if workspace is None:
        return Response(
            {"detail": "A valid workspace slug, acronym or name is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not _can_manage_workspace_users(request.user, workspace):
        return Response(
            {
                "detail": "You do not have permission to manage users for this workspace."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        memberships = (
            UnionWorkspaceMembership.objects.filter(
                workspace=workspace,
                is_active=True,
            )
            .select_related("user", "workspace")
            .order_by("role", "user__email")
        )

        serializer = UnionWorkspaceUserSerializer(
            memberships,
            many=True,
            context={"request": request},
        )

        return Response(
            {
                "count": memberships.count(),
                "workspace": workspace.slug,
                "results": serializer.data,
            }
        )

    email = (request.data.get("email") or "").strip().lower()
    first_name = (request.data.get("first_name") or "").strip()
    last_name = (request.data.get("last_name") or "").strip()
    phone_number = (request.data.get("phone_number") or "").strip() or None
    role = request.data.get("role") or UnionWorkspaceMembership.Role.VIEWER
    password = request.data.get("password")

    if not email:
        return Response(
            {"detail": "email is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not _validate_workspace_role(role):
        return Response(
            {"detail": "Invalid workspace role."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if role == UnionWorkspaceMembership.Role.OWNER and not _is_super_admin_user(
        request.user
    ):
        return Response(
            {"detail": "Only a Super Admin can create or assign a workspace owner."},
            status=status.HTTP_403_FORBIDDEN,
        )

    user = User.objects.filter(email__iexact=email).first()
    created_user = False
    generated_password = None

    if user is None:
        import secrets

        generated_password = password or f"LeagueOS-{secrets.token_urlsafe(8)}A1!"
        create_kwargs = {
            "email": email,
            "password": generated_password,
            "first_name": first_name or "Union",
            "last_name": last_name or "User",
            "role": User.Role.FAN,
            "is_email_verified": True,
        }

        if phone_number:
            create_kwargs["phone_number"] = phone_number

        user = User.objects.create_user(**create_kwargs)
        created_user = True
    else:
        update_fields = []

        if first_name and not user.first_name:
            user.first_name = first_name
            update_fields.append("first_name")

        if last_name and not user.last_name:
            user.last_name = last_name
            update_fields.append("last_name")

        if phone_number and not user.phone_number:
            user.phone_number = phone_number
            update_fields.append("phone_number")

        if update_fields:
            user.save(update_fields=update_fields)

    membership, created_membership = UnionWorkspaceMembership.objects.update_or_create(
        user=user,
        workspace=workspace,
        defaults={
            "role": role,
            "is_active": True,
            "invited_by": request.user,
        },
    )

    linked_official = None

    if (
        role == UnionWorkspaceMembership.Role.MATCH_OFFICIAL
        and workspace.related_union is not None
    ):
        linked_official = UnionMatchOfficial.objects.filter(
            union=workspace.related_union,
            email__iexact=email,
        ).first()

        if linked_official is not None and linked_official.user_id != user.id:
            linked_official.user = user
            linked_official.save(update_fields=["user", "updated_at"])

    serializer = UnionWorkspaceUserSerializer(
        membership,
        context={"request": request},
    )

    response_data = {
        "created_user": created_user,
        "created_membership": created_membership,
        "workspace": workspace.slug,
        "membership": serializer.data,
    }

    if created_user and generated_password:
        response_data["temporary_password"] = generated_password

    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_transfer_owner_view(request):
    """Transfer workspace ownership. This is intentionally Super Admin only."""

    if not _is_super_admin_user(request.user):
        return Response(
            {"detail": "Only a Super Admin can transfer workspace ownership."},
            status=status.HTTP_403_FORBIDDEN,
        )

    workspace_value = request.data.get("workspace")
    new_owner_email = (request.data.get("new_owner_email") or "").strip().lower()
    old_owner_new_role = (
        request.data.get("old_owner_new_role")
        or UnionWorkspaceMembership.Role.UNION_ADMIN
    )

    workspace = _get_union_workspace_by_value(workspace_value)

    if workspace is None:
        return Response(
            {"detail": "A valid workspace slug, acronym or name is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not new_owner_email:
        return Response(
            {"detail": "new_owner_email is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not _validate_workspace_role(old_owner_new_role):
        return Response(
            {"detail": "Invalid old owner role."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if old_owner_new_role == UnionWorkspaceMembership.Role.OWNER:
        return Response(
            {"detail": "old_owner_new_role cannot also be OWNER."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    new_owner = User.objects.filter(email__iexact=new_owner_email).first()

    if new_owner is None:
        return Response(
            {
                "detail": "New owner must already have a user account. Create the user first."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        UnionWorkspaceMembership.objects.filter(
            workspace=workspace,
            role=UnionWorkspaceMembership.Role.OWNER,
            is_active=True,
        ).exclude(user=new_owner).update(role=old_owner_new_role)

        new_owner_membership, _ = UnionWorkspaceMembership.objects.update_or_create(
            user=new_owner,
            workspace=workspace,
            defaults={
                "role": UnionWorkspaceMembership.Role.OWNER,
                "is_active": True,
                "invited_by": request.user,
            },
        )

    serializer = UnionWorkspaceUserSerializer(
        new_owner_membership,
        context={"request": request},
    )

    return Response(
        {
            "detail": "Workspace ownership transferred successfully.",
            "workspace": workspace.slug,
            "new_owner": serializer.data,
        }
    )
