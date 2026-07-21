"""Union-admin APIs for permanent competitions and season editions."""

from django.core.exceptions import ValidationError
from django.db.models import Count
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsAuthenticatedAudit

from .models import CompetitionEdition, CompetitionIdentity, Season
from .union_competition_serializers import (
    CompetitionEditionSerializer,
    CompetitionIdentitySerializer,
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
    serializer = CompetitionIdentitySerializer(data=request.data)
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
