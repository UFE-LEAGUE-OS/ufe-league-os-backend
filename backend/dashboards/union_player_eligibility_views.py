"""Scoped Union APIs for competition-eligibility history and decisions."""

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsAuthenticatedAudit

from .models import (
    UnionPlayerCompetitionEligibility,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
from .union_management_views import _has_workspace_permission, _resolve_membership
from .union_player_eligibility_serializers import (
    UnionPlayerEligibilityActionResultSerializer,
    UnionPlayerEligibilityApproveSerializer,
    UnionPlayerEligibilityDecisionSerializer,
    UnionPlayerEligibilityDetailSerializer,
    UnionPlayerEligibilityListSerializer,
)
from .union_player_eligibility_services import (
    approve_player_competition_eligibility,
    cancel_player_competition_eligibility,
    expire_player_competition_eligibility,
    reinstate_player_competition_eligibility,
    reject_player_competition_eligibility,
    suspend_player_competition_eligibility,
)
from .union_scopes import scope_allows


def _error(message, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"detail": message}, status=status_code)


def _resolve_eligibility_membership(request):
    workspace_value = (
        request.query_params.get("workspace")
        if request.method == "GET"
        else request.data.get("workspace")
    )
    if not workspace_value:
        return None, _error("workspace is required.")
    if str(workspace_value).isdigit():
        membership = (
            UnionWorkspaceMembership.objects.filter(
                user=request.user,
                workspace_id=workspace_value,
                is_active=True,
                workspace__status=UnionWorkspace.Status.ACTIVE,
            )
            .select_related("workspace", "workspace__related_union")
            .first()
        )
        if membership is None:
            return None, _error(
                "No active union workspace access found for this user.",
                status.HTTP_403_FORBIDDEN,
            )
        if membership.workspace.related_union is None:
            return None, _error(
                "This workspace is not linked to a union/federation record."
            )
        return membership, None
    return _resolve_membership(request)


def _require_permission(request, membership, permission):
    if not _has_workspace_permission(
        request.user,
        membership.workspace,
        permission,
    ):
        return _error(
            "You do not have permission to perform this workspace action.",
            status.HTTP_403_FORBIDDEN,
        )
    return None


def _eligibility_queryset():
    return UnionPlayerCompetitionEligibility.objects.select_related(
        "workspace",
        "player",
        "club",
        "team",
        "registration",
        "registration__season",
        "source_submission",
        "competition_identity",
        "competition_edition",
        "competition_edition__identity",
        "competition_edition__competition",
        "competition_edition__season",
        "season",
        "reviewed_by",
    )


def _in_scope(membership, eligibility):
    return (
        scope_allows(membership, "club", eligibility.club_id)
        and scope_allows(
            membership,
            "competition_identity",
            eligibility.competition_identity_id,
        )
        and scope_allows(
            membership,
            "competition_edition",
            eligibility.competition_edition_id,
        )
    )


def _scoped_eligibility_or_none(membership, eligibility_id):
    eligibility = get_object_or_404(
        _eligibility_queryset(),
        pk=eligibility_id,
        workspace=membership.workspace,
    )
    return eligibility if _in_scope(membership, eligibility) else None


