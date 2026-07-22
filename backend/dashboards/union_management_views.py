from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime, parse_time
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import Club
from accounts.permissions import IsAuthenticatedAudit
from accounts.rbac import log_governance_action
from teams.models import PlayerRegistration, Team
from .management_serializers import (
    ClubManagementSerializer,
    CompetitionManagementSerializer,
    FixtureOfficialAssignmentManagementSerializer,
    LeagueClubMembershipSerializer,
    LeagueManagementSerializer,
    MatchListSerializer,
    NationalTeamMemberSerializer,
    NationalTeamSerializer,
    SeasonManagementSerializer,
    UnionMatchOfficialManagementSerializer,
    UnionRegistrationApplicationSerializer,
)
from .models import (
    Competition,
    FixtureOfficialAssignment,
    League,
    LeagueClubMembership,
    Match,
    NationalTeam,
    NationalTeamMember,
    Season,
    UnionMatchOfficial,
    UnionRegistrationApplication,
    UnionWorkspaceMembership,
)
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


def _workspace_sport_value(workspace):
    value = (workspace.sport or "").strip().upper().replace(" ", "_")
    valid_values = {choice[0] for choice in Club.Sport.choices}
    return value if value in valid_values else Club.Sport.OTHER


def _workspace_management_clubs(workspace):
    """
    Return only clubs explicitly connected to the selected workspace.

    A shared sport is not sufficient evidence of workspace ownership.
    For example, FUFA, Budo League and SMACK League are all football
    workspaces but must never inherit one another's clubs.
    """
    if not workspace.related_union_id:
        return Club.objects.none()

    clubs = Club.objects.filter(
        models.Q(league_memberships__league__union=workspace.related_union)
        | models.Q(home_matches__competition__league__union=workspace.related_union)
        | models.Q(away_matches__competition__league__union=workspace.related_union)
        | models.Q(standings__competition__league__union=workspace.related_union)
    )

    return (
        clubs.distinct()
        .select_related("admin")
        .annotate(
            teams_count=models.Count("teams", distinct=True),
            players_count=models.Count("player_registrations", distinct=True),
        )
        .prefetch_related(
            "league_memberships__league",
            "league_memberships__season",
        )
        .order_by("name")
    )


def _resolve_existing_user_by_email(email):
    email_value = (email or "").strip().lower()
    if not email_value:
        return None, None

    User = get_user_model()
    user = User.objects.filter(email__iexact=email_value).first()

    if user is None:
        return None, _workspace_error(
            "No existing user found for the supplied admin email."
        )

    return user, None


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

    qs = _workspace_management_clubs(workspace)

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


