from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import Club, User
from accounts.permissions import (
    IsClubAdmin,
    IsLeagueAdmin,
    IsTicketingOfficer,
)
from ticketing.models import (
    Ticket,
    TicketType,
    TicketValidationLog,
)

from .models import (
    Competition,
    FixtureOfficialAssignment,
    LeagueAdminScope,
    Match,
    UnionWorkspaceMembership,
)

UPCOMING_STATUSES = (
    Match.Status.SCHEDULED,
    Match.Status.LIVE,
    Match.Status.POSTPONED,
)


def _media_url(request, field):
    if not field:
        return None

    try:
        return request.build_absolute_uri(field.url)
    except (ValueError, AttributeError):
        return None


def _serialize_match(match):
    return {
        "id": match.id,
        "label": f"{match.home_club.name} vs {match.away_club.name}",
        "competition_id": match.competition_id,
        "competition": match.competition.name,
        "league_id": match.competition.league_id,
        "league": match.competition.league.name,
        "home_club_id": match.home_club_id,
        "home_club": match.home_club.name,
        "away_club_id": match.away_club_id,
        "away_club": match.away_club.name,
        "match_date": match.match_date,
        "venue": match.venue,
        "round": match.round,
        "status": match.status,
        "home_score": match.home_score,
        "away_score": match.away_score,
    }


def _serialize_ticket_event(match):
    return {
        **_serialize_match(match),
        "ticket_types": getattr(match, "ticket_types_count", 0),
        "tickets_sold": getattr(match, "tickets_sold_count", 0),
        "checked_in": getattr(match, "checked_in_count", 0),
    }


def _matches_for_league_scopes(scopes):
    full_league_ids = {
        scope.league_id for scope in scopes if scope.competition_id is None
    }
    competition_ids = {
        scope.competition_id for scope in scopes if scope.competition_id is not None
    }

    if not full_league_ids and not competition_ids:
        return Match.objects.none()

    return (
        Match.objects.filter(
            Q(competition__league_id__in=full_league_ids)
            | Q(competition_id__in=competition_ids)
        )
        .select_related(
            "competition",
            "competition__league",
            "home_club",
            "away_club",
        )
        .distinct()
    )


def _competitions_for_league_scopes(scopes):
    full_league_ids = {
        scope.league_id for scope in scopes if scope.competition_id is None
    }
    competition_ids = {
        scope.competition_id for scope in scopes if scope.competition_id is not None
    }

    if not full_league_ids and not competition_ids:
        return Competition.objects.none()

    return (
        Competition.objects.filter(
            Q(league_id__in=full_league_ids) | Q(id__in=competition_ids)
        )
        .select_related("league")
        .distinct()
    )


def _club_for_user(user):
    if user.club_id:
        return Club.objects.filter(id=user.club_id).first()

    return Club.objects.filter(admin=user).first()


def _club_matches(club):
    if club is None:
        return Match.objects.none()

    return (
        Match.objects.filter(Q(home_club=club) | Q(away_club=club))
        .select_related(
            "competition",
            "competition__league",
            "home_club",
            "away_club",
        )
        .distinct()
    )


def _ticketing_scopes(user):
    scopes = []

    club = _club_for_user(user)

    if club is not None:
        scopes.append(
            {
                "key": f"club:{club.id}",
                "scope_type": "CLUB",
                "id": club.id,
                "name": club.name,
                "short_name": club.short_name or club.name,
                "sport": club.get_sport_display(),
                "club": club,
                "workspace": None,
            }
        )

    memberships = (
        UnionWorkspaceMembership.objects.filter(
            user=user,
            is_active=True,
            workspace__status="ACTIVE",
        )
        .select_related(
            "workspace",
            "workspace__related_union",
        )
        .order_by("workspace__name")
    )

    for membership in memberships:
        permissions = set(membership.effective_permissions)

        if not {
            "union.ticketing.manage",
            "union.ticketing.scan",
        }.intersection(permissions):
            continue

        workspace = membership.workspace

        scopes.append(
            {
                "key": f"union:{workspace.id}",
                "scope_type": "UNION",
                "id": workspace.id,
                "name": workspace.name,
                "short_name": workspace.acronym,
                "sport": workspace.sport,
                "club": None,
                "workspace": workspace,
            }
        )

    return scopes


