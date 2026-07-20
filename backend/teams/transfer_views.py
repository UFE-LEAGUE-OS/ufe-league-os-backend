"""Secure Club APIs and read-only legacy compatibility for player transfers."""

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError as APIValidationError,
)
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAuthenticatedAudit
from accounts.rbac import get_user_clubs, has_role_permission
from dashboards.models import UnionPlayerTransfer
from dashboards.union_player_transfer_services import (
    cancel_player_transfer_request,
    create_player_transfer_draft,
    decline_player_transfer_consent,
    record_player_transfer_consent,
    record_source_club_transfer_response,
    resubmit_player_transfer,
    submit_player_transfer,
    update_player_transfer_draft,
)

from .models import PlayerTransfer
from .transfer_serializers import (
    ClubPlayerTransferCancelSerializer,
    ClubPlayerTransferDraftCreateSerializer,
    ClubPlayerTransferDraftUpdateSerializer,
    ClubPlayerTransferSourceResponseSerializer,
    ClubPlayerTransferSubmissionDetailSerializer,
    ClubPlayerTransferSubmissionListSerializer,
    LegacyPlayerTransferCompatibilityResultSerializer,
    LegacyPlayerTransferReadSerializer,
    LegacyPlayerTransferSummarySerializer,
    PlayerTransferDirectConsentSerializer,
    PlayerTransferDirectDeclineSerializer,
)

CLUB_TRANSFER_PERMISSION = "club.transfers.manage"


def _is_super_admin(user):
    return bool(
        getattr(user, "is_superuser", False)
        or getattr(user, "role", None) == User.Role.SUPER_ADMIN
    )


def _has_transfer_permission(user):
    return _is_super_admin(user) or has_role_permission(
        user,
        CLUB_TRANSFER_PERMISSION,
    )


def _managed_club_ids(user):
    return set(get_user_clubs(user).values_list("id", flat=True))


def _is_submitted(transfer):
    return bool(
        transfer.submitted_at is not None
        and transfer.status != UnionPlayerTransfer.Status.DRAFT
    )


def _transfer_queryset():
    return UnionPlayerTransfer.objects.select_related(
        "workspace",
        "player",
        "player__user",
        "source_registration",
        "source_registration__club",
        "source_registration__team",
        "destination_club",
        "destination_team",
        "destination_registration",
        "return_registration",
        "initiated_by",
        "source_club_responded_by",
        "player_consent_recorded_by",
        "reviewed_by",
        "cancelled_by",
    )


def _fresh_transfer(transfer_id):
    return _transfer_queryset().get(pk=transfer_id)


def _can_view_transfer(user, transfer):
    if _is_super_admin(user):
        return True
    managed_club_ids = _managed_club_ids(user)
    if (
        _has_transfer_permission(user)
        and transfer.destination_club_id in managed_club_ids
    ):
        return True
    if not _is_submitted(transfer):
        return False
    if (
        _has_transfer_permission(user)
        and transfer.source_registration.club_id in managed_club_ids
    ):
        return True
    return transfer.player.user_id == getattr(user, "pk", None)


def _visible_transfer_or_404(user, transfer_id):
    transfer = get_object_or_404(_transfer_queryset(), pk=transfer_id)
    if _can_view_transfer(user, transfer):
        return transfer
    managed_club_ids = _managed_club_ids(user)
    visibly_related_without_permission = (
        transfer.destination_club_id in managed_club_ids
        or (
            _is_submitted(transfer)
            and transfer.source_registration.club_id in managed_club_ids
        )
    )
    if visibly_related_without_permission and not _has_transfer_permission(user):
        raise PermissionDenied("Club transfer permission is required.")
    raise Http404


def _destination_transfer_or_404(user, transfer_id):
    transfer = get_object_or_404(_transfer_queryset(), pk=transfer_id)
    if not _is_super_admin(
        user
    ) and transfer.destination_club_id not in _managed_club_ids(user):
        raise Http404
    if not _has_transfer_permission(user):
        raise PermissionDenied("Club transfer permission is required.")
    return transfer


def _source_transfer_or_404(user, transfer_id):
    transfer = get_object_or_404(_transfer_queryset(), pk=transfer_id)
    if not _is_submitted(transfer):
        raise Http404
    if not _is_super_admin(
        user
    ) and transfer.source_registration.club_id not in _managed_club_ids(user):
        raise Http404
    if not _has_transfer_permission(user):
        raise PermissionDenied("Club transfer permission is required.")
    return transfer


def _player_transfer_or_404(user, transfer_id):
    transfer = get_object_or_404(_transfer_queryset(), pk=transfer_id)
    if not _is_submitted(transfer) or transfer.player.user_id != getattr(
        user, "pk", None
    ):
        raise Http404
    return transfer


def _validation_error_response(exc):
    try:
        data = exc.message_dict
    except AttributeError:
        data = {"detail": exc.messages}
    automatic_validation = getattr(exc, "automatic_validation", None)
    if automatic_validation is not None:
        data["automatic_validation"] = automatic_validation
    return Response(data, status=status.HTTP_400_BAD_REQUEST)