def _validation_error_response(exc):
    try:
        data = exc.message_dict
    except AttributeError:
        data = {"detail": exc.messages}
    automatic_validation = getattr(exc, "automatic_validation", None)
    if automatic_validation is not None:
        data["automatic_validation"] = automatic_validation
    return Response(data, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_player_eligibilities_view(request):
    membership, error = _resolve_eligibility_membership(request)
    if error:
        return error
    permission_error = _require_permission(
        request,
        membership,
        "union.players.view",
    )
    if permission_error:
        return permission_error

    queryset = _eligibility_queryset().filter(workspace=membership.workspace)
    statuses = request.query_params.getlist("status")
    if statuses:
        queryset = queryset.filter(status__in=statuses)
    for parameter, field_name in {
        "club": "club_id",
        "team": "team_id",
        "player": "player_id",
        "registration": "registration_id",
        "source_submission": "source_submission_id",
        "competition_identity": "competition_identity_id",
        "competition_edition": "competition_edition_id",
        "season": "season_id",
        "reviewed_by": "reviewed_by_id",
    }.items():
        value = request.query_params.get(parameter)
        if value:
            queryset = queryset.filter(**{field_name: value})

    created_from = parse_date(request.query_params.get("created_from", ""))
    created_to = parse_date(request.query_params.get("created_to", ""))
    if created_from:
        queryset = queryset.filter(created_at__date__gte=created_from)
    if created_to:
        queryset = queryset.filter(created_at__date__lte=created_to)

    search = request.query_params.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(player__union_player_number__icontains=search)
            | Q(player__first_name__icontains=search)
            | Q(player__last_name__icontains=search)
            | Q(club__name__icontains=search)
            | Q(competition_identity__name__icontains=search)
            | Q(competition_edition__competition__name__icontains=search)
            | Q(competition_edition__season__name__icontains=search)
        )

    ordering_map = {
        "created_at": ("created_at",),
        "-created_at": ("-created_at",),
        "updated_at": ("updated_at",),
        "-updated_at": ("-updated_at",),
        "reviewed_at": ("reviewed_at",),
        "-reviewed_at": ("-reviewed_at",),
        "eligible_from": ("eligible_from",),
        "-eligible_from": ("-eligible_from",),
        "player_name": ("player__first_name", "player__last_name"),
        "-player_name": ("-player__first_name", "-player__last_name"),
        "club_name": ("club__name",),
        "-club_name": ("-club__name",),
        "competition_name": ("competition_identity__name",),
        "-competition_name": ("-competition_identity__name",),
    }
    ordering = ordering_map.get(
        request.query_params.get("ordering"),
        ordering_map["-created_at"],
    )
    scoped = [
        eligibility
        for eligibility in queryset.order_by(*ordering, "id")
        if _in_scope(membership, eligibility)
    ]
    return Response(
        {
            "count": len(scoped),
            "results": UnionPlayerEligibilityListSerializer(
                scoped,
                many=True,
            ).data,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_player_eligibility_detail_view(request, eligibility_id):
    membership, error = _resolve_eligibility_membership(request)
    if error:
        return error
    permission_error = _require_permission(
        request,
        membership,
        "union.players.view",
    )
    if permission_error:
        return permission_error
    eligibility = _scoped_eligibility_or_none(membership, eligibility_id)
    if eligibility is None:
        return _error(
            "Player eligibility not found.",
            status.HTTP_404_NOT_FOUND,
        )
    return Response(UnionPlayerEligibilityDetailSerializer(eligibility).data)


def _action_context(request, eligibility_id):
    membership, error = _resolve_eligibility_membership(request)
    if error:
        return None, None, error
    permission_error = _require_permission(
        request,
        membership,
        "union.players.approve",
    )
    if permission_error:
        return None, None, permission_error
    eligibility = _scoped_eligibility_or_none(membership, eligibility_id)
    if eligibility is None:
        return (
            None,
            None,
            _error(
                "Player eligibility not found.",
                status.HTTP_404_NOT_FOUND,
            ),
        )
    return membership, eligibility, None


def _normalised_response(
    eligibility,
    *,
    automatic_validation=None,
    idempotent_replay=False,
):
    return Response(
        UnionPlayerEligibilityActionResultSerializer(
            {
                "eligibility": eligibility,
                "automatic_validation": automatic_validation,
                "idempotent_replay": idempotent_replay,
            }
        ).data
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_player_eligibility_approve_view(request, eligibility_id):
    membership, eligibility, error = _action_context(request, eligibility_id)
    if error:
        return error
    serializer = UnionPlayerEligibilityApproveSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        result = approve_player_competition_eligibility(
            eligibility_id=eligibility.id,
            reviewer=request.user,
            membership=membership,
            reason=serializer.validated_data["reason"],
            eligible_from=serializer.validated_data.get("eligible_from"),
            eligible_until=serializer.validated_data.get("eligible_until"),
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    return _normalised_response(
        result["eligibility"],
        automatic_validation=result["automatic_validation"],
        idempotent_replay=result["idempotent_replay"],
    )


def _decision_action(request, eligibility_id, service):
    membership, eligibility, error = _action_context(request, eligibility_id)
    if error:
        return error
    serializer = UnionPlayerEligibilityDecisionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        result = service(
            eligibility_id=eligibility.id,
            reviewer=request.user,
            membership=membership,
            reason=serializer.validated_data["reason"],
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    return _normalised_response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_player_eligibility_reject_view(request, eligibility_id):
    return _decision_action(
        request,
        eligibility_id,
        reject_player_competition_eligibility,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_player_eligibility_suspend_view(request, eligibility_id):
    return _decision_action(
        request,
        eligibility_id,
        suspend_player_competition_eligibility,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_player_eligibility_reinstate_view(request, eligibility_id):
    return _decision_action(
        request,
        eligibility_id,
        reinstate_player_competition_eligibility,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_player_eligibility_expire_view(request, eligibility_id):
    return _decision_action(
        request,
        eligibility_id,
        expire_player_competition_eligibility,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_player_eligibility_cancel_view(request, eligibility_id):
    return _decision_action(
        request,
        eligibility_id,
        cancel_player_competition_eligibility,
    )
