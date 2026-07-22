"""Scoped Union APIs for maintained player-transfer review and decisions."""

from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError as APIValidationError
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAuthenticatedAudit

from .models import (
    UnionPlayerCompetitionEligibility,
    UnionPlayerTransfer,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
from .union_management_views import _has_workspace_permission, _resolve_membership
from .union_player_transfer_review_services import (
    approve_player_transfer_decision,
    reject_player_transfer,
    request_player_transfer_changes,
)
from .union_player_transfer_serializers import (
    UnionPlayerTransferDecisionResultSerializer,
    UnionPlayerTransferDecisionSerializer,
    UnionPlayerTransferDetailSerializer,
    UnionPlayerTransferListSerializer,
    UnionPlayerTransferOfflineConsentSerializer,
    UnionPlayerTransferOfflineDeclineSerializer,
)
from .union_player_transfer_services import (
    decline_player_transfer_consent,
    record_player_transfer_consent,
)
from .union_scopes import scope_allows


def _error(message, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"detail": message}, status=status_code)


def _is_super_admin(user):
    return bool(
        getattr(user, "is_superuser", False)
        or getattr(user, "role", None) == User.Role.SUPER_ADMIN
    )


def _resolve_transfer_membership(request):
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


def _eligibility_scope_queryset():
    return UnionPlayerCompetitionEligibility.objects.select_related(
        "competition_identity",
        "competition_edition",
        "competition_edition__competition",
        "season",
        "club",
        "team",
        "registration",
    ).order_by("competition_edition_id", "id")


def _transfer_queryset():
    return UnionPlayerTransfer.objects.select_related(
        "workspace",
        "workspace__related_union",
        "player",
        "player__user",
        "source_registration",
        "source_registration__club",
        "source_registration__team",
        "source_registration__season",
        "destination_club",
        "destination_team",
        "destination_registration",
        "destination_registration__club",
        "destination_registration__team",
        "destination_registration__season",
        "return_registration",
        "return_registration__club",
        "return_registration__team",
        "return_registration__season",
        "initiated_by",
        "source_club_responded_by",
        "player_consent_recorded_by",
        "reviewed_by",
        "cancelled_by",
    ).prefetch_related(
        Prefetch(
            "source_registration__competition_eligibilities",
            queryset=_eligibility_scope_queryset(),
            to_attr="_transfer_scope_eligibilities",
        ),
        Prefetch(
            "destination_competition_eligibilities",
            queryset=_eligibility_scope_queryset(),
            to_attr="_transfer_scope_destination_eligibilities",
        ),
        Prefetch(
            "return_competition_eligibilities",
            queryset=_eligibility_scope_queryset(),
            to_attr="_transfer_scope_return_eligibilities",
        ),
    )


def _related_eligibilities(transfer):
    source = getattr(
        transfer.source_registration,
        "_transfer_scope_eligibilities",
        None,
    )
    destination = getattr(
        transfer,
        "_transfer_scope_destination_eligibilities",
        None,
    )
    returned = getattr(
        transfer,
        "_transfer_scope_return_eligibilities",
        None,
    )
    if source is None or destination is None or returned is None:
        return list(
            _eligibility_scope_queryset()
            .filter(
                Q(registration_id=transfer.source_registration_id)
                | Q(source_transfer_id=transfer.id)
                | Q(source_loan_return_id=transfer.id)
            )
            .distinct()
        )
    by_id = {
        eligibility.id: eligibility
        for eligibility in [*source, *destination, *returned]
    }
    return [by_id[key] for key in sorted(by_id)]


def _transfer_in_scope(membership, transfer):
    if transfer.workspace_id != membership.workspace_id:
        return False
    if _is_super_admin(membership.user):
        return True
    if not scope_allows(
        membership,
        "club",
        transfer.source_registration.club_id,
    ) or not scope_allows(
        membership,
        "club",
        transfer.destination_club_id,
    ):
        return False
    return all(
        scope_allows(
            membership,
            "competition_identity",
            eligibility.competition_identity_id,
        )
        and scope_allows(
            membership,
            "competition_edition",
            eligibility.competition_edition_id,
        )
        for eligibility in _related_eligibilities(transfer)
    )


