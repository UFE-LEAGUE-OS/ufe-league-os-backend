"""Workspace-isolated endpoints for Union approvals and audit evidence."""

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsAuthenticatedAudit

from .models import (
    UnionApproval,
    UnionAuditEvent,
    UnionDocumentReference,
    UnionReviewComment,
)
from .union_governance import (
    log_union_audit_event,
    request_union_approval,
    review_union_approval,
)
from .union_governance_serializers import (
    UnionApprovalSerializer,
    UnionAuditEventSerializer,
    UnionDocumentReferenceSerializer,
    UnionReviewCommentSerializer,
)
from .union_management_views import _has_workspace_permission, _resolve_membership
from .union_scopes import subject_belongs_to_workspace


def _page(request, queryset, serializer_class):
    try:
        page_size = min(max(int(request.query_params.get("page_size", 50)), 1), 100)
        page = max(int(request.query_params.get("page", 1)), 1)
    except ValueError:
        return Response(
            {"detail": "page and page_size must be positive integers."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    total = queryset.count()
    start = (page - 1) * page_size
    results = serializer_class(queryset[start : start + page_size], many=True).data
    return Response(
        {"count": total, "page": page, "page_size": page_size, "results": results}
    )


def _require_workspace_permission(request, membership, permission):
    if _has_workspace_permission(request.user, membership.workspace, permission):
        return None
    return Response(
        {"detail": "You do not have permission to perform this workspace action."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _can_write_operational_evidence(request, membership):
    return any(
        _has_workspace_permission(request.user, membership.workspace, permission)
        for permission in {
            "union.approvals.manage",
            "union.competitions.manage",
            "union.clubs.manage",
            "union.players.approve",
            "union.referees.manage",
            "union.finance.manage",
            "union.communications.manage",
            "union.sponsors.manage",
            "union.users.manage",
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_approvals_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error

    workspace = membership.workspace
    if request.method == "GET":
        denied = _require_workspace_permission(
            request, membership, "union.approvals.manage"
        )
        if denied:
            return denied
        queryset = UnionApproval.objects.filter(workspace=workspace).select_related(
            "requested_by", "reviewed_by"
        )
        for field in ("status", "action", "subject_type"):
            value = request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        value = request.query_params.get("subject_id")
        if value:
            queryset = queryset.filter(subject_id=value)
        return _page(request, queryset, UnionApprovalSerializer)

    denied = _require_workspace_permission(
        request, membership, "union.approvals.manage"
    )
    if denied:
        return denied
    serializer = UnionApprovalSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    if not subject_belongs_to_workspace(
        workspace,
        serializer.validated_data["subject_type"],
        serializer.validated_data["subject_id"],
    ):
        return Response(
            {"subject_id": "Subject is not owned by this workspace."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    approval = request_union_approval(
        workspace=workspace,
        requested_by=request.user,
        **serializer.validated_data,
    )
    return Response(
        UnionApprovalSerializer(approval).data, status=status.HTTP_201_CREATED
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_approval_detail_view(request, approval_id):
    membership, error = _resolve_membership(request)
    if error:
        return error
    denied = _require_workspace_permission(
        request, membership, "union.approvals.manage"
    )
    if denied:
        return denied

    approval = UnionApproval.objects.filter(
        pk=approval_id, workspace=membership.workspace
    ).first()
    if approval is None:
        return Response(
            {"detail": "Approval not found."}, status=status.HTTP_404_NOT_FOUND
        )
    if request.method == "GET":
        return Response(UnionApprovalSerializer(approval).data)

    decision = request.data.get("decision")
    if decision not in {"APPROVED", "REJECTED"}:
        return Response(
            {"decision": "Choose APPROVED or REJECTED."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        approval = review_union_approval(
            approval_id=approval.id,
            reviewer=request.user,
            approved=decision == "APPROVED",
            decision_reason=str(request.data.get("decision_reason") or ""),
        )
    except ValidationError as exc:
        return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
    return Response(UnionApprovalSerializer(approval).data)


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_audit_events_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error
    denied = _require_workspace_permission(request, membership, "union.audit.view")
    if denied:
        return denied

    queryset = UnionAuditEvent.objects.filter(
        workspace=membership.workspace
    ).select_related("actor")
    for field in ("action", "target_type"):
        value = request.query_params.get(field)
        if value:
            queryset = queryset.filter(**{field: value})
    return _page(request, queryset, UnionAuditEventSerializer)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_review_comments_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error
    denied = _require_workspace_permission(request, membership, "union.dashboard.view")
    if denied:
        return denied

    workspace = membership.workspace
    if request.method == "GET":
        queryset = UnionReviewComment.objects.filter(
            workspace=workspace
        ).select_related("author")
        for field in ("subject_type", "subject_id"):
            value = request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        return _page(request, queryset, UnionReviewCommentSerializer)

    if not _can_write_operational_evidence(request, membership):
        return Response(
            {"detail": "You do not have permission to add operational comments."},
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer = UnionReviewCommentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    if not subject_belongs_to_workspace(
        workspace,
        serializer.validated_data["subject_type"],
        serializer.validated_data["subject_id"],
    ):
        return Response(
            {"subject_id": "Subject is not owned by this workspace."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    comment = serializer.save(workspace=workspace, author=request.user)
    log_union_audit_event(
        workspace=workspace,
        actor=request.user,
        action="review_comment.created",
        target=comment,
        metadata={
            "subject_type": comment.subject_type,
            "subject_id": comment.subject_id,
        },
    )
    return Response(
        UnionReviewCommentSerializer(comment).data, status=status.HTTP_201_CREATED
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedAudit])
def union_admin_document_references_view(request):
    membership, error = _resolve_membership(request)
    if error:
        return error
    denied = _require_workspace_permission(request, membership, "union.dashboard.view")
    if denied:
        return denied

    workspace = membership.workspace
    if request.method == "GET":
        queryset = UnionDocumentReference.objects.filter(
            workspace=workspace
        ).select_related("uploaded_by")
        for field in ("subject_type", "subject_id", "document_type"):
            value = request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        return _page(request, queryset, UnionDocumentReferenceSerializer)

    if not _can_write_operational_evidence(request, membership):
        return Response(
            {"detail": "You do not have permission to add operational documents."},
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer = UnionDocumentReferenceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    if not subject_belongs_to_workspace(
        workspace,
        serializer.validated_data["subject_type"],
        serializer.validated_data["subject_id"],
    ):
        return Response(
            {"subject_id": "Subject is not owned by this workspace."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    document = serializer.save(workspace=workspace, uploaded_by=request.user)
    log_union_audit_event(
        workspace=workspace,
        actor=request.user,
        action="document_reference.created",
        target=document,
        metadata={
            "subject_type": document.subject_type,
            "subject_id": document.subject_id,
        },
    )
    return Response(
        UnionDocumentReferenceSerializer(document).data,
        status=status.HTTP_201_CREATED,
    )