def _create_transfer_from_validated(actor, validated_data):
    return create_player_transfer_draft(
        actor=actor,
        workspace=validated_data["workspace"],
        source_registration=validated_data["source_registration"],
        destination_club=validated_data["destination_club"],
        destination_team=validated_data.get("destination_team"),
        effective_on=validated_data["effective_on"],
        transfer_type=validated_data["transfer_type"],
        loan_end_on=validated_data.get("loan_end_on"),
        documents=validated_data.get("documents", []),
        fee_status=validated_data.get("fee_status", ""),
    )


def _require_creation_permission(user, destination_club):
    if destination_club.id in _managed_club_ids(user) and not _has_transfer_permission(
        user
    ):
        raise PermissionDenied("Club transfer permission is required.")


def _parse_date_filter(query_params, name):
    value = query_params.get(name)
    if not value:
        return None
    parsed = parse_date(value)
    if parsed is None:
        raise APIValidationError({name: "Use YYYY-MM-DD."})
    return parsed


def _filtered_transfer_queryset(request):
    user = request.user
    rows = _transfer_queryset()
    if not _is_super_admin(user):
        managed_club_ids = _managed_club_ids(user)
        visibility = Q()
        if _has_transfer_permission(user):
            visibility |= Q(destination_club_id__in=managed_club_ids)
            visibility |= Q(
                source_registration__club_id__in=managed_club_ids,
                submitted_at__isnull=False,
            ) & ~Q(status=UnionPlayerTransfer.Status.DRAFT)
        visibility |= Q(
            player__user=user,
            submitted_at__isnull=False,
        ) & ~Q(status=UnionPlayerTransfer.Status.DRAFT)
        rows = rows.filter(visibility).distinct()

    statuses = request.query_params.getlist("status")
    if statuses:
        supported_statuses = set(UnionPlayerTransfer.Status.values)
        invalid = sorted(set(statuses) - supported_statuses)
        if invalid:
            raise APIValidationError(
                {"status": f"Unsupported status: {', '.join(invalid)}."}
            )
        rows = rows.filter(status__in=statuses)

    exact_filters = {
        "workspace": "workspace_id",
        "player": "player_id",
        "source_club": "source_registration__club_id",
        "destination_club": "destination_club_id",
        "source_registration": "source_registration_id",
        "destination_registration": "destination_registration_id",
        "return_registration": "return_registration_id",
        "transfer_type": "transfer_type",
        "source_response_status": "source_club_response_status",
        "player_consent_status": "player_consent_status",
    }
    for parameter, model_field in exact_filters.items():
        value = request.query_params.get(parameter)
        if value:
            try:
                rows = rows.filter(**{model_field: value})
            except (TypeError, ValueError) as exc:
                raise APIValidationError({parameter: "Invalid filter value."}) from exc

    date_filters = {
        "effective_from": ("effective_on__gte", "effective_from"),
        "effective_to": ("effective_on__lte", "effective_to"),
        "loan_end_from": ("loan_end_on__gte", "loan_end_from"),
        "loan_end_to": ("loan_end_on__lte", "loan_end_to"),
    }
    for parameter, (model_field, _) in date_filters.items():
        value = _parse_date_filter(request.query_params, parameter)
        if value is not None:
            rows = rows.filter(**{model_field: value})

    search = request.query_params.get("search", "").strip()
    if search:
        rows = rows.filter(
            Q(player__union_player_number__icontains=search)
            | Q(player__first_name__icontains=search)
            | Q(player__last_name__icontains=search)
            | Q(source_registration__club__name__icontains=search)
            | Q(destination_club__name__icontains=search)
        )

    ordering = request.query_params.get("ordering", "-created_at")
    ordering_fields = {
        "created_at": ("created_at", "id"),
        "-created_at": ("-created_at", "-id"),
        "updated_at": ("updated_at", "id"),
        "-updated_at": ("-updated_at", "-id"),
        "submitted_at": ("submitted_at", "id"),
        "-submitted_at": ("-submitted_at", "-id"),
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
    if ordering not in ordering_fields:
        raise APIValidationError({"ordering": "Unsupported ordering value."})
    return rows.order_by(*ordering_fields[ordering])


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def player_transfer_submission_list_create_view(request):
    if request.method == "GET":
        rows = _filtered_transfer_queryset(request)
        results = ClubPlayerTransferSubmissionListSerializer(rows, many=True).data
        return Response({"count": len(results), "results": results})

    serializer = ClubPlayerTransferDraftCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    _require_creation_permission(
        request.user,
        serializer.validated_data["destination_club"],
    )
    try:
        transfer = _create_transfer_from_validated(
            request.user,
            serializer.validated_data,
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    transfer = _fresh_transfer(transfer.id)
    return Response(
        ClubPlayerTransferSubmissionDetailSerializer(transfer).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticatedAudit])
def player_transfer_submission_detail_view(request, pk):
    if request.method == "GET":
        transfer = _visible_transfer_or_404(request.user, pk)
        return Response(ClubPlayerTransferSubmissionDetailSerializer(transfer).data)

    transfer = _destination_transfer_or_404(request.user, pk)
    serializer = ClubPlayerTransferDraftUpdateSerializer(
        transfer,
        data=request.data,
        partial=True,
    )
    serializer.is_valid(raise_exception=True)
    try:
        updated = update_player_transfer_draft(
            transfer_id=transfer.id,
            actor=request.user,
            updates=serializer.validated_data,
        )
    except UnionPlayerTransfer.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        return _validation_error_response(exc)
    return Response(
        ClubPlayerTransferSubmissionDetailSerializer(_fresh_transfer(updated.id)).data
    )


def _destination_action(request, pk, service):
    transfer = _destination_transfer_or_404(request.user, pk)
    try:
        updated = service(transfer_id=transfer.id, actor=request.user)
    except UnionPlayerTransfer.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        return _validation_error_response(exc)
    return Response(
        ClubPlayerTransferSubmissionDetailSerializer(_fresh_transfer(updated.id)).data
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def player_transfer_submission_submit_view(request, pk):
    return _destination_action(request, pk, submit_player_transfer)


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def player_transfer_submission_resubmit_view(request, pk):
    return _destination_action(request, pk, resubmit_player_transfer)


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def player_transfer_submission_cancel_view(request, pk):
    transfer = _destination_transfer_or_404(request.user, pk)
    serializer = ClubPlayerTransferCancelSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        updated = cancel_player_transfer_request(
            transfer_id=transfer.id,
            actor=request.user,
            reason=serializer.validated_data["reason"],
        )
    except UnionPlayerTransfer.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        return _validation_error_response(exc)
    return Response(
        ClubPlayerTransferSubmissionDetailSerializer(_fresh_transfer(updated.id)).data
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def player_transfer_submission_source_response_view(request, pk):
    transfer = _source_transfer_or_404(request.user, pk)
    serializer = ClubPlayerTransferSourceResponseSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        updated = record_source_club_transfer_response(
            transfer_id=transfer.id,
            actor=request.user,
            response_status=serializer.validated_data["response_status"],
            response=serializer.validated_data["response"],
        )
    except UnionPlayerTransfer.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        return _validation_error_response(exc)
    return Response(
        ClubPlayerTransferSubmissionDetailSerializer(_fresh_transfer(updated.id)).data
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def player_transfer_submission_consent_view(request, pk):
    transfer = _player_transfer_or_404(request.user, pk)
    serializer = PlayerTransferDirectConsentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        updated = record_player_transfer_consent(
            transfer_id=transfer.id,
            actor=request.user,
            consent_method=serializer.validated_data["consent_method"],
        )
    except UnionPlayerTransfer.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        return _validation_error_response(exc)
    return Response(
        ClubPlayerTransferSubmissionDetailSerializer(_fresh_transfer(updated.id)).data
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def player_transfer_submission_decline_view(request, pk):
    transfer = _player_transfer_or_404(request.user, pk)
    serializer = PlayerTransferDirectDeclineSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        updated = decline_player_transfer_consent(
            transfer_id=transfer.id,
            actor=request.user,
            reason=serializer.validated_data["reason"],
        )
    except UnionPlayerTransfer.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        return _validation_error_response(exc)
    return Response(
        ClubPlayerTransferSubmissionDetailSerializer(_fresh_transfer(updated.id)).data
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def player_transfer_list_create_view(request):
    user_clubs = get_user_clubs(request.user)
    if not _is_super_admin(request.user) and not user_clubs.exists():
        raise PermissionDenied("Club access is required.")
    if request.method == "GET":
        rows = (
            PlayerTransfer.objects.filter(
                Q(from_club__in=user_clubs) | Q(to_club__in=user_clubs)
            )
            .select_related("player", "from_club", "to_club")
            .distinct()
        )
        return Response(LegacyPlayerTransferSummarySerializer(rows, many=True).data)

    serializer = ClubPlayerTransferDraftCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    _require_creation_permission(
        request.user,
        serializer.validated_data["destination_club"],
    )
    try:
        transfer = _create_transfer_from_validated(
            request.user,
            serializer.validated_data,
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    data = {
        "workflow": "UNION_PLAYER_TRANSFER",
        "deprecated_direct_creation": True,
        "submission": _fresh_transfer(transfer.id),
    }
    return Response(
        LegacyPlayerTransferCompatibilityResultSerializer(data).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def player_transfer_detail_view(request, pk):
    user_clubs = get_user_clubs(request.user)
    if not _is_super_admin(request.user) and not user_clubs.exists():
        raise PermissionDenied("Club access is required.")
    transfer = get_object_or_404(
        PlayerTransfer.objects.filter(
            Q(from_club__in=user_clubs) | Q(to_club__in=user_clubs)
        )
        .select_related(
            "player",
            "from_club",
            "to_club",
            "requested_by",
            "approved_by",
        )
        .distinct(),
        pk=pk,
    )
    return Response(LegacyPlayerTransferReadSerializer(transfer).data)