def _matches_for_ticketing_scope(scope):
    if scope["scope_type"] == "CLUB":
        return _club_matches(scope["club"])

    workspace = scope["workspace"]

    if workspace is None or workspace.related_union_id is None:
        return Match.objects.none()

    return (
        Match.objects.filter(competition__league__union_id=workspace.related_union_id)
        .select_related(
            "competition",
            "competition__league",
            "home_club",
            "away_club",
        )
        .distinct()
    )


@api_view(["GET"])
@permission_classes([IsLeagueAdmin])
def league_admin_workspace_view(request):
    scopes = list(
        LeagueAdminScope.objects.filter(user=request.user, is_active=True)
        .select_related(
            "league",
            "league__union",
            "competition",
        )
        .order_by("league__name", "competition__name")
    )

    matches = _matches_for_league_scopes(scopes)
    competitions = _competitions_for_league_scopes(scopes)
    now = timezone.now()

    upcoming = matches.filter(
        status__in=UPCOMING_STATUSES,
        match_date__gte=now,
    ).order_by("match_date")[:12]

    recent_results = matches.filter(
        status=Match.Status.COMPLETED,
    ).order_by(
        "-match_date"
    )[:8]

    scope_data = [
        {
            "id": scope.id,
            "role": scope.role,
            "role_display": scope.get_role_display(),
            "can_manage_appointments": (scope.can_manage_appointments),
            "league": {
                "id": scope.league_id,
                "name": scope.league.name,
                "slug": scope.league.slug,
                "union": scope.league.union.name,
            },
            "competition": (
                {
                    "id": scope.competition_id,
                    "name": scope.competition.name,
                    "slug": scope.competition.slug,
                    "season": scope.competition.season,
                }
                if scope.competition_id
                else None
            ),
        }
        for scope in scopes
    ]

    return Response(
        {
            "scope_type": "LEAGUE",
            "scopes": scope_data,
            "summary": {
                "leagues": len({scope.league_id for scope in scopes}),
                "competitions": competitions.count(),
                "upcoming_fixtures": matches.filter(
                    status__in=UPCOMING_STATUSES,
                    match_date__gte=now,
                ).count(),
                "completed_matches": matches.filter(
                    status=Match.Status.COMPLETED,
                ).count(),
                "official_appointments": (
                    FixtureOfficialAssignment.objects.filter(match__in=matches).count()
                ),
            },
            "upcoming_fixtures": [_serialize_match(match) for match in upcoming],
            "recent_results": [_serialize_match(match) for match in recent_results],
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsClubAdmin])
def club_admin_workspace_view(request):
    club = _club_for_user(request.user)

    if club is None:
        return Response(
            {"detail": ("This club administrator is not attached " "to a club.")},
            status=status.HTTP_404_NOT_FOUND,
        )

    matches = _club_matches(club)
    now = timezone.now()

    tickets = Ticket.objects.filter(match__in=matches)
    ticket_types = TicketType.objects.filter(match__in=matches)

    upcoming = matches.filter(
        status__in=UPCOMING_STATUSES,
        match_date__gte=now,
    ).order_by("match_date")[:12]

    recent_results = matches.filter(
        status=Match.Status.COMPLETED,
    ).order_by(
        "-match_date"
    )[:8]

    ticket_events = (
        matches.filter(match_date__gte=now)
        .annotate(
            ticket_types_count=Count(
                "ticket_types",
                distinct=True,
            ),
            tickets_sold_count=Count(
                "tickets",
                distinct=True,
            ),
            checked_in_count=Count(
                "tickets",
                filter=Q(tickets__status=Ticket.Status.USED),
                distinct=True,
            ),
        )
        .filter(ticket_types_count__gt=0)
        .order_by("match_date")[:10]
    )

    memberships = club.league_memberships.select_related("league", "season").order_by(
        "league__name", "-created_at"
    )

    staff = club.members.filter(
        role__in=[
            User.Role.CLUB_ADMIN,
            User.Role.TICKETING_OFFICER,
        ],
        is_active=True,
    ).order_by("role", "email")[:20]

    return Response(
        {
            "scope_type": "CLUB",
            "club": {
                "id": club.id,
                "name": club.name,
                "short_name": club.short_name,
                "slug": club.slug,
                "sport": club.sport,
                "sport_display": club.get_sport_display(),
                "logo_url": _media_url(request, club.logo),
                "primary_color": club.primary_color,
                "secondary_color": club.secondary_color,
            },
            "summary": {
                "competitions": (matches.values("competition_id").distinct().count()),
                "upcoming_fixtures": matches.filter(
                    status__in=UPCOMING_STATUSES,
                    match_date__gte=now,
                ).count(),
                "completed_matches": matches.filter(
                    status=Match.Status.COMPLETED,
                ).count(),
                "club_users": club.members.filter(
                    is_active=True,
                ).count(),
                "ticket_types": ticket_types.count(),
                "tickets_sold": tickets.count(),
                "checked_in": tickets.filter(
                    status=Ticket.Status.USED,
                ).count(),
            },
            "league_memberships": [
                {
                    "id": membership.id,
                    "league": membership.league.name,
                    "league_slug": membership.league.slug,
                    "season": (
                        membership.season.name if membership.season_id else None
                    ),
                    "status": membership.status,
                    "status_display": (membership.get_status_display()),
                }
                for membership in memberships
            ],
            "upcoming_fixtures": [_serialize_match(match) for match in upcoming],
            "recent_results": [_serialize_match(match) for match in recent_results],
            "ticket_events": [
                _serialize_ticket_event(match) for match in ticket_events
            ],
            "staff": [
                {
                    "id": user.id,
                    "name": user.full_name or user.email,
                    "email": user.email,
                    "role": user.role,
                    "role_display": user.get_role_display(),
                }
                for user in staff
            ],
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsTicketingOfficer])
def ticketing_officer_workspace_view(request):
    scopes = _ticketing_scopes(request.user)

    if not scopes:
        return Response(
            {
                "detail": (
                    "No active union or club ticketing scope "
                    "is assigned to this account."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    requested_scope = request.query_params.get("scope")
    selected = None

    if requested_scope:
        selected = next(
            (scope for scope in scopes if scope["key"] == requested_scope),
            None,
        )

        if selected is None:
            return Response(
                {"detail": "The requested ticketing scope is invalid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    if selected is None:
        selected = scopes[0]

    matches = _matches_for_ticketing_scope(selected)
    now = timezone.now()

    tickets = Ticket.objects.filter(match__in=matches)

    events = (
        matches.filter(
            status__in=UPCOMING_STATUSES,
            match_date__gte=now,
        )
        .annotate(
            ticket_types_count=Count(
                "ticket_types",
                distinct=True,
            ),
            tickets_sold_count=Count(
                "tickets",
                distinct=True,
            ),
            checked_in_count=Count(
                "tickets",
                filter=Q(tickets__status=Ticket.Status.USED),
                distinct=True,
            ),
        )
        .filter(ticket_types_count__gt=0)
        .order_by("match_date")[:15]
    )

    logs = (
        TicketValidationLog.objects.filter(match__in=matches)
        .select_related(
            "match",
            "match__home_club",
            "match__away_club",
            "scanned_by",
        )
        .order_by("-created_at")[:25]
    )

    return Response(
        {
            "available_scopes": [
                {
                    "key": scope["key"],
                    "scope_type": scope["scope_type"],
                    "id": scope["id"],
                    "name": scope["name"],
                    "short_name": scope["short_name"],
                    "sport": scope["sport"],
                }
                for scope in scopes
            ],
            "selected_scope": {
                "key": selected["key"],
                "scope_type": selected["scope_type"],
                "id": selected["id"],
                "name": selected["name"],
                "short_name": selected["short_name"],
                "sport": selected["sport"],
            },
            "summary": {
                "active_events": events.count(),
                "tickets_sold": tickets.count(),
                "checked_in": tickets.filter(
                    status=Ticket.Status.USED,
                ).count(),
                "pending_issues": (
                    TicketValidationLog.objects.filter(match__in=matches)
                    .exclude(result=TicketValidationLog.Result.VALID)
                    .count()
                ),
            },
            "events": [_serialize_ticket_event(match) for match in events],
            "recent_logs": [
                {
                    "id": log.id,
                    "match_id": log.match_id,
                    "match": (str(log.match) if log.match_id else "Unknown match"),
                    "scanned_by": (
                        log.scanned_by.full_name or log.scanned_by.email
                        if log.scanned_by_id
                        else "System"
                    ),
                    "result": log.result,
                    "result_display": log.get_result_display(),
                    "message": log.message,
                    "created_at": log.created_at,
                }
                for log in logs
            ],
        },
        status=status.HTTP_200_OK,
    )