def _scoped_transfer_or_404(membership, transfer_id):
    transfer = get_object_or_404(
        _transfer_queryset(),
        pk=transfer_id,
        workspace=membership.workspace,
    )
    if transfer.status == UnionPlayerTransfer.Status.DRAFT or not _transfer_in_scope(
        membership, transfer
    ):
        raise Http404
    return transfer


def _fresh_transfer(transfer_id):
    return _transfer_queryset().get(pk=transfer_id)


def _validation_error_response(exc):
    try:
        data = dict(exc.message_dict)
    except AttributeError:
        data = {"detail": list(exc.messages)}
    for attribute in (
        "automatic_validation",
        "structured_validation",
        "validation",
    ):
        value = getattr(exc, attribute, None)
        if value is not None and attribute not in data:
            data[attribute] = value
    return Response(data, status=status.HTTP_400_BAD_REQUEST)


def _parse_date_filter(query_params, name):
    value = query_params.get(name)
    if not value:
        return None
    parsed = parse_date(value)
    if parsed is None:
        raise APIValidationError({name: "Use YYYY-MM-DD."})
    return parsed


def _filtered_transfer_queryset(request, membership):
    queryset = (
        _transfer_queryset()
        .filter(
            workspace=membership.workspace,
        )
        .exclude(status=UnionPlayerTransfer.Status.DRAFT)
    )

    statuses = request.query_params.getlist("status")
    if statuses:
        supported = set(UnionPlayerTransfer.Status.values)
        invalid = sorted(set(statuses) - supported)
        if invalid:
            raise APIValidationError(
                {"status": f"Unsupported status: {', '.join(invalid)}."}
            )
        statuses = [
            value for value in statuses if value != UnionPlayerTransfer.Status.DRAFT
        ]
        queryset = queryset.filter(status__in=statuses)

    exact_filters = {
        "player": "player_id",
        "source_registration": "source_registration_id",
        "destination_registration": "destination_registration_id",
        "return_registration": "return_registration_id",
        "source_club": "source_registration__club_id",
        "destination_club": "destination_club_id",
        "destination_team": "destination_team_id",
        "transfer_type": "transfer_type",
        "source_response_status": "source_club_response_status",
        "player_consent_status": "player_consent_status",
        "initiated_by": "initiated_by_id",
        "reviewed_by": "reviewed_by_id",
    }
    for parameter, field_name in exact_filters.items():
        value = request.query_params.get(parameter)
        if value:
            try:
                queryset = queryset.filter(**{field_name: value})
            except (TypeError, ValueError) as exc:
                raise APIValidationError({parameter: "Invalid filter value."}) from exc

    date_filters = {
        "effective_from": "effective_on__gte",
        "effective_to": "effective_on__lte",
        "loan_end_from": "loan_end_on__gte",
        "loan_end_to": "loan_end_on__lte",
        "submitted_from": "submitted_at__date__gte",
        "submitted_to": "submitted_at__date__lte",
        "created_from": "created_at__date__gte",
        "created_to": "created_at__date__lte",
    }
    for parameter, field_name in date_filters.items():
        value = _parse_date_filter(request.query_params, parameter)
        if value is not None:
            queryset = queryset.filter(**{field_name: value})

    search = request.query_params.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(player__union_player_number__icontains=search)
            | Q(player__first_name__icontains=search)
            | Q(player__last_name__icontains=search)
            | Q(source_registration__club__name__icontains=search)
            | Q(destination_club__name__icontains=search)
        )

    ordering_map = {
        "created_at": ("created_at", "id"),
        "-created_at": ("-created_at", "-id"),
        "updated_at": ("updated_at", "id"),
        "-updated_at": ("-updated_at", "-id"),
        "submitted_at": ("submitted_at", "id"),
        "-submitted_at": ("-submitted_at", "-id"),
        "reviewed_at": ("reviewed_at", "id"),
        "-reviewed_at": ("-reviewed_at", "-id"),
        "effective_on": ("effective_on", "id"),
        "-effective_on": ("-effective_on", "-id"),
        "loan_end_on": ("loan_end_on", "id"),
        "-loan_end_on": ("-loan_end_on", "-id"),
        "player_name": ("player__last_name", "player__first_name", "id"),
        "-player_name": ("-player__last_name", "-player__first_name", "-id"),
        "source_club_name": ("source_registration__club__name", "id"),
        "-source_club_name": ("-source_registration__club__name", "-id"),
        "destination_club_name": ("destination_club__name", "id"),
        "-destination_club_name": ("-destination_club__name", "-id"),
    }
    ordering = ordering_map.get(
        request.query_params.get("ordering"),
        ordering_map["-submitted_at"],
    )
    return queryset.order_by(*ordering)


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_player_transfers_view(request):
    membership, error = _resolve_transfer_membership(request)
    if error:
        return error
    permission_error = _require_permission(
        request,
        membership,
        "union.transfers.view",
    )
    if permission_error:
        return permission_error
    scoped = [
        transfer
        for transfer in _filtered_transfer_queryset(request, membership)
        if _transfer_in_scope(membership, transfer)
    ]
    return Response(
        {
            "count": len(scoped),
            "results": UnionPlayerTransferListSerializer(scoped, many=True).data,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_player_transfer_detail_view(request, transfer_id):
    membership, error = _resolve_transfer_membership(request)
    if error:
        return error
    permission_error = _require_permission(
        request,
        membership,
        "union.transfers.view",
    )
    if permission_error:
        return permission_error
    transfer = _scoped_transfer_or_404(membership, transfer_id)
    return Response(UnionPlayerTransferDetailSerializer(transfer).data)


def _action_context(request, transfer_id):
    membership, error = _resolve_transfer_membership(request)
    if error:
        return None, None, error
    permission_error = _require_permission(
        request,
        membership,
        "union.transfers.approve",
    )
    if permission_error:
        return None, None, permission_error
    try:
        transfer = _scoped_transfer_or_404(membership, transfer_id)
    except Http404:
        return (
            None,
            None,
            _error("Player transfer not found.", status.HTTP_404_NOT_FOUND),
        )
    return membership, transfer, None


def _updated_transfer_response(transfer_id):
    return Response(
        UnionPlayerTransferDetailSerializer(_fresh_transfer(transfer_id)).data
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_player_transfer_offline_consent_view(request, transfer_id):
    membership, transfer, error = _action_context(request, transfer_id)
    if error:
        return error
    serializer = UnionPlayerTransferOfflineConsentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        updated = record_player_transfer_consent(
            transfer_id=transfer.id,
            actor=request.user,
            consent_method=serializer.validated_data["consent_method"],
            membership=membership,
            evidence_reference=serializer.validated_data["evidence_reference"],
        )
    except UnionPlayerTransfer.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        return _validation_error_response(exc)
    return _updated_transfer_response(updated.id)


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_player_transfer_offline_decline_view(request, transfer_id):
    membership, transfer, error = _action_context(request, transfer_id)
    if error:
        return error
    serializer = UnionPlayerTransferOfflineDeclineSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        updated = decline_player_transfer_consent(
            transfer_id=transfer.id,
            actor=request.user,
            reason=serializer.validated_data["reason"],
            membership=membership,
            evidence_reference=serializer.validated_data["evidence_reference"],
        )
    except UnionPlayerTransfer.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        return _validation_error_response(exc)
    return _updated_transfer_response(updated.id)


def _decision_action(request, transfer_id, service):
    membership, transfer, error = _action_context(request, transfer_id)
    if error:
        return error
    serializer = UnionPlayerTransferDecisionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        return service(
            transfer_id=transfer.id,
            reviewer=request.user,
            membership=membership,
            reason=serializer.validated_data["reason"],
        )
    except UnionPlayerTransfer.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        return _validation_error_response(exc)


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_player_transfer_request_changes_view(request, transfer_id):
    result = _decision_action(
        request,
        transfer_id,
        request_player_transfer_changes,
    )
    if isinstance(result, Response):
        return result
    return _updated_transfer_response(result.id)


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_player_transfer_reject_view(request, transfer_id):
    result = _decision_action(request, transfer_id, reject_player_transfer)
    if isinstance(result, Response):
        return result
    return Response(
        {
            "transfer": UnionPlayerTransferDetailSerializer(
                _fresh_transfer(result["transfer"].id)
            ).data,
            "automatic_validation": result.get("automatic_validation"),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_player_transfer_approve_view(request, transfer_id):
    result = _decision_action(
        request,
        transfer_id,
        approve_player_transfer_decision,
    )
    if isinstance(result, Response):
        return result
    result = {
        **result,
        "transfer": _fresh_transfer(result["transfer"].id),
    }
    return Response(UnionPlayerTransferDecisionResultSerializer(result).data)
