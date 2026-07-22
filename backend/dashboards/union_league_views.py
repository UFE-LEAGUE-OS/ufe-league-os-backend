"""Union-admin governance options, League CRUD, and administrator scopes."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils.text import slugify
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import Club, ClubAdminScope
from accounts.permissions import IsAuthenticatedAudit

from .models import (
    ClubAffiliation,
    CompetitionIdentity,
    League,
    LeagueAdminScope,
    LeagueClubMembership,
)
from .union_account_provisioning import provision_or_attach_user
from .union_competition_serializers import CompetitionFormatSerializer
from .union_governance import log_union_audit_event
from .union_league_serializers import (
    LeagueAdministratorSerializer,
    LeagueAdministratorWriteSerializer,
    LeagueSerializer,
    LeagueWriteSerializer,
)
from .union_management_views import (
    _has_workspace_permission,
    _resolve_membership,
    _workspace_leagues,
)

SUPPORTED_SPORTS = (
    (Club.Sport.FOOTBALL, "Football"),
    (Club.Sport.RUGBY, "Rugby"),
    (Club.Sport.BASKETBALL, "Basketball"),
)

SPORT_VARIANTS = {
    Club.Sport.FOOTBALL: (("11_A_SIDE", "11-a-side"),),
    Club.Sport.RUGBY: (
        ("RUGBY_15S", "Rugby 15s"),
        ("RUGBY_10S", "Rugby 10s"),
        ("RUGBY_7S", "Rugby 7s"),
    ),
    Club.Sport.BASKETBALL: (("FIVE_A_SIDE", "5-a-side"),),
}

SPORT_FORMAT_TEMPLATES = {
    Club.Sport.FOOTBALL: (
        {
            "key": "DOUBLE_ROUND_ROBIN",
            "label": "Double round robin",
            "competition_types": ["LEAGUE"],
            "defaults": {
                "format": "DOUBLE_ROUND_ROBIN",
                "number_of_legs": 2,
                "home_and_away": True,
                "match_duration_minutes": 90,
                "points_for_win": 3,
                "points_for_draw": 1,
                "points_for_loss": 0,
                "gameweek_structure": "WEEKLY",
                "minimum_clubs": 2,
                "maximum_clubs": 40,
            },
        },
        {
            "key": "STRAIGHT_KNOCKOUT",
            "label": "Knockout",
            "competition_types": ["KNOCKOUT", "TOURNAMENT"],
            "defaults": {
                "format": "STRAIGHT_KNOCKOUT",
                "number_of_legs": 1,
                "home_and_away": False,
                "match_duration_minutes": 90,
                "points_for_win": 3,
                "points_for_draw": 1,
                "points_for_loss": 0,
                "gameweek_structure": "CUSTOM",
                "minimum_clubs": 2,
                "maximum_clubs": 128,
            },
        },
    ),
    Club.Sport.RUGBY: (
        {
            "key": "SINGLE_ROUND_ROBIN",
            "label": "League",
            "competition_types": ["LEAGUE", "SERIES"],
            "defaults": {
                "format": "SINGLE_ROUND_ROBIN",
                "number_of_legs": 1,
                "home_and_away": False,
                "match_duration_minutes": 80,
                "points_for_win": 4,
                "points_for_draw": 2,
                "points_for_loss": 0,
                "gameweek_structure": "WEEKLY",
                "minimum_clubs": 2,
                "maximum_clubs": 32,
            },
        },
        {
            "key": "GROUPS_AND_KNOCKOUT",
            "label": "Pools and knockout",
            "competition_types": ["GROUP_AND_KNOCKOUT", "TOURNAMENT"],
            "defaults": {
                "format": "GROUPS_AND_KNOCKOUT",
                "number_of_groups": 2,
                "clubs_per_group": 4,
                "advancing_per_group": 2,
                "home_and_away": False,
                "match_duration_minutes": 14,
                "points_for_win": 3,
                "points_for_draw": 2,
                "points_for_loss": 1,
                "gameweek_structure": "TOURNAMENT_DAYS",
                "minimum_clubs": 4,
                "maximum_clubs": 64,
            },
        },
    ),
    Club.Sport.BASKETBALL: (
        {
            "key": "LEAGUE_AND_PLAYOFFS",
            "label": "League and playoffs",
            "competition_types": ["LEAGUE", "TOURNAMENT"],
            "defaults": {
                "format": "LEAGUE_AND_PLAYOFFS",
                "number_of_legs": 2,
                "home_and_away": True,
                "match_duration_minutes": 40,
                "points_for_win": 2,
                "points_for_draw": 0,
                "points_for_loss": 1,
                "gameweek_structure": "WEEKLY",
                "minimum_clubs": 2,
                "maximum_clubs": 40,
            },
        },
    ),
}


def _choice_rows(choices):
    return [{"value": value, "label": label} for value, label in choices]


def _denied():
    return Response(
        {"detail": "You do not have permission to perform this workspace action."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _league_queryset(workspace):
    return (
        _workspace_leagues(workspace)
        .select_related("union", "union__workspace")
        .annotate(
            competitions_count=Count("competition_identities", distinct=True),
            clubs_count=Count("club_memberships__club", distinct=True),
            administrators_count=Count("admin_scopes", distinct=True),
        )
    )


def _league_for_workspace(workspace, league_id):
    return _league_queryset(workspace).filter(pk=league_id).first()


def _unique_league_slug(union, name):
    base = slugify(name)[:190] or "league"
    candidate = base
    suffix = 2
    while League.objects.filter(slug=candidate).exists():
        candidate = f"{base[:185]}-{suffix}"
        suffix += 1
    return candidate


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_governance_options_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    if not _has_workspace_permission(
        request.user, workspace, "union.competitions.view"
    ):
        return _denied()
    workspace_sport = (workspace.sport or "").strip().upper().replace(" ", "_")
    selectable_sports = (
        SUPPORTED_SPORTS
        if workspace_sport == Club.Sport.MULTI_SPORT
        else tuple(item for item in SUPPORTED_SPORTS if item[0] == workspace_sport)
    )
    template_sports = [item[0] for item in selectable_sports]
    return Response(
        {
            "workspace": {
                "slug": workspace.slug,
                "name": workspace.name,
                "sport": workspace_sport,
                "is_multi_sport": workspace_sport == Club.Sport.MULTI_SPORT,
            },
            "supported_sports": _choice_rows(selectable_sports),
            "competition_types": _choice_rows(
                CompetitionIdentity.CompetitionType.choices
            ),
            "competition_format_types": _choice_rows(
                (value, value.replace("_", " ").title())
                for value in CompetitionFormatSerializer.FORMAT_CHOICES
            ),
            "sport_variants": {
                sport: _choice_rows(SPORT_VARIANTS.get(sport, ()))
                for sport in template_sports
            },
            "format_templates": {
                sport: SPORT_FORMAT_TEMPLATES.get(sport, ())
                for sport in template_sports
            },
            "league_administrator_roles": _choice_rows(LeagueAdminScope.Role.choices),
            "competition_administrator_roles": _choice_rows(
                LeagueAdminScope.Role.choices
            ),
            "club_administrator_roles": _choice_rows(ClubAdminScope.Role.choices),
            "club_affiliation_statuses": _choice_rows(ClubAffiliation.Status.choices),
            "league_membership_statuses": _choice_rows(
                LeagueClubMembership.Status.choices
            ),
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_leagues_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    permission = (
        "union.competitions.view"
        if request.method == "GET"
        else "union.competitions.manage"
    )
    if not _has_workspace_permission(request.user, workspace, permission):
        return _denied()
    if request.method == "GET":
        leagues = _league_queryset(workspace)
        search = (request.query_params.get("search") or "").strip()
        if search:
            leagues = leagues.filter(name__icontains=search)
        return Response(
            {
                "count": leagues.count(),
                "results": LeagueSerializer(
                    leagues, many=True, context={"request": request}
                ).data,
            }
        )
    payload = request.data.copy()
    payload.pop("workspace", None)
    serializer = LeagueWriteSerializer(data=payload, context={"workspace": workspace})
    serializer.is_valid(raise_exception=True)
    league = serializer.save(
        union=workspace.related_union,
        slug=_unique_league_slug(
            workspace.related_union, serializer.validated_data["name"]
        ),
    )
    log_union_audit_event(
        workspace=workspace,
        actor=request.user,
        action="league.created",
        target=league,
        metadata={},
    )
    league = _league_for_workspace(workspace, league.pk)
    return Response(
        LeagueSerializer(league, context={"request": request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_league_detail_view(request, league_id):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    league = _league_for_workspace(workspace, league_id)
    if league is None:
        return Response(
            {"detail": "League not found."}, status=status.HTTP_404_NOT_FOUND
        )
    permission = (
        "union.competitions.view"
        if request.method == "GET"
        else "union.competitions.manage"
    )
    if not _has_workspace_permission(request.user, workspace, permission):
        return _denied()
    if request.method == "GET":
        return Response(LeagueSerializer(league, context={"request": request}).data)
    if request.method == "PATCH":
        payload = request.data.copy()
        payload.pop("workspace", None)
        serializer = LeagueWriteSerializer(
            league, data=payload, partial=True, context={"workspace": workspace}
        )
        serializer.is_valid(raise_exception=True)
        league = serializer.save()
        log_union_audit_event(
            workspace=workspace,
            actor=request.user,
            action="league.updated",
            target=league,
            metadata={},
        )
        return Response(
            LeagueSerializer(
                _league_for_workspace(workspace, league.pk),
                context={"request": request},
            ).data
        )
    history = {
        "competitions": league.competitions.exists()
        or league.competition_identities.exists(),
        "club_memberships": league.club_memberships.exists(),
        "administrator_scopes": league.admin_scopes.exists(),
    }
    if any(history.values()):
        return Response(
            {
                "detail": "This League has governance or competition history. Deactivate it instead of deleting it.",
                "blocking_records": [key for key, exists in history.items() if exists],
            },
            status=status.HTTP_409_CONFLICT,
        )
    log_union_audit_event(
        workspace=workspace,
        actor=request.user,
        action="league.deleted",
        target=league,
        metadata={"league_id": league.pk},
    )
    league.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_league_administrators_view(request, league_id):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    league = _league_for_workspace(workspace, league_id)
    if league is None:
        return Response(
            {"detail": "League not found."}, status=status.HTTP_404_NOT_FOUND
        )
    permission = (
        "union.competitions.view"
        if request.method == "GET"
        else "union.competitions.manage"
    )
    if not _has_workspace_permission(request.user, workspace, permission):
        return _denied()
    if request.method == "GET":
        scopes = LeagueAdminScope.objects.filter(league=league).select_related(
            "user", "competition"
        )
        return Response(
            {
                "count": scopes.count(),
                "results": LeagueAdministratorSerializer(scopes, many=True).data,
            }
        )
    payload = request.data.copy()
    payload.pop("workspace", None)
    serializer = LeagueAdministratorWriteSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    competition = serializer.validated_data.get("competition")
    if competition and competition.league_id != league.id:
        return Response(
            {"competition": "Competition is outside the selected League."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        with transaction.atomic():
            user, created_user, temporary_password = provision_or_attach_user(
                account=serializer.validated_data["account"]
            )
            lookup = {"user": user, "league": league, "competition": competition}
            scope, created_scope = LeagueAdminScope.objects.update_or_create(
                **lookup,
                defaults={
                    "role": serializer.validated_data["role"],
                    "is_active": True,
                    "created_by": request.user,
                },
            )
            log_union_audit_event(
                workspace=workspace,
                actor=request.user,
                action="league_administrator.assigned",
                target=scope,
                metadata={
                    "league_id": league.id,
                    "competition_id": competition.id if competition else None,
                    "role": scope.role,
                    "created_user": created_user,
                },
            )
    except (ValidationError, IntegrityError) as exc:
        detail = getattr(exc, "message_dict", None) or {
            "account": "The account could not be provisioned with the supplied details."
        }
        raise serializers.ValidationError(detail) from exc
    response = {
        "created_user": created_user,
        "created_scope": created_scope,
        "administrator": LeagueAdministratorSerializer(scope).data,
    }
    if created_user:
        response["temporary_password"] = temporary_password
    return Response(
        response,
        status=status.HTTP_201_CREATED if created_scope else status.HTTP_200_OK,
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_league_administrator_detail_view(request, league_id, scope_id):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    if not _has_workspace_permission(
        request.user, workspace, "union.competitions.manage"
    ):
        return _denied()
    scope = (
        LeagueAdminScope.objects.filter(
            pk=scope_id, league_id=league_id, league__union=workspace.related_union
        )
        .select_related("user", "competition")
        .first()
    )
    if scope is None:
        return Response(
            {"detail": "Administrator scope not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    allowed = {"role", "is_active"}
    unknown = set(request.data) - allowed - {"workspace"}
    if unknown:
        return Response(
            {key: "This field is not supported." for key in sorted(unknown)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if "role" in request.data:
        valid_roles = {choice[0] for choice in LeagueAdminScope.Role.choices}
        if request.data["role"] not in valid_roles:
            return Response(
                {"role": "Invalid administrator role."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        scope.role = request.data["role"]
    if "is_active" in request.data:
        if not isinstance(request.data["is_active"], bool):
            return Response(
                {"is_active": "A boolean value is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        scope.is_active = request.data["is_active"]
    scope.save(update_fields=["role", "is_active", "updated_at"])
    log_union_audit_event(
        workspace=workspace,
        actor=request.user,
        action="league_administrator.updated",
        target=scope,
        metadata={"role": scope.role, "is_active": scope.is_active},
    )
    return Response(LeagueAdministratorSerializer(scope).data)
