from decimal import Decimal
from django.db import models, transaction
from django.db.models.expressions import F
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.models import Club, User
from accounts.rbac import get_user_permissions
from accounts.permissions import (
    IsAuthenticatedAudit,
    IsClubAdmin,
    IsFan,
    IsLeagueAdmin,
    IsReferee,
    IsSponsor,
    IsSuperAdmin,
    IsTicketingOfficer,
    IsUnionAdmin,
)
from accounts.routing import (
    get_backend_dashboard_route,
    get_dashboard_route,
    get_dashboard_routes,
)
from accounts.serializers import UserSerializer

from .models import (
    ClubAdminScope,
    Competition,
    League,
    LeagueClubMembership,
    FixtureOfficialAssignment,
    Match,
    Standing,
    UnionMatchOfficial,
    Union,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
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
    User.Role.SUPER_ADMIN: {
        "title": "Super Admin Dashboard",
        "description": "Monitor the full League OS platform, users, roles, tenants, and audit activity.",
        "summary_cards": [
            {"label": "Users", "value": 0},
            {"label": "Organizations", "value": 0},
            {"label": "Roles", "value": 0},
            {"label": "Audit Events", "value": 0},
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
    },
    User.Role.REFEREE: {
        "title": "Referee Dashboard",
        "description": "View match assignments, submit reports, and manage match official duties.",
        "summary_cards": [
            {"label": "Assignments", "value": 0},
            {"label": "Upcoming Matches", "value": 0},
            {"label": "Reports Due", "value": 0},
            {"label": "Completed Matches", "value": 0},
        ],
        "modules": [
            "Assignments",
            "Match Reports",
            "Availability",
            "Disciplinary Notes",
        ],
        "quick_actions": [
            "View assignment",
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


def user_has_sponsor_access(user):
    if user.role == User.Role.SPONSOR:
        return True

    return user.sponsor_memberships.filter(is_active=True).exists()


def build_available_dashboards(user):
    dashboards = [
        {
            "label": user.get_role_display(),
            "frontend_route": get_dashboard_route(user),
            "backend_route": get_backend_dashboard_route(user),
        }
    ]

    sponsor_dashboard = {
        "label": "Sponsor Dashboard",
        "frontend_route": "/dashboard/sponsor",
        "backend_route": "/api/dashboards/sponsor/",
    }

    if user_has_sponsor_access(user) and sponsor_dashboard not in dashboards:
        dashboards.append(sponsor_dashboard)

    return dashboards


def build_dashboard_response(request, role, message=None):
    """Build a consistent dashboard response for the authenticated user's role."""

    user = request.user
    content = DASHBOARD_CONTENT.get(role)

    if content is None:
        return Response(
            {"detail": "No dashboard is configured for this user role."},
            status=status.HTTP_404_NOT_FOUND,
        )

    frontend_dashboard_route = get_dashboard_route(user)
    backend_dashboard_route = get_backend_dashboard_route(user)

    if role == User.Role.SPONSOR:
        frontend_dashboard_route = "/dashboard/sponsor"
        backend_dashboard_route = "/api/dashboards/sponsor/"

    success_message = message or f"{content['title']} loaded successfully."

    return Response(
        {
            "message": success_message,
            "role": user.role,
            "role_display": user.get_role_display(),
            "dashboard_role": role,
            "frontend_dashboard_route": frontend_dashboard_route,
            "backend_dashboard_route": backend_dashboard_route,
            "available_dashboards": get_dashboard_routes(user),
            "dashboard": content,
            "user": UserSerializer(user, context={"request": request}).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def my_dashboard_view(request):
    """Return the dashboard route and summary for the authenticated user's role"""

    return build_dashboard_response(
        request,
        request.user.role,
        message="Dashboard resolved successfully.",
    )


@api_view(["GET"])
@permission_classes([IsFan])
def fan_dashboard_view(request):
    return build_dashboard_response(request, User.Role.FAN)


@api_view(["GET"])
@permission_classes([IsClubAdmin])
def club_admin_dashboard_view(request):
    user = request.user
    # Find the user's active club scope
    scope = (
        ClubAdminScope.objects.filter(user=user, is_active=True)
        .select_related("club")
        .first()
    )

    if not scope:
        # Fallback for users with the direct role but no scope object
        return build_dashboard_response(request, User.Role.CLUB_ADMIN)

    # Get all permissions (base role + club scope)
    permissions = get_user_permissions(user)

    # Dynamically build dashboard content based on permissions
    dashboard_content = {
        "title": f"{scope.club.name} Admin",
        "description": f"Manage operations for {scope.club.name}.",
        "summary_cards": [],
        "modules": [],
        "quick_actions": [],
    }

    if "club.profile.view" in permissions:
        dashboard_content["modules"].append("Club Profile")
        dashboard_content["quick_actions"].append("Update club profile")

    if "club.squad.manage" in permissions:
        dashboard_content["modules"].append("Squad Management")
        dashboard_content["quick_actions"].append("Manage player roster")

    if "club.members.manage" in permissions:
        dashboard_content["modules"].append("Memberships")
        dashboard_content["quick_actions"].append("Review memberships")

    if "club.ticketing.manage" in permissions:
        dashboard_content["modules"].append("Ticketing")
        dashboard_content["quick_actions"].append("View ticket sales")

    # Override the static content with our dynamic version
    DASHBOARD_CONTENT[User.Role.CLUB_ADMIN] = dashboard_content

    return build_dashboard_response(request, User.Role.CLUB_ADMIN)


@api_view(["GET"])
@permission_classes([IsLeagueAdmin])
def league_admin_dashboard_view(request):
    return build_dashboard_response(request, User.Role.LEAGUE_ADMIN)


@api_view(["GET"])
@permission_classes([IsUnionAdmin])
def union_admin_dashboard_view(request):
    return build_dashboard_response(request, User.Role.UNION_ADMIN)


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def super_admin_dashboard_view(request):
    return build_dashboard_response(request, User.Role.SUPER_ADMIN)


@api_view(["GET"])
@permission_classes([IsReferee])
def referee_dashboard_view(request):
    return build_dashboard_response(request, User.Role.REFEREE)


@api_view(["GET"])
@permission_classes([IsTicketingOfficer])
def ticketing_officer_dashboard_view(request):
    return build_dashboard_response(request, User.Role.TICKETING_OFFICER)


@api_view(["GET"])
@permission_classes([IsSponsor])
def sponsor_dashboard_view(request):
    return build_dashboard_response(request, User.Role.SPONSOR)


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

    return Response(serializer.data)


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
                models.Q(home_matches__competition__league__union=related_union)
                | models.Q(away_matches__competition__league__union=related_union)
                | models.Q(standings__competition__league__union=related_union)
            )
            .distinct()
            .count()
        )

        if member_clubs == 0 and workspace.sport:
            sport_value = workspace.sport.strip().upper().replace(" ", "_")
            member_clubs = Club.objects.filter(sport=sport_value).count()
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
                "pending_approvals": 0,
                "referees": 0,
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


NATIONAL_TEAM_ROWS = {
    "URU": [
        {
            "team": "Uganda Rugby Cranes",
            "category": "Senior Men",
            "players": 32,
            "staff": 8,
            "status": "Active",
        },
        {
            "team": "Lady Rugby Cranes",
            "category": "Senior Women",
            "players": 30,
            "staff": 7,
            "status": "Active",
        },
        {
            "team": "Uganda Rugby 7s",
            "category": "Sevens",
            "players": 18,
            "staff": 5,
            "status": "Camp",
        },
        {
            "team": "Uganda U20 Rugby",
            "category": "Age Grade",
            "players": 36,
            "staff": 6,
            "status": "Selection",
        },
    ],
    "FUFA": [
        {
            "team": "Uganda Cranes",
            "category": "Senior Men",
            "players": 28,
            "staff": 10,
            "status": "Active",
        },
        {
            "team": "Crested Cranes",
            "category": "Senior Women",
            "players": 26,
            "staff": 8,
            "status": "Active",
        },
        {
            "team": "Uganda U20 Football",
            "category": "Age Grade",
            "players": 30,
            "staff": 7,
            "status": "Camp",
        },
        {
            "team": "Uganda U17 Football",
            "category": "Age Grade",
            "players": 30,
            "staff": 6,
            "status": "Selection",
        },
    ],
    "FUBA": [
        {
            "team": "Uganda Silverbacks",
            "category": "Senior Men",
            "players": 18,
            "staff": 7,
            "status": "Active",
        },
        {
            "team": "Uganda Gazelles",
            "category": "Senior Women",
            "players": 18,
            "staff": 7,
            "status": "Active",
        },
        {
            "team": "Uganda U18 Basketball",
            "category": "Age Grade",
            "players": 20,
            "staff": 5,
            "status": "Camp",
        },
        {
            "team": "Uganda 3x3 Basketball",
            "category": "3x3",
            "players": 12,
            "staff": 4,
            "status": "Selection",
        },
    ],
    "BUDO": [
        {
            "team": "Budo League Select",
            "category": "Community Select",
            "players": 24,
            "staff": 5,
            "status": "Active",
        },
        {
            "team": "Budo Veterans",
            "category": "Veterans",
            "players": 22,
            "staff": 4,
            "status": "Active",
        },
    ],
    "SMACK": [
        {
            "team": "SMACK League Select",
            "category": "Community Select",
            "players": 24,
            "staff": 5,
            "status": "Active",
        },
        {
            "team": "SMACK Veterans",
            "category": "Veterans",
            "players": 22,
            "staff": 4,
            "status": "Active",
        },
    ],
}


PLAYER_POSITIONS_BY_SPORT = {
    "RUGBY": [
        {
            "group": "Forwards",
            "positions": [
                "Loosehead Prop",
                "Hooker",
                "Tighthead Prop",
                "Lock",
                "Flanker",
                "Number Eight",
            ],
        },
        {
            "group": "Backs",
            "positions": [
                "Scrum-half",
                "Fly-half",
                "Centre",
                "Wing",
                "Fullback",
            ],
        },
    ],
    "FOOTBALL": [
        {
            "group": "Goalkeeping",
            "positions": ["Goalkeeper"],
        },
        {
            "group": "Defence",
            "positions": ["Right Back", "Centre Back", "Left Back"],
        },
        {
            "group": "Midfield",
            "positions": [
                "Defensive Midfielder",
                "Central Midfielder",
                "Attacking Midfielder",
            ],
        },
        {
            "group": "Attack",
            "positions": ["Winger", "Striker"],
        },
    ],
    "BASKETBALL": [
        {
            "group": "Backcourt",
            "positions": ["Point Guard", "Shooting Guard"],
        },
        {
            "group": "Frontcourt",
            "positions": ["Small Forward", "Power Forward", "Center"],
        },
    ],
}


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
    clubs = Club.objects.none()

    if workspace.related_union:
        league_member_clubs = Club.objects.filter(
            league_memberships__league__union=workspace.related_union,
            league_memberships__status__in=[
                LeagueClubMembership.Status.ACTIVE,
                LeagueClubMembership.Status.PROMOTED,
            ],
        )

        match_clubs = Club.objects.filter(
            models.Q(home_matches__competition__league__union=workspace.related_union)
            | models.Q(away_matches__competition__league__union=workspace.related_union)
            | models.Q(standings__competition__league__union=workspace.related_union)
        )

        clubs = (league_member_clubs | match_clubs).distinct().order_by("name")

    if not clubs.exists() and workspace.sport:
        clubs = Club.objects.filter(sport=_workspace_sport_value(workspace)).order_by(
            "name"
        )

    return clubs


def _club_admin_label(club):
    if club.admin:
        return club.admin.get_full_name() or club.admin.email

    return "Workspace Admin"


def _workspace_referees(workspace, competitions):
    sport = (workspace.sport or "").lower()

    if "football" in sport:
        role_1 = "Centre Referee"
        role_2 = "Assistant Referee"
        grade = "FUFA Grade 1"
    elif "basketball" in sport:
        role_1 = "Crew Chief"
        role_2 = "Table Official"
        grade = "FIBA Level"
    else:
        role_1 = "Centre Referee"
        role_2 = "Assistant Referee"
        grade = "Level 2"

    competition_names = (
        ", ".join([competition.name for competition in competitions[:3]])
        or "Competition pool"
    )

    return [
        {
            "name": f"{workspace.acronym} Lead Official",
            "role": role_1,
            "grade": grade,
            "status": "Available",
            "competitions": competition_names,
            "nextMatch": "Assigned from fixture list",
        },
        {
            "name": f"{workspace.acronym} Assistant Official",
            "role": role_2,
            "grade": grade,
            "status": "Available",
            "competitions": competition_names,
            "nextMatch": "Pending assignment",
        },
        {
            "name": f"{workspace.acronym} Match Commissioner",
            "role": "Match Commissioner",
            "grade": "Assessor",
            "status": "Review",
            "competitions": competition_names,
            "nextMatch": "Pending assignment",
        },
    ]


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
            "teams": 2 + (index % 3),
            "players": 24 + ((index + 1) * 5),
            "compliance": "Ready" if index % 3 != 2 else "Review",
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

    registration_rows = [
        {
            "applicant": f"{club.short_name or club.name} Player {index + 1}",
            "club": club.name,
            "type": "New player" if index % 2 == 0 else "Transfer",
            "submitted": "Today" if index == 0 else f"{index + 1} days ago",
            "status": "Needs review" if index % 2 == 0 else "Documents missing",
            "reviewer": "Registrar",
        }
        for index, club in enumerate(clubs_qs[:5])
    ]

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
                else NATIONAL_TEAM_ROWS.get(
                    workspace.acronym.upper(),
                    [],
                )
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
                else PLAYER_POSITIONS_BY_SPORT.get(
                    sport_value,
                    [],
                )
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
