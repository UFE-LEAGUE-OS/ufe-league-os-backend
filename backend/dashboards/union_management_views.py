from datetime import datetime, timedelta

from django.db import models, transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import Club
from accounts.permissions import IsAuthenticatedAudit
from .management_serializers import (
    CompetitionManagementSerializer,
    LeagueClubMembershipSerializer,
    MatchListSerializer,
    SeasonManagementSerializer,
)
from .models import Competition, League, LeagueClubMembership, Match, Season
from .views import (
    _get_membership_for_workspace,
    _get_union_membership_for_request,
    _is_super_admin_user,
)


def _workspace_error(message, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"detail": message}, status=status_code)


def _resolve_membership(request):
    workspace_value = (
        request.query_params.get("workspace")
        if request.method == "GET"
        else request.data.get("workspace")
    )

    membership = _get_union_membership_for_request(request.user, workspace_value)

    if membership is None:
        return None, _workspace_error(
            "No active union workspace access found for this user.",
            status.HTTP_403_FORBIDDEN,
        )

    if membership.workspace.related_union is None:
        return None, _workspace_error(
            "This workspace is not linked to a union/federation record.",
            status.HTTP_400_BAD_REQUEST,
        )

    return membership, None


def _has_workspace_permission(user, workspace, permission):
    if _is_super_admin_user(user):
        return True

    membership = _get_membership_for_workspace(user, workspace)

    if membership is None:
        return False

    return permission in membership.effective_permissions


def _require_permission(user, workspace, permission):
    if not _has_workspace_permission(user, workspace, permission):
        return _workspace_error(
            "You do not have permission to perform this workspace action.",
            status.HTTP_403_FORBIDDEN,
        )

    return None


def _workspace_leagues(workspace):
    return League.objects.filter(union=workspace.related_union).order_by("name")


def _get_workspace_league(workspace, value):
    if not value:
        return None

    qs = _workspace_leagues(workspace)

    if str(value).isdigit():
        return qs.filter(id=value).first()

    return qs.filter(models.Q(slug=value) | models.Q(name__iexact=value)).first()


def _get_workspace_competition(workspace, value):
    if not value:
        return None

    qs = Competition.objects.filter(league__union=workspace.related_union)

    if str(value).isdigit():
        return qs.filter(id=value).first()

    return qs.filter(slug=value).first()


def _get_workspace_club(workspace, value):
    if not value:
        return None

    qs = Club.objects.all()

    if str(value).isdigit():
        return qs.filter(id=value).first()

    return qs.filter(models.Q(slug=value) | models.Q(name__iexact=value)).first()


def _get_workspace_season(workspace, value):
    if not value:
        return None

    qs = Season.objects.filter(league__union=workspace.related_union)

    if str(value).isdigit():
        return qs.filter(id=value).first()

    return qs.filter(models.Q(slug=value) | models.Q(name__iexact=value)).first()


