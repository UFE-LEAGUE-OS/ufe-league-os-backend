from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Count, Prefetch
from django.utils.text import slugify
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import Club, ClubAdminScope
from accounts.permissions import IsAuthenticatedAudit

from .models import ClubAffiliation, League, LeagueClubMembership, Season
from .union_account_provisioning import provision_or_attach_user
from .union_club_serializers import (
    ClubAdministratorSerializer,
    ClubAdministratorWriteSerializer,
    ClubCreationSerializer,
    ClubUpdateSerializer,
    GovernanceClubSerializer,
)
from .union_governance import log_union_audit_event
from .union_management_views import _has_workspace_permission, _resolve_membership


def _denied():
    return Response(
        {"detail": "You do not have permission to perform this workspace action."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _normalize_sport(value):
    return str(value or "").strip().upper().replace(" ", "_")


def _validate_workspace_sport(workspace, submitted):
    workspace_sport = _normalize_sport(workspace.sport)
    selected = _normalize_sport(submitted)
    supported = {Club.Sport.FOOTBALL, Club.Sport.RUGBY, Club.Sport.BASKETBALL}
    if workspace_sport == Club.Sport.MULTI_SPORT:
        if selected not in supported:
            raise serializers.ValidationError(
                {"sport": "Select a supported workspace sport."}
            )
        return selected
    if selected and selected != workspace_sport:
        raise serializers.ValidationError(
            {"sport": "Sport must match the active workspace."}
        )
    return workspace_sport


def _club_queryset(workspace):
    affiliations = ClubAffiliation.objects.filter(workspace=workspace)
    memberships = LeagueClubMembership.objects.filter(
        league__union=workspace.related_union
    ).select_related("league", "season")
    scopes = ClubAdminScope.objects.select_related("user").order_by("-is_active", "id")
    return (
        Club.objects.filter(
            models.Q(union_affiliations__workspace=workspace)
            | models.Q(league_memberships__league__union=workspace.related_union)
            | models.Q(home_matches__competition__league__union=workspace.related_union)
            | models.Q(away_matches__competition__league__union=workspace.related_union)
            | models.Q(standings__competition__league__union=workspace.related_union)
        )
        .distinct()
        .annotate(
            teams_count=Count("teams", distinct=True),
            players_count=Count("player_registrations", distinct=True),
        )
        .prefetch_related(
            Prefetch(
                "union_affiliations",
                queryset=affiliations,
                to_attr="workspace_affiliations",
            ),
            Prefetch(
                "league_memberships",
                queryset=memberships,
                to_attr="workspace_memberships",
            ),
            Prefetch("clubadminscope_set", queryset=scopes, to_attr="club_scopes"),
        )
        .order_by("name")
    )


def _decorate_affiliation(clubs):
    for club in clubs:
        affiliation = (
            club.workspace_affiliations[0] if club.workspace_affiliations else None
        )
        club.affiliation_status = affiliation.status if affiliation else "LEGACY_LINK"
        club.compliance_status = (
            affiliation.compliance_status if affiliation else "NOT_RECORDED"
        )
        club.compliance_notes = affiliation.compliance_notes if affiliation else ""
    return clubs


def _unique_slug(name):
    base = slugify(name)[:140] or "club"
    candidate = base
    suffix = 2
    while Club.objects.filter(slug=candidate).exists():
        candidate = f"{base[:135]}-{suffix}"
        suffix += 1
    return candidate


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_clubs_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    permission = "union.clubs.view" if request.method == "GET" else "union.clubs.manage"
    if not _has_workspace_permission(request.user, workspace, permission):
        return _denied()
    if request.method == "GET":
        clubs = _club_queryset(workspace)
        search = (request.query_params.get("q") or "").strip()
        if search:
            clubs = clubs.filter(
                models.Q(name__icontains=search)
                | models.Q(short_name__icontains=search)
            )
        affiliation_status = request.query_params.get("affiliation_status")
        if affiliation_status:
            clubs = clubs.filter(
                union_affiliations__workspace=workspace,
                union_affiliations__status=affiliation_status,
            )
        rows = _decorate_affiliation(list(clubs))
        return Response(
            {
                "count": len(rows),
                "results": GovernanceClubSerializer(
                    rows, many=True, context={"request": request}
                ).data,
            }
        )

    payload = request.data.copy()
    payload.pop("workspace", None)
    serializer = ClubCreationSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    sport = _validate_workspace_sport(workspace, data.get("sport"))
    membership_data = data.pop("league_membership", None)
    affiliation_data = data.pop("affiliation")
    administrator_data = data.pop("administrator")
    league = season = None
    if membership_data:
        league = League.objects.filter(
            pk=membership_data["league"], union=workspace.related_union
        ).first()
        if league is None:
            raise serializers.ValidationError(
                {"league_membership": {"league": "League is outside this workspace."}}
            )
        if membership_data.get("season"):
            season = Season.objects.filter(
                pk=membership_data["season"], league=league
            ).first()
            if season is None:
                raise serializers.ValidationError(
                    {
                        "league_membership": {
                            "season": "Season does not belong to the selected League."
                        }
                    }
                )
    try:
        with transaction.atomic():
            club = Club.objects.create(
                slug=_unique_slug(data["name"]),
                sport=sport,
                **{key: value for key, value in data.items() if key != "sport"},
            )
            affiliation = ClubAffiliation.objects.create(
                workspace=workspace, club=club, **affiliation_data
            )
            league_membership = None
            if membership_data:
                league_membership = LeagueClubMembership.objects.create(
                    league=league,
                    club=club,
                    season=season,
                    status=membership_data["status"],
                    notes=membership_data.get("notes", ""),
                    created_by=request.user,
                )
            user, created_user, temporary_password = provision_or_attach_user(
                account=administrator_data["account"]
            )
            scope = ClubAdminScope.objects.create(
                user=user, club=club, role=administrator_data["role"], is_active=True
            )
            club.admin = user
            club.save(update_fields=["admin", "updated_at"])
            log_union_audit_event(
                workspace=workspace,
                actor=request.user,
                action="club.created",
                target=club,
                metadata={
                    "affiliation_id": affiliation.id,
                    "membership_id": (
                        league_membership.id if league_membership else None
                    ),
                    "administrator_scope_id": scope.id,
                    "created_user": created_user,
                },
            )
    except (ValidationError, IntegrityError) as exc:
        detail = getattr(exc, "message_dict", None) or {
            "detail": "The Club could not be created with the supplied data."
        }
        raise serializers.ValidationError(detail) from exc
    created = _decorate_affiliation(list(_club_queryset(workspace).filter(pk=club.pk)))[
        0
    ]
    response = {
        "club": GovernanceClubSerializer(created, context={"request": request}).data,
        "affiliation": {
            "id": affiliation.id,
            "status": affiliation.status,
            "compliance_status": affiliation.compliance_status,
            "compliance_notes": affiliation.compliance_notes,
        },
        "league_membership": (
            {
                "id": league_membership.id,
                "league": league_membership.league_id,
                "season": league_membership.season_id,
                "status": league_membership.status,
            }
            if league_membership
            else None
        ),
        "administrator_scope": ClubAdministratorSerializer(scope).data,
        "account": {"created_user": created_user},
    }
    if created_user:
        response["temporary_password"] = temporary_password
    return Response(response, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_club_detail_view(request, club_id):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    rows = _decorate_affiliation(list(_club_queryset(workspace).filter(pk=club_id)))
    if not rows:
        return Response({"detail": "Club not found."}, status=status.HTTP_404_NOT_FOUND)
    club = rows[0]
    permission = "union.clubs.view" if request.method == "GET" else "union.clubs.manage"
    if not _has_workspace_permission(request.user, workspace, permission):
        return _denied()
    if request.method == "GET":
        return Response(
            GovernanceClubSerializer(club, context={"request": request}).data
        )
    payload = request.data.copy()
    payload.pop("workspace", None)
    serializer = ClubUpdateSerializer(club, data=payload, partial=True)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if "sport" in data:
        data["sport"] = _validate_workspace_sport(workspace, data["sport"])
    affiliation_updates = {
        key: data.pop(key)
        for key in ("affiliation_status", "compliance_status", "compliance_notes")
        if key in data
    }
    with transaction.atomic():
        club = serializer.update(club, data)
        affiliation, _ = ClubAffiliation.objects.get_or_create(
            workspace=workspace, club=club
        )
        for key, value in affiliation_updates.items():
            setattr(
                affiliation, "status" if key == "affiliation_status" else key, value
            )
        if affiliation_updates:
            affiliation.save()
        log_union_audit_event(
            workspace=workspace,
            actor=request.user,
            action="club.updated",
            target=club,
            metadata={"affiliation_updated": bool(affiliation_updates)},
        )
    updated = _decorate_affiliation(list(_club_queryset(workspace).filter(pk=club.pk)))[
        0
    ]
    return Response(
        GovernanceClubSerializer(updated, context={"request": request}).data
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_club_administrators_view(request, club_id):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    if not _club_queryset(workspace).filter(pk=club_id).exists():
        return Response({"detail": "Club not found."}, status=status.HTTP_404_NOT_FOUND)
    permission = "union.clubs.view" if request.method == "GET" else "union.clubs.manage"
    if not _has_workspace_permission(request.user, workspace, permission):
        return _denied()
    scopes = ClubAdminScope.objects.filter(club_id=club_id).select_related("user")
    if request.method == "GET":
        return Response(
            {
                "count": scopes.count(),
                "results": ClubAdministratorSerializer(scopes, many=True).data,
            }
        )
    payload = request.data.copy()
    payload.pop("workspace", None)
    serializer = ClubAdministratorWriteSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        user, created_user, temporary_password = provision_or_attach_user(
            account=serializer.validated_data["account"]
        )
        scope, created_scope = ClubAdminScope.objects.update_or_create(
            user=user,
            club_id=club_id,
            defaults={"role": serializer.validated_data["role"], "is_active": True},
        )
    response = {
        "created_user": created_user,
        "created_scope": created_scope,
        "administrator": ClubAdministratorSerializer(scope).data,
    }
    if created_user:
        response["temporary_password"] = temporary_password
    return Response(
        response,
        status=status.HTTP_201_CREATED if created_scope else status.HTTP_200_OK,
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_club_administrator_detail_view(request, club_id, scope_id):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    if not _has_workspace_permission(request.user, workspace, "union.clubs.manage"):
        return _denied()
    scope = (
        ClubAdminScope.objects.filter(
            pk=scope_id, club_id=club_id, club__union_affiliations__workspace=workspace
        )
        .select_related("user")
        .first()
    )
    if scope is None:
        return Response(
            {"detail": "Administrator scope not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    unknown = set(request.data) - {"workspace", "role", "is_active", "make_primary"}
    if unknown:
        return Response(
            {key: "This field is not supported." for key in unknown},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if "role" in request.data:
        if request.data["role"] not in {
            value for value, _ in ClubAdminScope.Role.choices
        }:
            return Response(
                {"role": "Invalid Club administrator role."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        scope.role = request.data["role"]
    if "is_active" in request.data:
        scope.is_active = bool(request.data["is_active"])
    scope.save()
    if request.data.get("make_primary"):
        scope.club.admin = scope.user
        scope.club.save(update_fields=["admin", "updated_at"])
    return Response(ClubAdministratorSerializer(scope).data)