def _parse_boolean(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _workspace_national_teams(workspace):
    active_member_filter = ~models.Q(members__status=NationalTeamMember.Status.RELEASED)
    return (
        NationalTeam.objects.filter(workspace=workspace)
        .select_related("workspace", "created_by")
        .annotate(
            players_count=models.Count(
                "members",
                filter=(
                    models.Q(members__member_type=NationalTeamMember.MemberType.PLAYER)
                    & active_member_filter
                ),
                distinct=True,
            ),
            staff_count=models.Count(
                "members",
                filter=(
                    models.Q(members__member_type=NationalTeamMember.MemberType.STAFF)
                    & active_member_filter
                ),
                distinct=True,
            ),
        )
        .order_by("name")
    )


def _get_workspace_national_team(workspace, value):
    if not value:
        return None
    queryset = _workspace_national_teams(workspace)
    if str(value).isdigit():
        return queryset.filter(id=value).first()
    return queryset.filter(slug=value).first()


def _get_workspace_team(workspace, value):
    if not value:
        return None
    queryset = Team.objects.filter(
        club__in=_workspace_management_clubs(workspace)
    ).select_related("club")
    if str(value).isdigit():
        return queryset.filter(id=value).first()
    return queryset.filter(name__iexact=value).first()


def _get_workspace_player_registration(workspace, value):
    if not value:
        return None
    queryset = PlayerRegistration.objects.filter(
        club__in=_workspace_management_clubs(workspace)
    ).select_related("club", "team")
    if str(value).isdigit():
        return queryset.filter(id=value).first()
    return queryset.filter(registration_number__iexact=value).first()


def _resolve_optional_user(value):
    if value in (None, ""):
        return None, None
    User = get_user_model()
    if str(value).isdigit():
        user = User.objects.filter(id=value).first()
    else:
        user = User.objects.filter(email__iexact=str(value).strip()).first()
    if user is None:
        return None, _workspace_error("The selected user account was not found.")
    return user, None


def _validate_choice(value, choices, field_name, default=None):
    normalized = str(value or default or "").strip().upper()
    valid = {choice[0] for choice in choices}
    if normalized not in valid:
        return None, _workspace_error(f"Invalid {field_name} value.")
    return normalized, None


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_clubs_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace

    if request.method == "GET":
        clubs = _workspace_management_clubs(workspace)

        query = (request.query_params.get("q") or "").strip()
        if query:
            clubs = clubs.filter(
                models.Q(name__icontains=query)
                | models.Q(short_name__icontains=query)
                | models.Q(admin__email__icontains=query)
            )

        return Response(
            {
                "count": clubs.count(),
                "results": ClubManagementSerializer(
                    clubs,
                    many=True,
                    context={"request": request},
                ).data,
            }
        )

    permission_error = _require_permission(
        request.user, workspace, "union.clubs.manage"
    )
    if permission_error:
        return permission_error

    name = (request.data.get("name") or "").strip()
    if not name:
        return _workspace_error("Club name is required.")

    if Club.objects.filter(name__iexact=name).exists():
        return _workspace_error("A club with this name already exists.")

    admin, admin_error = _resolve_existing_user_by_email(
        request.data.get("admin_email")
    )
    if admin_error:
        return admin_error

    sport_value = (
        (request.data.get("sport") or _workspace_sport_value(workspace))
        .strip()
        .upper()
        .replace(" ", "_")
    )
    if sport_value not in {choice[0] for choice in Club.Sport.choices}:
        sport_value = _workspace_sport_value(workspace)

    club = Club.objects.create(
        name=name,
        slug=_unique_slug(Club, name, Club.objects.all()),
        short_name=(request.data.get("short_name") or "").strip(),
        sport=sport_value,
        primary_color=(request.data.get("primary_color") or "").strip(),
        secondary_color=(request.data.get("secondary_color") or "").strip(),
        admin=admin,
    )

    return Response(
        ClubManagementSerializer(club, context={"request": request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_club_detail_view(request, club_id):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace
    club = _workspace_management_clubs(workspace).filter(id=club_id).first()

    if club is None:
        return _workspace_error("Club not found.", status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(
            ClubManagementSerializer(club, context={"request": request}).data
        )

    permission_error = _require_permission(
        request.user, workspace, "union.clubs.manage"
    )
    if permission_error:
        return permission_error

    if request.method == "DELETE":
        has_workspace_links = club.league_memberships.filter(
            league__union=workspace.related_union
        ).exists()
        has_matches = (
            club.home_matches.exists()
            or club.away_matches.exists()
            or club.standings.exists()
        )

        if has_workspace_links or has_matches:
            return _workspace_error(
                "This club has league, fixture or standings records. Remove it from a league season instead of deleting the club."
            )

        club.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    if "name" in request.data:
        name = (request.data.get("name") or "").strip()
        if not name:
            return _workspace_error("Club name cannot be blank.")
        if Club.objects.filter(name__iexact=name).exclude(id=club.id).exists():
            return _workspace_error("Another club with this name already exists.")
        club.name = name

    if "short_name" in request.data:
        club.short_name = (request.data.get("short_name") or "").strip()

    if "sport" in request.data:
        sport_value = (
            (request.data.get("sport") or "").strip().upper().replace(" ", "_")
        )
        if sport_value not in {choice[0] for choice in Club.Sport.choices}:
            return _workspace_error("Invalid sport value.")
        club.sport = sport_value

    if "primary_color" in request.data:
        club.primary_color = (request.data.get("primary_color") or "").strip()

    if "secondary_color" in request.data:
        club.secondary_color = (request.data.get("secondary_color") or "").strip()

    if "admin_email" in request.data:
        admin_email = (request.data.get("admin_email") or "").strip()
        if admin_email:
            admin, admin_error = _resolve_existing_user_by_email(admin_email)
            if admin_error:
                return admin_error
            club.admin = admin
        else:
            club.admin = None

    club.save()

    return Response(ClubManagementSerializer(club, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_leagues_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace
    leagues = _workspace_leagues(workspace).select_related("union")

    return Response(
        {
            "count": leagues.count(),
            "results": LeagueManagementSerializer(leagues, many=True).data,
        }
    )


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


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_league_clubs_bulk_add_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace

    permission_error = _require_permission(
        request.user, workspace, "union.competitions.manage"
    )
    if permission_error:
        return permission_error

    league_id = request.data.get("league")
    season_id = request.data.get("season")
    club_ids = request.data.get("club_ids") or []
    notes = (request.data.get("notes") or "").strip()
    status_value = request.data.get("status") or LeagueClubMembership.Status.ACTIVE
    valid_statuses = {choice[0] for choice in LeagueClubMembership.Status.choices}

    if status_value not in valid_statuses:
        return _workspace_error("Invalid club membership status.")

    if not league_id:
        return _workspace_error("League is required.")

    if not season_id:
        return _workspace_error("Season is required.")

    if not isinstance(club_ids, list) or not club_ids:
        return _workspace_error("Select at least one club to add.")

    league = _workspace_leagues(workspace).filter(id=league_id).first()
    if league is None:
        return _workspace_error("League not found.", status.HTTP_404_NOT_FOUND)

    season = Season.objects.filter(id=season_id, league=league).first()
    if season is None:
        return _workspace_error(
            "Season not found for this league.", status.HTTP_404_NOT_FOUND
        )

    clean_club_ids = []
    for club_id in club_ids:
        try:
            clean_club_ids.append(int(club_id))
        except (TypeError, ValueError):
            continue

    if not clean_club_ids:
        return _workspace_error("No valid club ids were supplied.")

    clubs = list(_workspace_management_clubs(workspace).filter(id__in=clean_club_ids))
    found_ids = {club.id for club in clubs}
    missing_ids = [club_id for club_id in clean_club_ids if club_id not in found_ids]

    created_count = 0
    updated_count = 0
    memberships = []

    for club in clubs:
        membership_record, was_created = LeagueClubMembership.objects.update_or_create(
            league=league,
            season=season,
            club=club,
            defaults={
                "status": status_value,
                "notes": notes,
            },
        )

        if was_created:
            created_count += 1
        else:
            updated_count += 1

        memberships.append(membership_record)

    memberships = (
        LeagueClubMembership.objects.filter(id__in=[item.id for item in memberships])
        .select_related(
            "league", "season", "club", "promoted_from_league", "relegated_to_league"
        )
        .order_by("club__name")
    )

    return Response(
        {
            "created": created_count,
            "updated": updated_count,
            "missing_club_ids": missing_ids,
            "results": LeagueClubMembershipSerializer(
                memberships,
                many=True,
                context={"request": request},
            ).data,
        },
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


WEEKDAY_LOOKUP = {
    "MONDAY": 0,
    "TUESDAY": 1,
    "WEDNESDAY": 2,
    "THURSDAY": 3,
    "FRIDAY": 4,
    "SATURDAY": 5,
    "SUNDAY": 6,
}


def _safe_positive_int(value, default, minimum=1, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    parsed = max(parsed, minimum)
    if maximum is not None:
        parsed = min(parsed, maximum)

    return parsed


def _normalise_match_days(raw_days):
    if not raw_days:
        return None

    if isinstance(raw_days, str):
        raw_days = [raw_days]

    allowed_days = set()

    for raw_day in raw_days:
        day = str(raw_day).strip().upper()
        if not day:
            continue

        if day.isdigit():
            numeric_day = int(day)
            if 0 <= numeric_day <= 6:
                allowed_days.add(numeric_day)
            continue

        if day in WEEKDAY_LOOKUP:
            allowed_days.add(WEEKDAY_LOOKUP[day])

    return allowed_days or None


def _normalise_excluded_dates(raw_dates):
    if not raw_dates:
        return set()

    if isinstance(raw_dates, str):
        raw_dates = [raw_dates]

    excluded = set()

    for raw_date in raw_dates:
        parsed = parse_date(str(raw_date).strip())
        if parsed:
            excluded.add(parsed)

    return excluded


def _normalise_venues(raw_venues, fallback_venue):
    if not raw_venues:
        return [
            {
                "name": fallback_venue or "Venue TBC",
                "pitches": ["Main Pitch"],
            }
        ]

    venues = []

    for raw_venue in raw_venues:
        if isinstance(raw_venue, str):
            venue_name = raw_venue.strip()
            pitches = ["Main Pitch"]
        elif isinstance(raw_venue, dict):
            venue_name = str(raw_venue.get("name") or "").strip()
            raw_pitches = (
                raw_venue.get("pitches")
                or raw_venue.get("courts")
                or raw_venue.get("fields")
                or []
            )
            if isinstance(raw_pitches, str):
                raw_pitches = [raw_pitches]
            pitches = [
                str(pitch).strip() for pitch in raw_pitches if str(pitch).strip()
            ]
            if not pitches:
                pitches = ["Main Pitch"]
        else:
            continue

        if venue_name:
            venues.append({"name": venue_name, "pitches": pitches})

    return venues or [
        {
            "name": fallback_venue or "Venue TBC",
            "pitches": ["Main Pitch"],
        }
    ]


def _format_fixture_venue(venue_name, pitch_name):
    if not pitch_name or pitch_name == "Main Pitch":
        return venue_name

    return f"{venue_name} - {pitch_name}"


def _parse_time_slots(raw_slots):
    if not raw_slots:
        return []

    if isinstance(raw_slots, str):
        raw_slots = [raw_slots]

    slots = []

    for raw_slot in raw_slots:
        parsed = parse_time(str(raw_slot).strip())
        if parsed:
            slots.append(parsed)

    return sorted(set(slots))


def _next_allowed_match_date(start_date, allowed_weekdays, excluded_dates):
    match_day = start_date

    for _ in range(370):
        weekday_ok = allowed_weekdays is None or match_day.weekday() in allowed_weekdays
        excluded = match_day in excluded_dates

        if weekday_ok and not excluded:
            return match_day

        match_day = match_day + timedelta(days=1)

    return start_date


def _build_day_slots(
    match_day,
    venues,
    explicit_time_slots,
    first_kickoff,
    match_duration_minutes,
    turnaround_minutes,
    max_games_per_day,
    timezone_value,
):
    pitch_count = sum(max(len(venue["pitches"]), 1) for venue in venues)
    pitch_count = max(pitch_count, 1)

    if explicit_time_slots:
        time_slots = explicit_time_slots
    else:
        slot_gap = timedelta(minutes=match_duration_minutes + turnaround_minutes)
        sequential_windows = max(
            1,
            (max_games_per_day + pitch_count - 1) // pitch_count,
        )
        anchor = datetime.combine(match_day, first_kickoff)
        time_slots = [
            (anchor + slot_gap * index).time() for index in range(sequential_windows)
        ]

    slots = []

    for slot_time in time_slots:
        slot_datetime = timezone.make_aware(
            datetime.combine(match_day, slot_time),
            timezone_value,
        )
        for venue in venues:
            for pitch in venue["pitches"]:
                slots.append(
                    {
                        "datetime": slot_datetime,
                        "venue": _format_fixture_venue(venue["name"], pitch),
                        "pitch": pitch,
                    }
                )

    return slots[:max_games_per_day]


def _get_workspace_match(workspace, match_id):
    return (
        Match.objects.select_related(
            "competition",
            "competition__league",
            "home_club",
            "away_club",
        )
        .filter(id=match_id, competition__league__union=workspace.related_union)
        .first()
    )


def _fixture_datetime_from_request(request, current_match_date):
    raw_match_date = str(request.data.get("match_date") or "").strip()
    parsed_datetime = parse_datetime(raw_match_date) if raw_match_date else None

    if parsed_datetime:
        if timezone.is_naive(parsed_datetime):
            return timezone.make_aware(
                parsed_datetime,
                timezone.get_current_timezone(),
            )
        return parsed_datetime

    current_local = timezone.localtime(current_match_date)
    requested_date = parse_date(str(request.data.get("scheduled_date") or "").strip())
    requested_time = parse_time(
        str(request.data.get("kickoff_time") or request.data.get("time") or "").strip()
    )

    if requested_date is None and requested_time is None:
        return current_match_date

    fixture_date = requested_date or current_local.date()
    fixture_time = requested_time or current_local.time().replace(microsecond=0)

    return timezone.make_aware(
        datetime.combine(fixture_date, fixture_time),
        timezone.get_current_timezone(),
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_fixture_reschedule_view(request, match_id):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace

    permission_error = _require_permission(
        request.user,
        workspace,
        "union.competitions.manage",
    )
    if permission_error:
        return permission_error

    match = _get_workspace_match(workspace, match_id)
    if match is None:
        return _workspace_error("Fixture not found.", status.HTTP_404_NOT_FOUND)

    if match.status in [Match.Status.COMPLETED, Match.Status.ABANDONED]:
        return _workspace_error("Completed or abandoned matches cannot be rescheduled.")

    status_value = request.data.get("status") or match.status
    valid_statuses = {choice[0] for choice in Match.Status.choices}

    if status_value not in valid_statuses:
        return _workspace_error("Invalid fixture status.")

    previous = {
        "match_date": match.match_date.isoformat(),
        "venue": match.venue,
        "round": match.round,
        "status": match.status,
    }

    new_match_date = _fixture_datetime_from_request(request, match.match_date)

    venue_value = request.data.get("venue")
    pitch_value = str(
        request.data.get("pitch")
        or request.data.get("field")
        or request.data.get("court")
        or ""
    ).strip()

    if venue_value is not None or pitch_value:
        venue_name = str(venue_value or match.venue or "Venue TBC").strip()
        match.venue = _format_fixture_venue(venue_name, pitch_value)
    else:
        match.venue = match.venue or "Venue TBC"

    if "round" in request.data:
        match.round = str(request.data.get("round") or "").strip()

    match.match_date = new_match_date
    match.status = status_value
    match.save(update_fields=["match_date", "venue", "round", "status", "updated_at"])

    reason = str(request.data.get("reason") or "").strip()

    log_governance_action(
        actor=request.user,
        action="fixture_rescheduled",
        details={
            "workspace": workspace.slug,
            "competition": match.competition_id,
            "match": match.id,
            "home_club": match.home_club.name,
            "away_club": match.away_club.name,
            "previous": previous,
            "updated": {
                "match_date": match.match_date.isoformat(),
                "venue": match.venue,
                "round": match.round,
                "status": match.status,
            },
            "reason": reason,
        },
    )

    return Response(
        {
            "previous": previous,
            "updated": MatchListSerializer(
                match,
                context={"request": request},
            ).data,
            "reason": reason,
        }
    )


OFFICIAL_ROLES_BY_SPORT = {
    "RUGBY": {
        UnionMatchOfficial.RoleType.CENTRE_REFEREE,
        UnionMatchOfficial.RoleType.ASSISTANT_REFEREE,
        UnionMatchOfficial.RoleType.TMO,
        UnionMatchOfficial.RoleType.MATCH_COMMISSIONER,
        UnionMatchOfficial.RoleType.ASSESSOR,
        UnionMatchOfficial.RoleType.CITING_COMMISSIONER,
        UnionMatchOfficial.RoleType.TIMEKEEPER,
        UnionMatchOfficial.RoleType.SUBSTITUTION_CONTROLLER,
        UnionMatchOfficial.RoleType.TECHNICAL_ZONE_OFFICIAL,
        UnionMatchOfficial.RoleType.SCOREBOARD_OPERATOR,
        UnionMatchOfficial.RoleType.OTHER,
    },
    "FOOTBALL": {
        UnionMatchOfficial.RoleType.CENTRE_REFEREE,
        UnionMatchOfficial.RoleType.ASSISTANT_REFEREE,
        UnionMatchOfficial.RoleType.FOURTH_OFFICIAL,
        UnionMatchOfficial.RoleType.VAR,
        UnionMatchOfficial.RoleType.AVAR,
        UnionMatchOfficial.RoleType.MATCH_COMMISSIONER,
        UnionMatchOfficial.RoleType.ASSESSOR,
        UnionMatchOfficial.RoleType.MATCH_COORDINATOR,
        UnionMatchOfficial.RoleType.OTHER,
    },
    "BASKETBALL": {
        UnionMatchOfficial.RoleType.CREW_CHIEF,
        UnionMatchOfficial.RoleType.UMPIRE,
        UnionMatchOfficial.RoleType.MATCH_COMMISSIONER,
        UnionMatchOfficial.RoleType.TABLE_OFFICIAL,
        UnionMatchOfficial.RoleType.SCORER,
        UnionMatchOfficial.RoleType.ASSISTANT_SCORER,
        UnionMatchOfficial.RoleType.TIMER,
        UnionMatchOfficial.RoleType.SHOT_CLOCK_OPERATOR,
        UnionMatchOfficial.RoleType.ASSESSOR,
        UnionMatchOfficial.RoleType.OTHER,
    },
}

DEFAULT_OFFICIAL_ROLE_BY_SPORT = {
    "RUGBY": UnionMatchOfficial.RoleType.CENTRE_REFEREE,
    "FOOTBALL": UnionMatchOfficial.RoleType.CENTRE_REFEREE,
    "BASKETBALL": UnionMatchOfficial.RoleType.CREW_CHIEF,
}


def _normalise_official_sport(value):
    return str(value or "").strip().upper().replace(" ", "_")


def _official_role_options_for_sport(sport_value):
    labels = dict(UnionMatchOfficial.RoleType.choices)
    allowed_roles = OFFICIAL_ROLES_BY_SPORT.get(sport_value, set())

    return [
        {
            "value": role,
            "label": labels.get(role, role.replace("_", " ").title()),
        }
        for role in sorted(allowed_roles, key=lambda item: labels.get(item, item))
    ]


def _workspace_match_officials(workspace):
    workspace_sport = _workspace_sport_value(workspace)

    return UnionMatchOfficial.objects.filter(
        union=workspace.related_union,
        primary_sport__iexact=workspace_sport,
    )


def _get_workspace_match_official(workspace, official_id):
    return _workspace_match_officials(workspace).filter(id=official_id).first()


def _normalise_official_role(value, sport_value):
    allowed_roles = OFFICIAL_ROLES_BY_SPORT.get(sport_value, set())
    default_role = DEFAULT_OFFICIAL_ROLE_BY_SPORT.get(
        sport_value,
        UnionMatchOfficial.RoleType.OTHER,
    )

    if value in (None, ""):
        return default_role

    role_value = str(value).strip().upper()
    return role_value if role_value in allowed_roles else None


def _ensure_match_official_workspace_membership(workspace, user):
    if user is None:
        return None

    membership = UnionWorkspaceMembership.objects.filter(
        user=user,
        workspace=workspace,
    ).first()

    if membership is None:
        return UnionWorkspaceMembership.objects.create(
            user=user,
            workspace=workspace,
            role=UnionWorkspaceMembership.Role.MATCH_OFFICIAL,
            is_active=True,
        )

    update_fields = []

    if not membership.is_active:
        membership.is_active = True
        update_fields.append("is_active")

    if membership.role == UnionWorkspaceMembership.Role.VIEWER:
        membership.role = UnionWorkspaceMembership.Role.MATCH_OFFICIAL
        update_fields.append("role")

    if update_fields:
        update_fields.append("updated_at")
        membership.save(update_fields=update_fields)

    return membership


def _normalise_official_status(value):
    status_value = str(value or "").strip().upper()

    valid_statuses = {choice[0] for choice in UnionMatchOfficial.Status.choices}
    return (
        status_value
        if status_value in valid_statuses
        else UnionMatchOfficial.Status.AVAILABLE
    )


def _normalise_assignment_status(value):
    status_value = str(value or "").strip().upper()

    valid_statuses = {choice[0] for choice in FixtureOfficialAssignment.Status.choices}
    return (
        status_value
        if status_value in valid_statuses
        else FixtureOfficialAssignment.Status.ASSIGNED
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_match_officials_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace
    workspace_sport = _workspace_sport_value(workspace)

    permission_error = _require_permission(
        request.user, workspace, "union.referees.manage"
    )
    if permission_error:
        return permission_error

    if request.method == "GET":
        officials = _workspace_match_officials(workspace).select_related("user")

        query = str(request.query_params.get("q") or "").strip()
        if query:
            officials = officials.filter(
                models.Q(full_name__icontains=query)
                | models.Q(email__icontains=query)
                | models.Q(role_type__icontains=query)
                | models.Q(certification_level__icontains=query)
                | models.Q(status__icontains=query)
            )

        return Response(
            {
                "count": officials.count(),
                "sport": workspace_sport,
                "role_options": _official_role_options_for_sport(workspace_sport),
                "results": UnionMatchOfficialManagementSerializer(
                    officials,
                    many=True,
                    context={"request": request},
                ).data,
            }
        )

    email = str(request.data.get("email") or "").strip().lower()
    full_name = str(
        request.data.get("full_name") or request.data.get("name") or ""
    ).strip()
    requested_sport = _normalise_official_sport(request.data.get("primary_sport"))

    if requested_sport and requested_sport != workspace_sport:
        return _workspace_error(
            f"Officials in this workspace must belong to {workspace_sport.title()}."
        )

    role_type = _normalise_official_role(
        request.data.get("role_type"),
        workspace_sport,
    )

    if role_type is None:
        return _workspace_error(
            f"The selected official role is not valid for {workspace_sport.title()}."
        )

    linked_user = None
    if email:
        linked_user = get_user_model().objects.filter(email__iexact=email).first()

    if not full_name and linked_user:
        full_name = linked_user.full_name or linked_user.email

    if not full_name:
        return _workspace_error("Official full name is required.")

    defaults = {
        "user": linked_user,
        "full_name": full_name,
        "phone_number": str(request.data.get("phone_number") or "").strip(),
        "role_type": role_type,
        "certification_level": str(
            request.data.get("certification_level") or ""
        ).strip(),
        "primary_sport": workspace_sport,
        "competitions": str(request.data.get("competitions") or "").strip(),
        "status": _normalise_official_status(request.data.get("status")),
        "notes": str(request.data.get("notes") or "").strip(),
        "created_by": request.user,
    }

    if email:
        official, created = UnionMatchOfficial.objects.update_or_create(
            union=workspace.related_union,
            email=email,
            defaults=defaults,
        )
    else:
        official = UnionMatchOfficial.objects.create(
            union=workspace.related_union,
            email="",
            **defaults,
        )
        created = True

    _ensure_match_official_workspace_membership(
        workspace,
        official.user,
    )

    log_governance_action(
        actor=request.user,
        action="match_official_created" if created else "match_official_updated",
        details={
            "workspace": workspace.slug,
            "official": official.id,
            "email": official.email,
            "role_type": official.role_type,
            "status": official.status,
        },
    )

    return Response(
        UnionMatchOfficialManagementSerializer(
            official,
            context={"request": request},
        ).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_match_official_detail_view(request, official_id):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace
    workspace_sport = _workspace_sport_value(workspace)

    permission_error = _require_permission(
        request.user, workspace, "union.referees.manage"
    )
    if permission_error:
        return permission_error

    official = _get_workspace_match_official(workspace, official_id)
    if official is None:
        return _workspace_error("Match official not found.", status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(
            UnionMatchOfficialManagementSerializer(
                official,
                context={"request": request},
            ).data
        )

    if request.method == "DELETE":
        if official.assignments.exists():
            return _workspace_error(
                "Officials with fixture assignments cannot be deleted. Mark them unavailable or suspended instead."
            )

        official.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    if "full_name" in request.data or "name" in request.data:
        official.full_name = str(
            request.data.get("full_name")
            or request.data.get("name")
            or official.full_name
        ).strip()
    if "email" in request.data:
        official.email = str(request.data.get("email") or "").strip().lower()
        official.user = (
            get_user_model().objects.filter(email__iexact=official.email).first()
            if official.email
            else None
        )
    if "phone_number" in request.data:
        official.phone_number = str(request.data.get("phone_number") or "").strip()
    if "role_type" in request.data:
        role_type = _normalise_official_role(
            request.data.get("role_type"),
            workspace_sport,
        )

        if role_type is None:
            return _workspace_error(
                f"The selected official role is not valid for {workspace_sport.title()}."
            )

        official.role_type = role_type
    if "certification_level" in request.data:
        official.certification_level = str(
            request.data.get("certification_level") or ""
        ).strip()
    if "primary_sport" in request.data:
        requested_sport = _normalise_official_sport(request.data.get("primary_sport"))

        if requested_sport and requested_sport != workspace_sport:
            return _workspace_error(
                f"Officials in this workspace must belong to {workspace_sport.title()}."
            )
    if "competitions" in request.data:
        official.competitions = str(request.data.get("competitions") or "").strip()
    if "status" in request.data:
        official.status = _normalise_official_status(request.data.get("status"))
    if "notes" in request.data:
        official.notes = str(request.data.get("notes") or "").strip()

    official.primary_sport = workspace_sport
    official.save()

    _ensure_match_official_workspace_membership(
        workspace,
        official.user,
    )

    log_governance_action(
        actor=request.user,
        action="match_official_updated",
        details={
            "workspace": workspace.slug,
            "official": official.id,
            "status": official.status,
        },
    )

    return Response(
        UnionMatchOfficialManagementSerializer(
            official,
            context={"request": request},
        ).data
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_fixture_official_appointments_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace
    workspace_sport = _workspace_sport_value(workspace)

    permission_error = _require_permission(
        request.user, workspace, "union.referees.manage"
    )
    if permission_error:
        return permission_error

    if request.method == "GET":
        assignments = FixtureOfficialAssignment.objects.select_related(
            "match",
            "match__competition",
            "match__home_club",
            "match__away_club",
            "official",
        ).filter(match__competition__league__union=workspace.related_union)

        match_id = request.query_params.get("match")
        official_id = request.query_params.get("official")

        if match_id:
            assignments = assignments.filter(match_id=match_id)
        if official_id:
            assignments = assignments.filter(official_id=official_id)

        return Response(
            {
                "count": assignments.count(),
                "results": FixtureOfficialAssignmentManagementSerializer(
                    assignments,
                    many=True,
                    context={"request": request},
                ).data,
            }
        )

    match = _get_workspace_match(workspace, request.data.get("match"))
    if match is None:
        return _workspace_error("A valid workspace fixture is required.")

    fixture_sports = {
        str(match.home_club.sport or "").strip().upper(),
        str(match.away_club.sport or "").strip().upper(),
    }

    if fixture_sports != {workspace_sport}:
        return _workspace_error(
            "The selected fixture does not match the workspace sport."
        )

    official = _get_workspace_match_official(workspace, request.data.get("official"))
    if official is None:
        return _workspace_error("A valid match official is required.")

    role_type = _normalise_official_role(
        request.data.get("role_type"),
        workspace_sport,
    )

    if role_type is None:
        return _workspace_error(
            f"The selected appointment role is not valid for {workspace_sport.title()}."
        )

    assignment_status = _normalise_assignment_status(request.data.get("status"))
    if assignment_status not in {
        FixtureOfficialAssignment.Status.PROPOSED,
        FixtureOfficialAssignment.Status.ASSIGNED,
    }:
        return _workspace_error(
            "New appointments must be PROPOSED or ASSIGNED. Officials control ACCEPTED and DECLINED responses."
        )

    assignment, created = FixtureOfficialAssignment.objects.update_or_create(
        match=match,
        official=official,
        role_type=role_type,
        defaults={
            "status": assignment_status,
            "notes": str(request.data.get("notes") or "").strip(),
            "assigned_by": request.user,
        },
    )

    log_governance_action(
        actor=request.user,
        action=(
            "fixture_official_assigned"
            if created
            else "fixture_official_assignment_updated"
        ),
        details={
            "workspace": workspace.slug,
            "match": match.id,
            "official": official.id,
            "role_type": role_type,
            "status": assignment.status,
        },
    )

    return Response(
        FixtureOfficialAssignmentManagementSerializer(
            assignment,
            context={"request": request},
        ).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_fixture_official_appointment_detail_view(request, assignment_id):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace
    workspace_sport = _workspace_sport_value(workspace)

    permission_error = _require_permission(
        request.user, workspace, "union.referees.manage"
    )
    if permission_error:
        return permission_error

    assignment = (
        FixtureOfficialAssignment.objects.select_related(
            "match",
            "match__competition",
            "match__home_club",
            "match__away_club",
            "official",
        )
        .filter(
            id=assignment_id, match__competition__league__union=workspace.related_union
        )
        .first()
    )

    if assignment is None:
        return _workspace_error(
            "Official appointment not found.", status.HTTP_404_NOT_FOUND
        )

    if request.method == "DELETE":
        if assignment.status in {
            FixtureOfficialAssignment.Status.ACCEPTED,
            FixtureOfficialAssignment.Status.DECLINED,
        }:
            return _workspace_error(
                "Accepted or declined appointments must be cancelled rather than deleted."
            )
        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    if "role_type" in request.data:
        role_type = _normalise_official_role(
            request.data.get("role_type"),
            workspace_sport,
        )

        if role_type is None:
            return _workspace_error(
                f"The selected appointment role is not valid for {workspace_sport.title()}."
            )

        assignment.role_type = role_type
    if "status" in request.data:
        next_status = _normalise_assignment_status(request.data.get("status"))
        if next_status not in {
            FixtureOfficialAssignment.Status.PROPOSED,
            FixtureOfficialAssignment.Status.ASSIGNED,
            FixtureOfficialAssignment.Status.CANCELLED,
        }:
            return _workspace_error(
                "Administrators may only set PROPOSED, ASSIGNED or CANCELLED. Officials control ACCEPTED and DECLINED responses."
            )
        if (
            assignment.status
            in {
                FixtureOfficialAssignment.Status.ACCEPTED,
                FixtureOfficialAssignment.Status.DECLINED,
            }
            and next_status != FixtureOfficialAssignment.Status.CANCELLED
        ):
            return _workspace_error(
                "An official response can only be preserved or cancelled; it cannot be reset by an administrator."
            )
        assignment.status = next_status
        if next_status in {
            FixtureOfficialAssignment.Status.PROPOSED,
            FixtureOfficialAssignment.Status.ASSIGNED,
        }:
            assignment.response_note = ""
            assignment.responded_at = None
    if "notes" in request.data:
        assignment.notes = str(request.data.get("notes") or "").strip()

    assignment.save()

    return Response(
        FixtureOfficialAssignmentManagementSerializer(
            assignment,
            context={"request": request},
        ).data
    )


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
    first_kickoff = (
        parse_time(str(request.data.get("first_kickoff_time") or ""))
        or parse_time(str(request.data.get("kickoff_time") or ""))
        or parse_time("15:00")
    )
    explicit_time_slots = _parse_time_slots(request.data.get("time_slots"))
    interval_days = _safe_positive_int(request.data.get("interval_days"), 7, 1, 90)
    match_duration_minutes = _safe_positive_int(
        request.data.get("match_duration_minutes"), 80, 1, 240
    )
    turnaround_minutes = _safe_positive_int(
        request.data.get("turnaround_minutes"), 20, 0, 180
    )
    max_games_per_day = _safe_positive_int(
        request.data.get("max_games_per_day"), 8, 1, 80
    )
    home_and_away = bool(request.data.get("home_and_away", True))
    default_venue = (request.data.get("venue") or "").strip()
    venues = _normalise_venues(request.data.get("venues"), default_venue)
    allowed_weekdays = _normalise_match_days(request.data.get("match_days"))
    excluded_dates = _normalise_excluded_dates(
        request.data.get("excluded_dates") or request.data.get("rest_weeks")
    )

    rounds = _round_robin_pairs(clubs)
    if home_and_away:
        reverse_rounds = [
            [(away, home) for home, away in round_pairs] for round_pairs in rounds
        ]
        rounds = rounds + reverse_rounds

    created_matches = []
    byes = []
    timezone_value = timezone.get_current_timezone()
    cursor_date = start_date

    with transaction.atomic():
        for round_index, round_pairs in enumerate(rounds, start=1):
            round_label = f"Matchweek {round_index}"
            round_club_ids = {
                club.id for pair in round_pairs for club in pair if club is not None
            }
            bye_clubs = [club for club in clubs if club.id not in round_club_ids]
            for club in bye_clubs:
                byes.append(
                    {
                        "round": round_label,
                        "club": club.id,
                        "club_name": club.name,
                    }
                )

            unscheduled_pairs = list(round_pairs)
            round_first_date = _next_allowed_match_date(
                cursor_date,
                allowed_weekdays,
                excluded_dates,
            )
            match_day = round_first_date

            while unscheduled_pairs:
                match_day = _next_allowed_match_date(
                    match_day,
                    allowed_weekdays,
                    excluded_dates,
                )
                day_slots = _build_day_slots(
                    match_day,
                    venues,
                    explicit_time_slots,
                    first_kickoff,
                    match_duration_minutes,
                    turnaround_minutes,
                    max_games_per_day,
                    timezone_value,
                )

                if not day_slots:
                    return _workspace_error(
                        "No valid fixture slots could be generated."
                    )

                for slot in day_slots:
                    if not unscheduled_pairs:
                        break

                    home, away = unscheduled_pairs.pop(0)
                    created_matches.append(
                        Match.objects.create(
                            competition=competition,
                            home_club=home,
                            away_club=away,
                            match_date=slot["datetime"],
                            venue=slot["venue"],
                            round=round_label,
                            status=Match.Status.SCHEDULED,
                        )
                    )

                if unscheduled_pairs:
                    match_day = match_day + timedelta(days=1)

            cursor_date = round_first_date + timedelta(days=interval_days)

    return Response(
        {
            "competition": CompetitionManagementSerializer(competition).data,
            "created_count": len(created_matches),
            "schedule_rules": {
                "start_date": start_date,
                "match_days": request.data.get("match_days") or [],
                "interval_days": interval_days,
                "first_kickoff_time": first_kickoff,
                "time_slots": explicit_time_slots,
                "match_duration_minutes": match_duration_minutes,
                "turnaround_minutes": turnaround_minutes,
                "max_games_per_day": max_games_per_day,
                "venues": venues,
                "excluded_dates": sorted(excluded_dates),
                "home_and_away": home_and_away,
            },
            "byes": byes,
            "fixtures": MatchListSerializer(
                created_matches, many=True, context={"request": request}
            ).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_national_teams_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace
    permission_error = _require_permission(
        request.user, workspace, "union.teams.manage"
    )
    if permission_error:
        return permission_error

    if request.method == "GET":
        teams = _workspace_national_teams(workspace)
        query = str(request.query_params.get("q") or "").strip()
        status_value = str(request.query_params.get("status") or "").strip().upper()
        active_value = request.query_params.get("is_active")

        if query:
            teams = teams.filter(
                models.Q(name__icontains=query)
                | models.Q(category__icontains=query)
                | models.Q(head_coach__icontains=query)
            )
        if status_value:
            if status_value not in {
                choice[0] for choice in NationalTeam.Status.choices
            }:
                return _workspace_error("Invalid national team status value.")
            teams = teams.filter(status=status_value)
        if active_value is not None:
            teams = teams.filter(is_active=_parse_boolean(active_value))

        return Response(
            {
                "count": teams.count(),
                "results": NationalTeamSerializer(teams, many=True).data,
            }
        )

    name = str(request.data.get("name") or "").strip()
    category = str(request.data.get("category") or "").strip()
    if not name:
        return _workspace_error("National team name is required.")
    if not category:
        return _workspace_error("National team category is required.")

    status_value, choice_error = _validate_choice(
        request.data.get("status"),
        NationalTeam.Status.choices,
        "national team status",
        NationalTeam.Status.ACTIVE,
    )
    if choice_error:
        return choice_error

    team = NationalTeam.objects.create(
        workspace=workspace,
        name=name,
        slug=_unique_slug(
            NationalTeam,
            name,
            NationalTeam.objects.filter(workspace=workspace),
        ),
        category=category,
        gender=str(request.data.get("gender") or "").strip(),
        age_group=str(request.data.get("age_group") or "").strip(),
        head_coach=str(request.data.get("head_coach") or "").strip(),
        status=status_value,
        notes=str(request.data.get("notes") or "").strip(),
        is_active=_parse_boolean(request.data.get("is_active"), True),
        created_by=request.user,
    )

    log_governance_action(
        actor=request.user,
        action="national_team_created",
        details={"workspace": workspace.slug, "national_team": team.id},
    )
    team = _workspace_national_teams(workspace).get(id=team.id)
    return Response(NationalTeamSerializer(team).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_national_team_detail_view(request, team_id):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    permission_error = _require_permission(
        request.user, workspace, "union.teams.manage"
    )
    if permission_error:
        return permission_error

    team = _get_workspace_national_team(workspace, team_id)
    if team is None:
        return _workspace_error("National team not found.", status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(NationalTeamSerializer(team).data)

    if request.method == "DELETE":
        team_id_value = team.id
        team.delete()
        log_governance_action(
            actor=request.user,
            action="national_team_deleted",
            details={"workspace": workspace.slug, "national_team": team_id_value},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    if "name" in request.data:
        name = str(request.data.get("name") or "").strip()
        if not name:
            return _workspace_error("National team name cannot be blank.")
        team.name = name
    if "category" in request.data:
        category = str(request.data.get("category") or "").strip()
        if not category:
            return _workspace_error("National team category cannot be blank.")
        team.category = category
    for field in ("gender", "age_group", "head_coach", "notes"):
        if field in request.data:
            setattr(team, field, str(request.data.get(field) or "").strip())
    if "status" in request.data:
        status_value, choice_error = _validate_choice(
            request.data.get("status"),
            NationalTeam.Status.choices,
            "national team status",
        )
        if choice_error:
            return choice_error
        team.status = status_value
    if "is_active" in request.data:
        team.is_active = _parse_boolean(request.data.get("is_active"), team.is_active)

    team.save()
    log_governance_action(
        actor=request.user,
        action="national_team_updated",
        details={"workspace": workspace.slug, "national_team": team.id},
    )
    team = _workspace_national_teams(workspace).get(id=team.id)
    return Response(NationalTeamSerializer(team).data)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_national_team_members_view(request, team_id):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    permission_error = _require_permission(
        request.user, workspace, "union.teams.manage"
    )
    if permission_error:
        return permission_error

    team = _get_workspace_national_team(workspace, team_id)
    if team is None:
        return _workspace_error("National team not found.", status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        members = team.members.select_related("team", "user", "club")
        member_type = str(request.query_params.get("member_type") or "").strip().upper()
        status_value = str(request.query_params.get("status") or "").strip().upper()
        query = str(request.query_params.get("q") or "").strip()
        if member_type:
            if member_type not in {
                choice[0] for choice in NationalTeamMember.MemberType.choices
            }:
                return _workspace_error("Invalid member type value.")
            members = members.filter(member_type=member_type)
        if status_value:
            if status_value not in {
                choice[0] for choice in NationalTeamMember.Status.choices
            }:
                return _workspace_error("Invalid member status value.")
            members = members.filter(status=status_value)
        if query:
            members = members.filter(
                models.Q(full_name__icontains=query)
                | models.Q(role__icontains=query)
                | models.Q(club__name__icontains=query)
            )
        return Response(
            {
                "count": members.count(),
                "results": NationalTeamMemberSerializer(members, many=True).data,
            }
        )

    full_name = str(request.data.get("full_name") or "").strip()
    if not full_name:
        return _workspace_error("Member full name is required.")
    member_type, choice_error = _validate_choice(
        request.data.get("member_type"),
        NationalTeamMember.MemberType.choices,
        "member type",
        NationalTeamMember.MemberType.PLAYER,
    )
    if choice_error:
        return choice_error
    status_value, choice_error = _validate_choice(
        request.data.get("status"),
        NationalTeamMember.Status.choices,
        "member status",
        NationalTeamMember.Status.ACTIVE,
    )
    if choice_error:
        return choice_error

    club = None
    if request.data.get("club") not in (None, ""):
        club = _get_workspace_club(workspace, request.data.get("club"))
        if club is None:
            return _workspace_error("The selected club is not in this workspace.")
    user, user_error = _resolve_optional_user(request.data.get("user"))
    if user_error:
        return user_error

    if user and team.members.filter(user=user, member_type=member_type).exists():
        return _workspace_error(
            "This user is already attached to the team in that role."
        )

    try:
        member = NationalTeamMember.objects.create(
            team=team,
            user=user,
            club=club,
            full_name=full_name,
            member_type=member_type,
            role=str(request.data.get("role") or "").strip(),
            status=status_value,
            notes=str(request.data.get("notes") or "").strip(),
        )
    except IntegrityError:
        return _workspace_error("This member already exists for the selected team.")

    log_governance_action(
        actor=request.user,
        action="national_team_member_created",
        details={
            "workspace": workspace.slug,
            "national_team": team.id,
            "member": member.id,
        },
    )
    return Response(
        NationalTeamMemberSerializer(member).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_national_team_member_detail_view(request, team_id, member_id):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    permission_error = _require_permission(
        request.user, workspace, "union.teams.manage"
    )
    if permission_error:
        return permission_error

    team = _get_workspace_national_team(workspace, team_id)
    if team is None:
        return _workspace_error("National team not found.", status.HTTP_404_NOT_FOUND)
    member = (
        team.members.select_related("team", "user", "club").filter(id=member_id).first()
    )
    if member is None:
        return _workspace_error(
            "National team member not found.", status.HTTP_404_NOT_FOUND
        )

    if request.method == "DELETE":
        member.delete()
        log_governance_action(
            actor=request.user,
            action="national_team_member_deleted",
            details={
                "workspace": workspace.slug,
                "national_team": team.id,
                "member": member_id,
            },
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    if "full_name" in request.data:
        full_name = str(request.data.get("full_name") or "").strip()
        if not full_name:
            return _workspace_error("Member full name cannot be blank.")
        member.full_name = full_name
    if "member_type" in request.data:
        member_type, choice_error = _validate_choice(
            request.data.get("member_type"),
            NationalTeamMember.MemberType.choices,
            "member type",
        )
        if choice_error:
            return choice_error
        member.member_type = member_type
    if "status" in request.data:
        status_value, choice_error = _validate_choice(
            request.data.get("status"),
            NationalTeamMember.Status.choices,
            "member status",
        )
        if choice_error:
            return choice_error
        member.status = status_value
    for field in ("role", "notes"):
        if field in request.data:
            setattr(member, field, str(request.data.get(field) or "").strip())
    if "club" in request.data:
        club_value = request.data.get("club")
        if club_value in (None, ""):
            member.club = None
        else:
            club = _get_workspace_club(workspace, club_value)
            if club is None:
                return _workspace_error("The selected club is not in this workspace.")
            member.club = club
    if "user" in request.data:
        user, user_error = _resolve_optional_user(request.data.get("user"))
        if user_error:
            return user_error
        member.user = user

    if (
        member.user
        and team.members.exclude(id=member.id)
        .filter(user=member.user, member_type=member.member_type)
        .exists()
    ):
        return _workspace_error(
            "This user is already attached to the team in that role."
        )

    try:
        member.save()
    except IntegrityError:
        return _workspace_error("This member already exists for the selected team.")

    log_governance_action(
        actor=request.user,
        action="national_team_member_updated",
        details={
            "workspace": workspace.slug,
            "national_team": team.id,
            "member": member.id,
        },
    )
    return Response(NationalTeamMemberSerializer(member).data)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_registration_applications_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    permission_error = _require_permission(
        request.user, workspace, "union.players.approve"
    )
    if permission_error:
        return permission_error

    if request.method == "GET":
        applications = UnionRegistrationApplication.objects.filter(
            workspace=workspace
        ).select_related(
            "workspace",
            "club",
            "team",
            "competition",
            "player_registration",
            "submitted_by",
            "reviewed_by",
        )
        status_value = str(request.query_params.get("status") or "").strip().upper()
        application_type = (
            str(request.query_params.get("application_type") or "").strip().upper()
        )
        club_value = request.query_params.get("club")
        query = str(request.query_params.get("q") or "").strip()
        if status_value:
            if status_value not in {
                choice[0] for choice in UnionRegistrationApplication.Status.choices
            }:
                return _workspace_error("Invalid registration status value.")
            applications = applications.filter(status=status_value)
        if application_type:
            if application_type not in {
                choice[0]
                for choice in UnionRegistrationApplication.ApplicationType.choices
            }:
                return _workspace_error("Invalid registration application type.")
            applications = applications.filter(application_type=application_type)
        if club_value:
            club = _get_workspace_club(workspace, club_value)
            if club is None:
                return _workspace_error("Club not found.", status.HTTP_404_NOT_FOUND)
            applications = applications.filter(club=club)
        if query:
            applications = applications.filter(
                models.Q(applicant_name__icontains=query)
                | models.Q(registration_number__icontains=query)
                | models.Q(club__name__icontains=query)
            )
        return Response(
            {
                "count": applications.count(),
                "results": UnionRegistrationApplicationSerializer(
                    applications, many=True
                ).data,
            }
        )

    applicant_name = str(request.data.get("applicant_name") or "").strip()
    if not applicant_name:
        return _workspace_error("Applicant name is required.")
    club = _get_workspace_club(workspace, request.data.get("club"))
    if club is None:
        return _workspace_error("A valid workspace club is required.")
    application_type, choice_error = _validate_choice(
        request.data.get("application_type"),
        UnionRegistrationApplication.ApplicationType.choices,
        "registration application type",
        UnionRegistrationApplication.ApplicationType.NEW_PLAYER,
    )
    if choice_error:
        return choice_error

    team = None
    if request.data.get("team") not in (None, ""):
        team = _get_workspace_team(workspace, request.data.get("team"))
        if team is None or team.club_id != club.id:
            return _workspace_error("The selected team does not belong to the club.")
    competition = None
    if request.data.get("competition") not in (None, ""):
        competition = _get_workspace_competition(
            workspace, request.data.get("competition")
        )
        if competition is None:
            return _workspace_error(
                "The selected competition is not in this workspace."
            )
    player_registration = None
    if request.data.get("player_registration") not in (None, ""):
        player_registration = _get_workspace_player_registration(
            workspace, request.data.get("player_registration")
        )
        if player_registration is None or player_registration.club_id != club.id:
            return _workspace_error(
                "The selected player registration does not belong to the club."
            )
        if team and player_registration.team_id != team.id:
            return _workspace_error(
                "The selected player registration does not belong to the team."
            )

    application = UnionRegistrationApplication.objects.create(
        workspace=workspace,
        application_type=application_type,
        club=club,
        team=team,
        competition=competition,
        player_registration=player_registration,
        applicant_name=applicant_name,
        registration_number=(
            str(request.data.get("registration_number") or "").strip()
            or (
                player_registration.registration_number
                if player_registration is not None
                else ""
            )
        ),
        status=UnionRegistrationApplication.Status.PENDING,
        documents_complete=_parse_boolean(
            request.data.get("documents_complete"), False
        ),
        submitted_by=request.user,
        reviewer_notes=str(request.data.get("reviewer_notes") or "").strip(),
        metadata=(
            request.data.get("metadata")
            if isinstance(request.data.get("metadata"), dict)
            else {}
        ),
    )
    log_governance_action(
        actor=request.user,
        action="union_registration_application_created",
        details={"workspace": workspace.slug, "application": application.id},
    )
    return Response(
        UnionRegistrationApplicationSerializer(application).data,
        status=status.HTTP_201_CREATED,
    )


_REGISTRATION_STATUS_TRANSITIONS = {
    UnionRegistrationApplication.Status.PENDING: {
        UnionRegistrationApplication.Status.PENDING,
        UnionRegistrationApplication.Status.UNDER_REVIEW,
        UnionRegistrationApplication.Status.DOCUMENTS_REQUIRED,
        UnionRegistrationApplication.Status.APPROVED,
        UnionRegistrationApplication.Status.REJECTED,
        UnionRegistrationApplication.Status.WITHDRAWN,
    },
    UnionRegistrationApplication.Status.UNDER_REVIEW: {
        UnionRegistrationApplication.Status.UNDER_REVIEW,
        UnionRegistrationApplication.Status.DOCUMENTS_REQUIRED,
        UnionRegistrationApplication.Status.APPROVED,
        UnionRegistrationApplication.Status.REJECTED,
        UnionRegistrationApplication.Status.WITHDRAWN,
    },
    UnionRegistrationApplication.Status.DOCUMENTS_REQUIRED: {
        UnionRegistrationApplication.Status.PENDING,
        UnionRegistrationApplication.Status.UNDER_REVIEW,
        UnionRegistrationApplication.Status.DOCUMENTS_REQUIRED,
        UnionRegistrationApplication.Status.APPROVED,
        UnionRegistrationApplication.Status.REJECTED,
        UnionRegistrationApplication.Status.WITHDRAWN,
    },
    UnionRegistrationApplication.Status.APPROVED: {
        UnionRegistrationApplication.Status.APPROVED,
    },
    UnionRegistrationApplication.Status.REJECTED: {
        UnionRegistrationApplication.Status.REJECTED,
    },
    UnionRegistrationApplication.Status.WITHDRAWN: {
        UnionRegistrationApplication.Status.WITHDRAWN,
        UnionRegistrationApplication.Status.PENDING,
    },
}


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_registration_application_detail_view(request, application_id):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    permission_error = _require_permission(
        request.user, workspace, "union.players.approve"
    )
    if permission_error:
        return permission_error

    application = (
        UnionRegistrationApplication.objects.filter(
            workspace=workspace, id=application_id
        )
        .select_related(
            "workspace",
            "club",
            "team",
            "competition",
            "player_registration",
            "submitted_by",
            "reviewed_by",
        )
        .first()
    )
    if application is None:
        return _workspace_error(
            "Registration application not found.", status.HTTP_404_NOT_FOUND
        )
    if request.method == "GET":
        return Response(UnionRegistrationApplicationSerializer(application).data)

    if "documents_complete" in request.data:
        application.documents_complete = _parse_boolean(
            request.data.get("documents_complete"), application.documents_complete
        )
    if "reviewer_notes" in request.data:
        application.reviewer_notes = str(
            request.data.get("reviewer_notes") or ""
        ).strip()
    if "metadata" in request.data:
        if not isinstance(request.data.get("metadata"), dict):
            return _workspace_error("Registration metadata must be an object.")
        application.metadata = request.data.get("metadata")

    if "status" in request.data:
        new_status, choice_error = _validate_choice(
            request.data.get("status"),
            UnionRegistrationApplication.Status.choices,
            "registration status",
        )
        if choice_error:
            return choice_error
        allowed = _REGISTRATION_STATUS_TRANSITIONS.get(application.status, set())
        if new_status not in allowed:
            return _workspace_error(
                "Cannot change registration status from "
                f"{application.status} to {new_status}."
            )
        if (
            new_status == UnionRegistrationApplication.Status.APPROVED
            and not application.documents_complete
        ):
            return _workspace_error(
                "Complete the required documents before approving this application."
            )
        if (
            new_status == UnionRegistrationApplication.Status.REJECTED
            and not application.reviewer_notes
        ):
            return _workspace_error(
                "Reviewer notes are required when rejecting an application."
            )

        application.status = new_status
        if new_status in {
            UnionRegistrationApplication.Status.APPROVED,
            UnionRegistrationApplication.Status.REJECTED,
            UnionRegistrationApplication.Status.DOCUMENTS_REQUIRED,
        }:
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
        elif new_status in {
            UnionRegistrationApplication.Status.PENDING,
            UnionRegistrationApplication.Status.UNDER_REVIEW,
        }:
            application.reviewed_by = None
            application.reviewed_at = None

    application.save()
    log_governance_action(
        actor=request.user,
        action="union_registration_application_updated",
        details={
            "workspace": workspace.slug,
            "application": application.id,
            "status": application.status,
        },
    )
    return Response(UnionRegistrationApplicationSerializer(application).data)


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_official_readiness_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    permission_error = _require_permission(
        request.user, workspace, "union.official.appointments.view"
    )
    if permission_error:
        return permission_error

    officials = UnionMatchOfficial.objects.filter(
        union=workspace.related_union
    ).select_related("union", "user")
    upcoming_matches = (
        Match.objects.filter(
            competition__league__union=workspace.related_union,
            match_date__gte=timezone.now(),
            status__in=[Match.Status.SCHEDULED, Match.Status.POSTPONED],
        )
        .select_related("competition", "home_club", "away_club")
        .prefetch_related("official_assignments")
        .order_by("match_date")
    )

    fixture_rows = []
    fixtures_without_assignments = 0
    fixtures_with_pending_responses = 0
    for match in upcoming_matches:
        assignments = list(match.official_assignments.all())
        accepted_count = sum(
            assignment.status == FixtureOfficialAssignment.Status.ACCEPTED
            for assignment in assignments
        )
        pending_count = sum(
            assignment.status
            in {
                FixtureOfficialAssignment.Status.PROPOSED,
                FixtureOfficialAssignment.Status.ASSIGNED,
            }
            for assignment in assignments
        )
        declined_count = sum(
            assignment.status == FixtureOfficialAssignment.Status.DECLINED
            for assignment in assignments
        )
        if not assignments:
            readiness = "NO_ASSIGNMENTS"
            fixtures_without_assignments += 1
        elif pending_count:
            readiness = "PENDING_RESPONSES"
            fixtures_with_pending_responses += 1
        elif accepted_count:
            readiness = "HAS_ACCEPTED_ASSIGNMENTS"
        else:
            readiness = "REVIEW_REQUIRED"

        fixture_rows.append(
            {
                "id": match.id,
                "match": f"{match.home_club.name} vs {match.away_club.name}",
                "competition": match.competition.name,
                "match_date": match.match_date,
                "venue": match.venue,
                "assignment_count": len(assignments),
                "accepted_count": accepted_count,
                "pending_response_count": pending_count,
                "declined_count": declined_count,
                "readiness": readiness,
            }
        )

    return Response(
        {
            "workspace": {
                "slug": workspace.slug,
                "acronym": workspace.acronym,
                "name": workspace.name,
            },
            "summary": {
                "officials_total": officials.count(),
                "officials_available": officials.filter(
                    status=UnionMatchOfficial.Status.AVAILABLE
                ).count(),
                "officials_unavailable": officials.filter(
                    status=UnionMatchOfficial.Status.UNAVAILABLE
                ).count(),
                "officials_suspended": officials.filter(
                    status=UnionMatchOfficial.Status.SUSPENDED
                ).count(),
                "upcoming_fixtures": upcoming_matches.count(),
                "fixtures_without_assignments": fixtures_without_assignments,
                "fixtures_with_pending_responses": fixtures_with_pending_responses,
            },
            "fixtures": fixture_rows,
            "officials": UnionMatchOfficialManagementSerializer(
                officials, many=True
            ).data,
        }
    )
