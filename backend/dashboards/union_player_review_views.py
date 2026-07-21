"""Scoped Union APIs for reviewing Club player-registration submissions."""

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsAuthenticatedAudit
from teams.models import PlayerRegistration

from .models import UnionPlayerRegistration
from .union_management_views import _has_workspace_permission, _resolve_membership
from .union_player_review_serializers import (
    UnionAuthoritativePlayerRegistrationSerializer,
    UnionPlayerRegistrationDecisionSerializer,
    UnionPlayerRegistrationReviewerAssignSerializer,
    UnionPlayerRegistrationReviewResultSerializer,
    UnionPlayerRegistrationSubmissionDetailSerializer,
    UnionPlayerRegistrationSubmissionListSerializer,
)
from .union_player_review_services import (
    approve_player_registration_submission,
    assign_player_registration_reviewer,
    reject_player_registration_submission,
    request_player_registration_changes,
    start_player_registration_review,
    submission_is_in_membership_scope,
)
from .union_scopes import scope_allows


def _error(message, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"detail": message}, status=status_code)


def _resolve_review_membership(request):
    workspace_value = (
        request.query_params.get("workspace")
        if request.method == "GET"
        else request.data.get("workspace")
    )
    if not workspace_value:
        return None, _error("workspace is required.")
    return _resolve_membership(request)


def _require_review_permission(request, membership, permission):
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


def _submission_queryset():
    return (
        PlayerRegistration.objects.exclude(
            submission_status=PlayerRegistration.SubmissionStatus.LEGACY
        )
        .select_related(
            "club",
            "team",
            "season_record",
            "union_workspace",
            "union_player",
            "assigned_reviewer",
            "submitted_by",
        )
        .prefetch_related("requested_competition_editions__identity")
    )


