from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.routing import get_backend_dashboard_route, get_dashboard_route
from accounts.serializers import UserSerializer

from .permissions import (
    IsClubAdmin,
    IsFan,
    IsLeagueAdmin,
    IsReferee,
    IsSponsor,
    IsSuperAdmin,
    IsTicketingOfficer,
    IsUnionAdmin,
)

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


def build_dashboard_response(request, role, message=None):
    """Build a consistent dashboard response for the authenticated user's role."""

    user = request.user
    content = DASHBOARD_CONTENT.get(role)

    if content is None:
        return Response(
            {"detail": "No dashboard is configured for this user role."},
            status=status.HTTP_404_NOT_FOUND,
        )

    success_message = message or f"{content['title']} loaded successfully."

    return Response(
        {
            "message": success_message,
            "role": user.role,
            "role_display": user.get_role_display(),
            "frontend_dashboard_route": get_dashboard_route(user),
            "backend_dashboard_route": get_backend_dashboard_route(user),
            "dashboard": content,
            "user": UserSerializer(user, context={"request": request}).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_dashboard_view(request):
    """Return the dashboard route and summary for the authenticated user's role"""

    return build_dashboard_response(
        request, 
        request.user.role, 
        message="Dashboard resolved successfully."
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
