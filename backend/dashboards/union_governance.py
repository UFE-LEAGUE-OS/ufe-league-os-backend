"""Shared, workspace-safe governance primitives for Union operations."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import UnionApproval, UnionAuditEvent


def log_union_audit_event(
    *,
    workspace,
    actor,
    action,
    target=None,
    target_type="",
    target_id=None,
    metadata=None,
):
    """Append a material workspace action to the immutable Union audit trail."""

    if target is not None:
        target_type = target._meta.label_lower
        target_id = target.pk

    return UnionAuditEvent.objects.create(
        workspace=workspace,
        actor=actor if getattr(actor, "pk", None) else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata or {},
    )


def transition_status(
    *, instance, target_status, allowed_transitions, actor, workspace, reason=""
):
    """Apply a legal status transition and write its accompanying audit event."""

    current_status = instance.status
    allowed = set(allowed_transitions.get(current_status, ()))

    if target_status not in allowed:
        raise ValidationError(
            {"status": f"Cannot transition from {current_status} to {target_status}."}
        )

    if not reason.strip():
        raise ValidationError({"reason": "A reason is required for this transition."})

    instance.status = target_status
    instance.save(update_fields=["status", "updated_at"])
    log_union_audit_event(
        workspace=workspace,
        actor=actor,
        action=f"{instance._meta.model_name}.status_changed",
        target=instance,
        metadata={
            "from_status": current_status,
            "to_status": target_status,
            "reason": reason.strip(),
        },
    )
    return instance


def request_union_approval(
    *,
    workspace,
    subject_type,
    subject_id,
    action,
    requested_by,
    reason="",
    metadata=None,
):
    """Create a pending approval and its request audit event."""

    approval = UnionApproval.objects.create(
        workspace=workspace,
        subject_type=subject_type,
        subject_id=subject_id,
        action=action,
        requested_by=requested_by,
        reason=reason.strip(),
        metadata=metadata or {},
    )
    log_union_audit_event(
        workspace=workspace,
        actor=requested_by,
        action="approval.requested",
        target=approval,
        metadata={
            "requested_action": action,
            "subject_type": subject_type,
            "subject_id": subject_id,
        },
    )
    return approval


@transaction.atomic
def review_union_approval(*, approval_id, reviewer, approved, decision_reason=""):
    """Resolve a pending approval without permitting self-approval."""

    approval = (
        UnionApproval.objects.select_for_update()
        .select_related("workspace")
        .get(pk=approval_id)
    )

    if approval.status != UnionApproval.Status.PENDING:
        raise ValidationError({"status": "Only pending approvals can be reviewed."})

    if approval.requested_by_id and approval.requested_by_id == getattr(
        reviewer, "pk", None
    ):
        raise ValidationError(
            {"reviewer": "A requester cannot approve their own request."}
        )

    if not decision_reason.strip():
        raise ValidationError({"decision_reason": "A written decision is required."})

    approval.status = (
        UnionApproval.Status.APPROVED if approved else UnionApproval.Status.REJECTED
    )
    approval.reviewed_by = reviewer
    approval.reviewed_at = timezone.now()
    approval.decision_reason = decision_reason.strip()
    approval.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "decision_reason",
            "updated_at",
        ]
    )
    log_union_audit_event(
        workspace=approval.workspace,
        actor=reviewer,
        action="approval.approved" if approved else "approval.rejected",
        target=approval,
        metadata={
            "subject_type": approval.subject_type,
            "subject_id": approval.subject_id,
        },
    )
    return approval