def _scoped_submission_or_404(membership, submission_id):
    submission = get_object_or_404(
        _submission_queryset(),
        pk=submission_id,
        union_workspace=membership.workspace,
    )
    if not submission_is_in_membership_scope(membership, submission):
        return None
    return submission


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
def union_player_registration_submissions_view(request):
    membership, error = _resolve_review_membership(request)
    if error:
        return error
    permission_error = _require_review_permission(
        request,
        membership,
        "union.registrations.view",
    )
    if permission_error:
        return permission_error

    queryset = _submission_queryset().filter(union_workspace=membership.workspace)
    statuses = request.query_params.getlist("submission_status")
    if statuses:
        queryset = queryset.filter(submission_status__in=statuses)
    else:
        queryset = queryset.exclude(
            submission_status__in=[
                PlayerRegistration.SubmissionStatus.DRAFT,
                PlayerRegistration.SubmissionStatus.WITHDRAWN,
            ]
        )

    field_filters = {
        "club": "club_id",
        "team": "team_id",
        "season": "season_record_id",
        "registration_type": "registration_type",
        "assigned_reviewer": "assigned_reviewer_id",
    }
    for parameter, field_name in field_filters.items():
        value = request.query_params.get(parameter)
        if value:
            queryset = queryset.filter(**{field_name: value})

    submitted_from = parse_date(request.query_params.get("submitted_from", ""))
    submitted_to = parse_date(request.query_params.get("submitted_to", ""))
    if submitted_from:
        queryset = queryset.filter(submitted_at__date__gte=submitted_from)
    if submitted_to:
        queryset = queryset.filter(submitted_at__date__lte=submitted_to)

    search = request.query_params.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(registration_number__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(union_player__union_player_number__icontains=search)
            | Q(club__name__icontains=search)
        )

    ordering_map = {
        "submitted_at": "submitted_at",
        "-submitted_at": "-submitted_at",
        "updated_at": "updated_at",
        "-updated_at": "-updated_at",
        "registration_number": "registration_number",
        "-registration_number": "-registration_number",
        "club": "club__name",
        "-club": "-club__name",
    }
    ordering = ordering_map.get(
        request.query_params.get("ordering"),
        "submitted_at",
    )
    scoped = [
        submission
        for submission in queryset.order_by(ordering, "id")
        if submission_is_in_membership_scope(membership, submission)
    ]
    return Response(
        {
            "count": len(scoped),
            "results": UnionPlayerRegistrationSubmissionListSerializer(
                scoped,
                many=True,
            ).data,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_player_registration_submission_detail_view(request, submission_id):
    membership, error = _resolve_review_membership(request)
    if error:
        return error
    permission_error = _require_review_permission(
        request,
        membership,
        "union.registrations.view",
    )
    if permission_error:
        return permission_error
    submission = _scoped_submission_or_404(membership, submission_id)
    if submission is None:
        return _error(
            "Player registration submission not found.",
            status.HTTP_404_NOT_FOUND,
        )
    return Response(UnionPlayerRegistrationSubmissionDetailSerializer(submission).data)


def _action_context(request, submission_id, permission):
    membership, error = _resolve_review_membership(request)
    if error:
        return None, None, error
    permission_error = _require_review_permission(request, membership, permission)
    if permission_error:
        return None, None, permission_error
    submission = _scoped_submission_or_404(membership, submission_id)
    if submission is None:
        return (
            None,
            None,
            _error(
                "Player registration submission not found.",
                status.HTTP_404_NOT_FOUND,
            ),
        )
    return membership, submission, None


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_player_registration_assign_reviewer_view(request, submission_id):
    membership, submission, error = _action_context(
        request,
        submission_id,
        "union.registrations.manage",
    )
    if error:
        return error
    serializer = UnionPlayerRegistrationReviewerAssignSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    assigned_user = serializer.validated_data.get("reviewer", request.user)
    try:
        submission = assign_player_registration_reviewer(
            submission_id=submission.id,
            reviewer=request.user,
            assigned_user=assigned_user,
            membership=membership,
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    return Response(UnionPlayerRegistrationSubmissionDetailSerializer(submission).data)


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_player_registration_start_review_view(request, submission_id):
    membership, submission, error = _action_context(
        request,
        submission_id,
        "union.registrations.manage",
    )
    if error:
        return error
    try:
        submission = start_player_registration_review(
            submission_id=submission.id,
            reviewer=request.user,
            membership=membership,
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    return Response(UnionPlayerRegistrationSubmissionDetailSerializer(submission).data)


def _decision_action(request, submission_id, service, permission):
    membership, submission, error = _action_context(
        request,
        submission_id,
        permission,
    )
    if error:
        return error
    serializer = UnionPlayerRegistrationDecisionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        result = service(
            submission_id=submission.id,
            reviewer=request.user,
            membership=membership,
            reason=serializer.validated_data["reason"],
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    return result


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_player_registration_request_changes_view(request, submission_id):
    result = _decision_action(
        request,
        submission_id,
        request_player_registration_changes,
        "union.registrations.manage",
    )
    if isinstance(result, Response):
        return result
    return Response(UnionPlayerRegistrationSubmissionDetailSerializer(result).data)


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_player_registration_approve_view(request, submission_id):
    result = _decision_action(
        request,
        submission_id,
        approve_player_registration_submission,
        "union.players.approve",
    )
    if isinstance(result, Response):
        return result
    return Response(UnionPlayerRegistrationReviewResultSerializer(result).data)


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def union_player_registration_reject_view(request, submission_id):
    result = _decision_action(
        request,
        submission_id,
        reject_player_registration_submission,
        "union.players.approve",
    )
    if isinstance(result, Response):
        return result
    return Response(UnionPlayerRegistrationSubmissionDetailSerializer(result).data)


def _authoritative_queryset(membership):
    return (
        UnionPlayerRegistration.objects.filter(workspace=membership.workspace)
        .select_related(
            "workspace",
            "player",
            "club",
            "team",
            "season",
            "source_registration",
            "approved_by",
            "predecessor",
        )
        .order_by("-effective_from", "-id")
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_authoritative_player_registrations_view(request):
    membership, error = _resolve_review_membership(request)
    if error:
        return error
    permission_error = _require_review_permission(
        request,
        membership,
        "union.players.view",
    )
    if permission_error:
        return permission_error
    queryset = _authoritative_queryset(membership)
    for parameter, field_name in {
        "player": "player_id",
        "club": "club_id",
        "team": "team_id",
        "season": "season_id",
        "status": "status",
        "registration_type": "registration_type",
    }.items():
        value = request.query_params.get(parameter)
        if value:
            queryset = queryset.filter(**{field_name: value})
    search = request.query_params.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(player__union_player_number__icontains=search)
            | Q(player__first_name__icontains=search)
            | Q(player__last_name__icontains=search)
            | Q(club__name__icontains=search)
        )
    scoped = [
        registration
        for registration in queryset
        if scope_allows(membership, "club", registration.club_id)
    ]
    return Response(
        {
            "count": len(scoped),
            "results": UnionAuthoritativePlayerRegistrationSerializer(
                scoped,
                many=True,
            ).data,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_authoritative_player_registration_detail_view(request, registration_id):
    membership, error = _resolve_review_membership(request)
    if error:
        return error
    permission_error = _require_review_permission(
        request,
        membership,
        "union.players.view",
    )
    if permission_error:
        return permission_error
    registration = get_object_or_404(
        _authoritative_queryset(membership),
        pk=registration_id,
    )
    if not scope_allows(membership, "club", registration.club_id):
        return _error(
            "Player registration not found.",
            status.HTTP_404_NOT_FOUND,
        )
    return Response(UnionAuthoritativePlayerRegistrationSerializer(registration).data)
