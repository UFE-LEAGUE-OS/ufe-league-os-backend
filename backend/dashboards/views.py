from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.models import Club, User
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

from .models import Competition, League, Match, Standing, Union
from .serializers import (
    ClubListSerializer,
    CompetitionSerializer,
    LeagueSerializer,
    MatchDetailSerializer,
    MatchListSerializer,
    StandingSerializer,
    UnionSerializer,
)
from .services import recalculate_standings

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
    serializer = MatchListSerializer(queryset, many=True)
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
    limit = request.query_params.get("limit", 50)

    queryset = Match.objects.filter(status=Match.Status.COMPLETED).select_related(
        "competition", "home_club", "away_club"
    )

    if competition_id:
        queryset = queryset.filter(competition_id=competition_id)
    if club_id:
        queryset = queryset.filter(home_club_id=club_id) | queryset.filter(
            away_club_id=club_id
        )

    queryset = queryset.order_by("-match_date")[: int(limit)]
    serializer = MatchListSerializer(queryset, many=True)
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
    serializer = ClubListSerializer(queryset, many=True)
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

    serializer = MatchDetailSerializer(match)
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