def _unique_slug(model, base, queryset):
    base_slug = slugify(base)[:80] or "item"
    slug = base_slug
    counter = 2

    while queryset.filter(slug=slug).exists():
        suffix = f"-{counter}"
        slug = f"{base_slug[:80 - len(suffix)]}{suffix}"
        counter += 1

    return slug


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_seasons_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace

    if request.method == "GET":
        seasons = Season.objects.filter(
            league__union=workspace.related_union
        ).select_related("league")
        league_value = request.query_params.get("league")
        if league_value:
            league = _get_workspace_league(workspace, league_value)
            if league is None:
                return _workspace_error("League not found.", status.HTTP_404_NOT_FOUND)
            seasons = seasons.filter(league=league)
        return Response(
            {
                "count": seasons.count(),
                "results": SeasonManagementSerializer(seasons, many=True).data,
            }
        )

    permission_error = _require_permission(
        request.user, workspace, "union.competitions.manage"
    )
    if permission_error:
        return permission_error

    league = _get_workspace_league(workspace, request.data.get("league"))
    if league is None:
        return _workspace_error("A valid league is required.")

    name = (request.data.get("name") or "").strip()
    if not name:
        return _workspace_error("Season name is required.")

    season = Season.objects.create(
        league=league,
        name=name,
        slug=_unique_slug(Season, name, Season.objects.filter(league=league)),
        start_date=parse_date(str(request.data.get("start_date") or "")),
        end_date=parse_date(str(request.data.get("end_date") or "")),
        is_active=bool(request.data.get("is_active", True)),
    )
    return Response(
        SeasonManagementSerializer(season).data, status=status.HTTP_201_CREATED
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_competitions_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace

    if request.method == "GET":
        competitions = (
            Competition.objects.filter(league__union=workspace.related_union)
            .select_related("league", "season_record")
            .annotate(
                matches_count=models.Count("matches", distinct=True),
                clubs_count=models.Count(
                    "league__club_memberships__club", distinct=True
                ),
            )
            .order_by("-is_active", "name")
        )
        return Response(
            {
                "count": competitions.count(),
                "results": CompetitionManagementSerializer(
                    competitions, many=True
                ).data,
            }
        )

    permission_error = _require_permission(
        request.user, workspace, "union.competitions.manage"
    )
    if permission_error:
        return permission_error

    league = _get_workspace_league(workspace, request.data.get("league"))
    if league is None:
        return _workspace_error("A valid league is required.")

    name = (request.data.get("name") or "").strip()
    if not name:
        return _workspace_error("Competition name is required.")

    season = _get_workspace_season(
        workspace, request.data.get("season") or request.data.get("season_id")
    )
    season_label = (
        request.data.get("season_name") or request.data.get("season_label") or ""
    ).strip()
    if season:
        season_label = season.name
    if not season_label:
        season_label = timezone.localdate().strftime("%Y")

    competition = Competition.objects.create(
        league=league,
        name=name,
        slug=_unique_slug(Competition, name, Competition.objects.filter(league=league)),
        season=season_label,
        season_record=season,
        start_date=parse_date(str(request.data.get("start_date") or "")),
        end_date=parse_date(str(request.data.get("end_date") or "")),
        is_active=bool(request.data.get("is_active", True)),
    )

    return Response(
        CompetitionManagementSerializer(competition).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_league_clubs_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace

    if request.method == "GET":
        memberships = (
            LeagueClubMembership.objects.filter(league__union=workspace.related_union)
            .select_related(
                "league",
                "club",
                "season",
                "promoted_from_league",
                "relegated_to_league",
            )
            .order_by("league__name", "club__name")
        )
        league_value = request.query_params.get("league")
        season_value = request.query_params.get("season")
        if league_value:
            league = _get_workspace_league(workspace, league_value)
            if league is None:
                return _workspace_error("League not found.", status.HTTP_404_NOT_FOUND)
            memberships = memberships.filter(league=league)
        if season_value:
            season = _get_workspace_season(workspace, season_value)
            if season is None:
                return _workspace_error("Season not found.", status.HTTP_404_NOT_FOUND)
            memberships = memberships.filter(season=season)
        return Response(
            {
                "count": memberships.count(),
                "results": LeagueClubMembershipSerializer(memberships, many=True).data,
            }
        )

    permission_error = _require_permission(
        request.user, workspace, "union.clubs.manage"
    )
    if permission_error:
        return permission_error

    league = _get_workspace_league(workspace, request.data.get("league"))
    club = _get_workspace_club(workspace, request.data.get("club"))
    season = _get_workspace_season(
        workspace, request.data.get("season") or request.data.get("season_id")
    )

    if league is None:
        return _workspace_error("A valid league is required.")
    if club is None:
        return _workspace_error("A valid club is required.")

    status_value = request.data.get("status") or LeagueClubMembership.Status.ACTIVE
    if status_value not in {
        choice[0] for choice in LeagueClubMembership.Status.choices
    }:
        return _workspace_error("Invalid league club status.")

    entry, _created = LeagueClubMembership.objects.update_or_create(
        league=league,
        club=club,
        season=season,
        defaults={
            "status": status_value,
            "notes": request.data.get("notes", ""),
            "created_by": request.user,
        },
    )

    return Response(
        LeagueClubMembershipSerializer(entry).data, status=status.HTTP_201_CREATED
    )


@api_view(["DELETE", "PATCH"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_league_club_detail_view(request, membership_id):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace
    permission_error = _require_permission(
        request.user, workspace, "union.clubs.manage"
    )
    if permission_error:
        return permission_error

    entry = (
        LeagueClubMembership.objects.filter(
            id=membership_id, league__union=workspace.related_union
        )
        .select_related("league", "club", "season")
        .first()
    )
    if entry is None:
        return _workspace_error(
            "League club entry not found.", status.HTTP_404_NOT_FOUND
        )

    if request.method == "DELETE":
        entry.status = LeagueClubMembership.Status.WITHDRAWN
        entry.notes = request.data.get("notes") or entry.notes
        entry.save(update_fields=["status", "notes", "updated_at"])
        return Response(LeagueClubMembershipSerializer(entry).data)

    status_value = request.data.get("status")
    if status_value:
        if status_value not in {
            choice[0] for choice in LeagueClubMembership.Status.choices
        }:
            return _workspace_error("Invalid league club status.")
        entry.status = status_value
    if "notes" in request.data:
        entry.notes = request.data.get("notes") or ""
    entry.save()
    return Response(LeagueClubMembershipSerializer(entry).data)


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_promote_relegate_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace
    permission_error = _require_permission(
        request.user, workspace, "union.clubs.manage"
    )
    if permission_error:
        return permission_error

    club = _get_workspace_club(workspace, request.data.get("club"))
    from_league = _get_workspace_league(workspace, request.data.get("from_league"))
    to_league = _get_workspace_league(workspace, request.data.get("to_league"))
    season = _get_workspace_season(workspace, request.data.get("season"))
    target_season = (
        _get_workspace_season(workspace, request.data.get("target_season")) or season
    )
    movement = (request.data.get("movement") or "PROMOTED").upper()

    if movement not in {
        LeagueClubMembership.Status.PROMOTED,
        LeagueClubMembership.Status.RELEGATED,
    }:
        return _workspace_error("movement must be PROMOTED or RELEGATED.")
    if club is None or from_league is None or to_league is None:
        return _workspace_error("club, from_league and to_league are required.")
    if from_league == to_league:
        return _workspace_error("from_league and to_league must be different.")

    with transaction.atomic():
        source, _ = LeagueClubMembership.objects.update_or_create(
            league=from_league,
            club=club,
            season=season,
            defaults={
                "status": movement,
                "relegated_to_league": (
                    to_league
                    if movement == LeagueClubMembership.Status.RELEGATED
                    else None
                ),
                "notes": request.data.get("notes", ""),
                "created_by": request.user,
            },
        )
        target, _ = LeagueClubMembership.objects.update_or_create(
            league=to_league,
            club=club,
            season=target_season,
            defaults={
                "status": movement,
                "promoted_from_league": (
                    from_league
                    if movement == LeagueClubMembership.Status.PROMOTED
                    else None
                ),
                "notes": request.data.get("notes", ""),
                "created_by": request.user,
            },
        )

    return Response(
        {
            "source": LeagueClubMembershipSerializer(source).data,
            "target": LeagueClubMembershipSerializer(target).data,
        }
    )


def _fixture_participants(competition):
    season = competition.season_record
    memberships = LeagueClubMembership.objects.filter(
        league=competition.league,
        status__in=[
            LeagueClubMembership.Status.ACTIVE,
            LeagueClubMembership.Status.PROMOTED,
        ],
    )
    if season:
        memberships = memberships.filter(season=season)

    clubs = list(
        Club.objects.filter(league_memberships__in=memberships)
        .distinct()
        .order_by("name")
    )

    if not clubs:
        clubs = list(
            Club.objects.filter(
                models.Q(home_matches__competition__league=competition.league)
                | models.Q(away_matches__competition__league=competition.league)
                | models.Q(standings__competition__league=competition.league)
            )
            .distinct()
            .order_by("name")
        )

    return clubs


def _round_robin_pairs(clubs):
    teams = list(clubs)
    if len(teams) % 2:
        teams.append(None)

    rounds = []
    total_rounds = max(len(teams) - 1, 0)

    for round_index in range(total_rounds):
        pairs = []
        for index in range(len(teams) // 2):
            home = teams[index]
            away = teams[-(index + 1)]
            if home is not None and away is not None:
                if round_index % 2 and index == 0:
                    home, away = away, home
                pairs.append((home, away))
        rounds.append(pairs)
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]

    return rounds


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_generate_fixtures_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace
    permission_error = _require_permission(
        request.user, workspace, "union.competitions.manage"
    )
    if permission_error:
        return permission_error

    competition = _get_workspace_competition(workspace, request.data.get("competition"))
    if competition is None:
        return _workspace_error("A valid competition is required.")

    existing = Match.objects.filter(competition=competition)
    clear_existing = bool(request.data.get("clear_existing", False))

    if existing.exists() and not clear_existing:
        return _workspace_error(
            "This competition already has fixtures. Send clear_existing=true to replace scheduled fixtures."
        )

    if clear_existing:
        if existing.exclude(status=Match.Status.SCHEDULED).exists():
            return _workspace_error(
                "Only competitions with scheduled-only fixtures can be regenerated."
            )
        existing.delete()

    clubs = _fixture_participants(competition)
    if len(clubs) < 2:
        return _workspace_error(
            "At least two league clubs are required to generate fixtures."
        )

    start_date = (
        parse_date(str(request.data.get("start_date") or ""))
        or competition.start_date
        or timezone.localdate()
    )
    kickoff = parse_time(str(request.data.get("kickoff_time") or "15:00"))
    interval_days = int(request.data.get("interval_days") or 7)
    home_and_away = bool(request.data.get("home_and_away", True))
    default_venue = (request.data.get("venue") or "").strip()

    rounds = _round_robin_pairs(clubs)
    if home_and_away:
        reverse_rounds = [
            [(away, home) for home, away in round_pairs] for round_pairs in rounds
        ]
        rounds = rounds + reverse_rounds

    created_matches = []
    timezone_value = timezone.get_current_timezone()

    with transaction.atomic():
        for round_index, round_pairs in enumerate(rounds, start=1):
            match_day = start_date + timedelta(days=interval_days * (round_index - 1))
            match_datetime = timezone.make_aware(
                datetime.combine(match_day, kickoff),
                timezone_value,
            )
            for home, away in round_pairs:
                created_matches.append(
                    Match.objects.create(
                        competition=competition,
                        home_club=home,
                        away_club=away,
                        match_date=match_datetime,
                        venue=default_venue or "Venue TBC",
                        round=f"Matchweek {round_index}",
                        status=Match.Status.SCHEDULED,
                    )
                )

    return Response(
        {
            "competition": CompetitionManagementSerializer(competition).data,
            "created_count": len(created_matches),
            "fixtures": MatchListSerializer(
                created_matches, many=True, context={"request": request}
            ).data,
        },
        status=status.HTTP_201_CREATED,
    )
