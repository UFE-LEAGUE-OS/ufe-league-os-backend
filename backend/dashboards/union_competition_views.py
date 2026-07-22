"""Union-admin APIs for permanent competitions and season editions."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsAuthenticatedAudit

from .models import (
    CompetitionEdition,
    CompetitionIdentity,
    LeagueAdminScope,
    Season,
    UnionWorkspaceMembership,
)
from .union_competition_serializers import (
    CompetitionEditionSerializer,
    CompetitionAdministratorSerializer,
    CompetitionAdministratorWriteSerializer,
    CompetitionCreationSerializer,
    CompetitionIdentitySerializer,
    CompetitionIdentityWriteSerializer,
)
from .union_competitions import (
    create_competition_edition,
    transition_competition_edition,
)
from .union_management_views import (
    _has_workspace_permission,
    _resolve_membership,
    _workspace_leagues,
)
from .union_scopes import scope_allows
from .union_governance import log_union_audit_event


def _denied():
    return Response(
        {"detail": "You do not have permission to perform this workspace action."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _identity_for_workspace(membership, identity_id):
    identity = CompetitionIdentity.objects.filter(
        pk=identity_id,
        union=membership.workspace.related_union,
    ).first()
    if identity and not scope_allows(membership, "competition_identity", identity.id):
        return None
    return identity


def _identity_slug(union, name):
    base = slugify(name)[:190] or "competition"
    slug = base
    suffix = 2
    while CompetitionIdentity.objects.filter(union=union, slug=slug).exists():
        slug = f"{base[:190 - len(str(suffix))]}-{suffix}"
        suffix += 1
    return slug


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_competition_identities_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    if not _has_workspace_permission(
        request.user, workspace, "union.competitions.view"
    ):
        return _denied()

    if request.method == "GET":
        identities = (
            CompetitionIdentity.objects.filter(union=workspace.related_union)
            .select_related("union", "primary_league")
            .annotate(editions_count=Count("editions"))
        )
        restrictions = membership.scope_restrictions or {}
        if "competition_identity_ids" in restrictions:
            identities = identities.filter(
                id__in=restrictions["competition_identity_ids"]
            )
        if request.query_params.get("is_active") in {"true", "false"}:
            identities = identities.filter(
                is_active=request.query_params["is_active"] == "true"
            )
        if search := request.query_params.get("search"):
            identities = identities.filter(name__icontains=search)
        return Response(
            {
                "count": identities.count(),
                "results": CompetitionIdentitySerializer(identities, many=True).data,
            }
        )

    if not _has_workspace_permission(
        request.user, workspace, "union.competitions.manage"
    ):
        return _denied()
    serializer = CompetitionIdentityWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    primary_league = serializer.validated_data.get("primary_league")
    if primary_league and primary_league not in _workspace_leagues(workspace):
        return Response(
            {"primary_league": "League is outside this workspace."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    identity = serializer.save(
        union=workspace.related_union,
        slug=_identity_slug(workspace.related_union, serializer.validated_data["name"]),
        sport=serializer.validated_data.get("sport") or workspace.sport,
    )
    return Response(
        CompetitionIdentitySerializer(identity).data, status=status.HTTP_201_CREATED
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_competition_editions_view(request, identity_id):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    if not _has_workspace_permission(
        request.user, workspace, "union.competitions.view"
    ):
        return _denied()
    identity = _identity_for_workspace(membership, identity_id)
    if identity is None:
        return Response(
            {"detail": "Competition identity not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        editions = CompetitionEdition.objects.filter(identity=identity).select_related(
            "competition", "season", "published_by"
        )
        return Response(
            {
                "count": editions.count(),
                "results": CompetitionEditionSerializer(editions, many=True).data,
            }
        )

    if not _has_workspace_permission(
        request.user, workspace, "union.competitions.manage"
    ):
        return _denied()
    season_id = request.data.get("season")
    season = Season.objects.filter(
        pk=season_id, league__union=workspace.related_union
    ).first()
    if season is None:
        return Response(
            {"season": "A workspace season is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    source_id = request.data.get("copied_from")
    source = (
        CompetitionEdition.objects.filter(pk=source_id, identity=identity)
        .select_related("competition", "season")
        .first()
        if source_id
        else None
    )
    if source_id and source is None:
        return Response(
            {"copied_from": "Source edition is outside this competition identity."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        edition = create_competition_edition(
            workspace=workspace,
            identity=identity,
            season=season,
            actor=request.user,
            copied_from=source,
            copy_fields=request.data.get("copy", []),
        )
    except ValidationError as exc:
        return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        CompetitionEditionSerializer(edition).data, status=status.HTTP_201_CREATED
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_competition_edition_transition_view(request, edition_id):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    edition = (
        CompetitionEdition.objects.filter(
            pk=edition_id,
            identity__union=workspace.related_union,
        )
        .select_related("competition", "identity")
        .first()
    )
    if edition is None:
        return Response(
            {"detail": "Competition edition not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not scope_allows(membership, "competition_edition", edition.id):
        return Response(
            {"detail": "Competition edition not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    target_status = request.data.get("status")
    permission = (
        "union.competitions.publish"
        if target_status == "PUBLISHED"
        else "union.competitions.manage"
    )
    if not _has_workspace_permission(request.user, workspace, permission):
        return _denied()
    try:
        edition = transition_competition_edition(
            edition=edition,
            target_status=target_status,
            actor=request.user,
            workspace=workspace,
            reason=str(request.data.get("reason") or ""),
        )
    except ValidationError as exc:
        return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
    return Response(CompetitionEditionSerializer(edition).data)


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_competition_eligible_administrators_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    if not _has_workspace_permission(request.user, workspace, "union.competitions.manage"):
        return _denied()
    memberships = UnionWorkspaceMembership.objects.filter(
        workspace=workspace, is_active=True, user__is_active=True
    ).select_related("user")
    search = (request.query_params.get("search") or "").strip()
    if search:
        memberships = memberships.filter(
            Q(user__email__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
        )
    return Response(
        {
            "count": memberships.count(),
            "results": [
                {
                    "id": item.user_id,
                    "email": item.user.email,
                    "name": item.user.get_full_name() or item.user.email,
                    "workspace_role": item.role,
                    "effective_permissions": item.effective_permissions,
                }
                for item in memberships
            ],
        }
    )


def _competition_for_workspace(membership, competition_id):
    return CompetitionEdition.objects.filter(
        competition_id=competition_id,
        identity__union=membership.workspace.related_union,
    ).select_related("competition__league", "identity").first()


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_competition_administrators_view(request, competition_id):
    membership, error = _resolve_membership(request)
    if error:
        return error
    edition = _competition_for_workspace(membership, competition_id)
    if edition is None or not scope_allows(membership, "competition_edition", edition.id):
        return Response({"detail": "Competition not found."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "GET":
        if not _has_workspace_permission(request.user, membership.workspace, "union.competitions.view"):
            return _denied()
        scopes = LeagueAdminScope.objects.filter(
            competition=edition.competition, is_active=True
        ).select_related("user")
        return Response({"count": scopes.count(), "results": CompetitionAdministratorSerializer(scopes, many=True).data})
    if not _has_workspace_permission(request.user, membership.workspace, "union.competitions.manage"):
        return _denied()
    serializer = CompetitionAdministratorWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    candidate = UnionWorkspaceMembership.objects.filter(
        workspace=membership.workspace,
        user_id=serializer.validated_data["user"],
        is_active=True,
        user__is_active=True,
    ).select_related("user").first()
    if candidate is None:
        return Response({"user": "Select an active user in this workspace."}, status=status.HTTP_400_BAD_REQUEST)
    scope, _ = LeagueAdminScope.objects.update_or_create(
        user=candidate.user,
        competition=edition.competition,
        defaults={"league": edition.competition.league, "role": serializer.validated_data["role"], "is_active": True, "created_by": request.user},
    )
    log_union_audit_event(workspace=membership.workspace, actor=request.user, action="competition_administrator.assigned", target=scope, metadata={"competition_id": competition_id, "role": scope.role})
    return Response(CompetitionAdministratorSerializer(scope).data, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_competition_administrator_detail_view(request, competition_id, scope_id):
    membership, error = _resolve_membership(request)
    if error:
        return error
    if not _has_workspace_permission(request.user, membership.workspace, "union.competitions.manage"):
        return _denied()
    scope = LeagueAdminScope.objects.filter(pk=scope_id, competition_id=competition_id, competition__league__union=membership.workspace.related_union, is_active=True).first()
    if scope is None:
        return Response({"detail": "Assignment not found."}, status=status.HTTP_404_NOT_FOUND)
    scope.is_active = False
    scope.save(update_fields=["is_active", "updated_at"])
    log_union_audit_event(workspace=membership.workspace, actor=request.user, action="competition_administrator.removed", target=scope, metadata={"competition_id": competition_id})
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_competition_create_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error
    workspace = membership.workspace
    if not _has_workspace_permission(request.user, workspace, "union.competitions.manage"):
        return _denied()
    serializer = CompetitionCreationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    identity_data = serializer.validated_data["identity"]
    league = identity_data.get("primary_league")
    if league not in _workspace_leagues(workspace):
        return Response({"identity": {"primary_league": "League is outside this workspace."}}, status=status.HTTP_400_BAD_REQUEST)
    season = Season.objects.filter(pk=serializer.validated_data["first_edition"]["season"], league__union=workspace.related_union).first()
    if season is None:
        return Response({"first_edition": {"season": "A workspace season is required."}}, status=status.HTTP_400_BAD_REQUEST)
    user_ids = [item["user"] for item in serializer.validated_data.get("administrators", [])]
    candidates = {item.user_id: item for item in UnionWorkspaceMembership.objects.filter(workspace=workspace, user_id__in=user_ids, is_active=True, user__is_active=True).select_related("user")}
    if len(candidates) != len(user_ids):
        return Response({"administrators": "Every administrator must be an active user in this workspace."}, status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        identity = CompetitionIdentity.objects.create(
            union=workspace.related_union,
            slug=_identity_slug(workspace.related_union, identity_data["name"]),
            **identity_data,
        )
        first = serializer.validated_data["first_edition"]
        edition = create_competition_edition(workspace=workspace, identity=identity, season=season, actor=request.user, registration_opens_at=first.get("registration_opens_at"), registration_closes_at=first.get("registration_closes_at"), entry_fee=first.get("entry_fee"), currency=first.get("currency", "UGX"), rules=first.get("rules"), eligibility_rules=first.get("eligibility_rules"), structure=identity.default_format)
        scopes = [LeagueAdminScope.objects.create(user=candidates[item["user"]].user, league=edition.competition.league, competition=edition.competition, role=item["role"], created_by=request.user) for item in serializer.validated_data.get("administrators", [])]
        for scope in scopes:
            log_union_audit_event(workspace=workspace, actor=request.user, action="competition_administrator.assigned", target=scope, metadata={"competition_id": edition.competition_id, "role": scope.role})
        log_union_audit_event(workspace=workspace, actor=request.user, action="competition_identity.created", target=identity, metadata={"edition_id": edition.id})
    return Response({"identity": CompetitionIdentitySerializer(identity).data, "edition": CompetitionEditionSerializer(edition).data, "administrators": CompetitionAdministratorSerializer(scopes, many=True).data}, status=status.HTTP_201_CREATED)
