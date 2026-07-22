"""Union-side review services for Club player-registration submissions."""

from datetime import timedelta
from functools import partial

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import Notification, NotificationPreference
from accounts.services import create_in_app_notification
from teams.models import PlayerRegistration
from teams.player_submission_services import (
    SubmissionValidationError,
    _store_validation_result,
    validate_player_registration_for_union_review,
)

from .models import (
    UnionPlayer,
    UnionPlayerRegistration,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
from .union_governance import log_union_audit_event
from .union_player_eligibility_services import (
    TERMINAL_STATUSES,
    create_pending_eligibilities_for_submission,
)
from .union_scopes import scope_allows


def _is_super_admin(user):
    return bool(
        user
        and (
            getattr(user, "is_superuser", False)
            or getattr(user, "role", None) == "SUPER_ADMIN"
        )
    )


def _active_membership(*, reviewer, membership):
    if membership is None or not getattr(membership, "pk", None):
        raise ValidationError({"workspace": "An active Union membership is required."})
    active = (
        UnionWorkspaceMembership.objects.filter(
            pk=membership.pk,
            user=reviewer,
            is_active=True,
            workspace__status=UnionWorkspace.Status.ACTIVE,
            workspace__related_union__isnull=False,
        )
        .select_related("workspace", "workspace__related_union")
        .first()
    )
    if active is None:
        raise ValidationError({"workspace": "An active Union membership is required."})
    return active


def _has_permission(user, membership, permission):
    return _is_super_admin(user) or permission in membership.effective_permissions


def _submission_scope_allows(membership, submission):
    if submission.union_workspace_id != membership.workspace_id:
        return False
    if not scope_allows(membership, "club", submission.club_id):
        return False
    for edition in submission.requested_competition_editions.select_related(
        "identity"
    ).all():
        if not scope_allows(
            membership, "competition_identity", edition.identity_id
        ) or not scope_allows(membership, "competition_edition", edition.id):
            return False
    return True


def submission_is_in_membership_scope(membership, submission):
    """Public read helper shared by scoped Union list/detail endpoints."""

    return bool(
        membership
        and getattr(membership, "is_active", False)
        and membership.workspace.status == UnionWorkspace.Status.ACTIVE
        and _submission_scope_allows(membership, submission)
    )


def _require_review_access(*, reviewer, membership, submission, permission):
    membership = _active_membership(reviewer=reviewer, membership=membership)
    if not _has_permission(reviewer, membership, permission):
        raise ValidationError({"permission": f"Reviewer requires {permission}."})
    if not _submission_scope_allows(membership, submission):
        raise ValidationError(
            {"scope": "Submission is outside the selected workspace or resource scope."}
        )
    return membership


def _notify_club_submitter(submission_id, status_value, title, message):
    submission = (
        PlayerRegistration.objects.filter(pk=submission_id)
        .select_related("submitted_by")
        .first()
    )
    if submission is None or submission.submitted_by_id is None:
        return
    try:
        create_in_app_notification(
            user=submission.submitted_by,
            event_type=NotificationPreference.EventType.GOVERNANCE,
            category=Notification.Category.GOVERNANCE,
            title=title,
            message=message,
            action_url="/dashboard/club-admin",
            metadata={
                "submission_id": submission.id,
                "club_id": submission.club_id,
                "submission_status": status_value,
            },
        )
    except Exception:
        # A post-commit notification failure must not undo a completed decision.
        return


def _schedule_club_notification(submission, *, title, message):
    if submission.submitted_by_id is None:
        return
    transaction.on_commit(
        partial(
            _notify_club_submitter,
            submission.id,
            submission.submission_status,
            title,
            message,
        )
    )


def _decision_reason(reason):
    value = str(reason or "").strip()
    if not value:
        raise ValidationError({"reason": "A written reason is required."})
    return value


@transaction.atomic
def assign_player_registration_reviewer(
    *,
    submission_id,
    reviewer,
    assigned_user,
    membership,
):
    submission = (
        PlayerRegistration.objects.select_for_update(of=("self",))
        .select_related("union_workspace", "club")
        .get(pk=submission_id)
    )
    membership = _require_review_access(
        reviewer=reviewer,
        membership=membership,
        submission=submission,
        permission="union.registrations.manage",
    )
    if submission.submission_status not in {
        PlayerRegistration.SubmissionStatus.SUBMITTED,
        PlayerRegistration.SubmissionStatus.UNDER_UNION_REVIEW,
    }:
        raise ValidationError(
            {"submission_status": "Reviewer assignment is not allowed in this state."}
        )
    assigned_membership = (
        UnionWorkspaceMembership.objects.filter(
            user=assigned_user,
            workspace=membership.workspace,
            is_active=True,
            workspace__status=UnionWorkspace.Status.ACTIVE,
        )
        .select_related("workspace")
        .first()
    )
    if assigned_membership is None:
        raise ValidationError(
            {"reviewer": "Assigned reviewer must belong to this workspace."}
        )
    if not {
        "union.registrations.manage",
        "union.players.approve",
    }.intersection(assigned_membership.effective_permissions):
        raise ValidationError(
            {"reviewer": "Assigned user does not have a review permission."}
        )
    submission.assigned_reviewer = assigned_user
    submission.save(update_fields=["assigned_reviewer", "updated_at"])
    log_union_audit_event(
        workspace=membership.workspace,
        actor=reviewer,
        action="player_registration.reviewer_assigned",
        target=submission,
        metadata={
            "submission_id": submission.id,
            "assigned_reviewer_id": assigned_user.id,
        },
    )
    return submission


@transaction.atomic
def start_player_registration_review(*, submission_id, reviewer, membership):
    submission = (
        PlayerRegistration.objects.select_for_update(of=("self",))
        .select_related(
            "union_workspace",
            "club",
            "team",
            "season_record__league",
            "union_player",
        )
        .get(pk=submission_id)
    )
    membership = _require_review_access(
        reviewer=reviewer,
        membership=membership,
        submission=submission,
        permission="union.registrations.manage",
    )
    if submission.submission_status != PlayerRegistration.SubmissionStatus.SUBMITTED:
        raise ValidationError(
            {"submission_status": "Only submitted applications may enter review."}
        )
    validation_result = validate_player_registration_for_union_review(
        submission=submission,
        reviewer=reviewer,
        membership=membership,
        required_permission="union.registrations.manage",
    )
    _store_validation_result(
        submission=submission,
        actor=reviewer,
        validation_result=validation_result,
    )
    submission.submission_status = (
        PlayerRegistration.SubmissionStatus.UNDER_UNION_REVIEW
    )
    submission.assigned_reviewer = reviewer
    submission.save(
        update_fields=[
            "submission_status",
            "assigned_reviewer",
            "updated_at",
        ]
    )
    log_union_audit_event(
        workspace=membership.workspace,
        actor=reviewer,
        action="player_registration.review_started",
        target=submission,
        metadata={"submission_id": submission.id},
    )
    return submission


@transaction.atomic
def request_player_registration_changes(
    *,
    submission_id,
    reviewer,
    membership,
    reason,
):
    written_reason = _decision_reason(reason)
    submission = (
        PlayerRegistration.objects.select_for_update(of=("self",))
        .select_related("union_workspace", "club", "submitted_by")
        .get(pk=submission_id)
    )
    membership = _require_review_access(
        reviewer=reviewer,
        membership=membership,
        submission=submission,
        permission="union.registrations.manage",
    )
    if (
        submission.submission_status
        != PlayerRegistration.SubmissionStatus.UNDER_UNION_REVIEW
    ):
        raise ValidationError(
            {
                "submission_status": (
                    "Only applications under Union review may request changes."
                )
            }
        )
    submission.submission_status = PlayerRegistration.SubmissionStatus.CHANGES_REQUESTED
    submission.change_request_reason = written_reason
    submission.assigned_reviewer = reviewer
    submission.reviewed_at = timezone.now()
    submission.save(
        update_fields=[
            "submission_status",
            "change_request_reason",
            "assigned_reviewer",
            "reviewed_at",
            "updated_at",
        ]
    )
    log_union_audit_event(
        workspace=membership.workspace,
        actor=reviewer,
        action="player_registration.changes_requested",
        target=submission,
        metadata={"submission_id": submission.id},
    )
    _schedule_club_notification(
        submission,
        title="Player registration changes requested",
        message="The Union requested changes to a player registration submission.",
    )
    return submission


def reject_player_registration_submission(
    *,
    submission_id,
    reviewer,
    membership,
    reason,
):
    written_reason = _decision_reason(reason)
    validation_error = None
    with transaction.atomic():
        submission = (
            PlayerRegistration.objects.select_for_update(of=("self",))
            .select_related(
                "union_workspace",
                "club",
                "team",
                "season_record__league",
                "union_player",
                "submitted_by",
            )
            .get(pk=submission_id)
        )
        membership = _require_review_access(
            reviewer=reviewer,
            membership=membership,
            submission=submission,
            permission="union.players.approve",
        )
        if (
            submission.submission_status
            != PlayerRegistration.SubmissionStatus.UNDER_UNION_REVIEW
        ):
            raise ValidationError(
                {
                    "submission_status": (
                        "Only applications under Union review may be rejected."
                    )
                }
            )
        validation_result = validate_player_registration_for_union_review(
            submission=submission,
            reviewer=reviewer,
            membership=membership,
            required_permission="union.players.approve",
            final_decision=True,
        )
        _store_validation_result(
            submission=submission,
            actor=reviewer,
            validation_result=validation_result,
        )
        self_review_error = next(
            (
                item
                for item in validation_result["blocking_errors"]
                if item["code"] == "REVIEWER_IS_SUBMITTER"
            ),
            None,
        )
        if self_review_error is not None:
            validation_error = SubmissionValidationError(validation_result)
        else:
            submission.submission_status = PlayerRegistration.SubmissionStatus.REJECTED
            submission.status = PlayerRegistration.RegistrationStatus.INACTIVE
            submission.union_decision_reason = written_reason
            submission.assigned_reviewer = reviewer
            submission.reviewed_at = timezone.now()
            submission.save(
                update_fields=[
                    "submission_status",
                    "status",
                    "union_decision_reason",
                    "assigned_reviewer",
                    "reviewed_at",
                    "updated_at",
                ]
            )
            log_union_audit_event(
                workspace=membership.workspace,
                actor=reviewer,
                action="player_registration.rejected",
                target=submission,
                metadata={
                    "submission_id": submission.id,
                    "player_id": submission.union_player_id,
                    "club_id": submission.club_id,
                    "season_id": submission.season_record_id,
                    "registration_type": submission.registration_type,
                },
            )
            _schedule_club_notification(
                submission,
                title="Player registration rejected",
                message="The Union rejected a player registration submission.",
            )
    if validation_error is not None:
        raise validation_error
    return submission


def _resolve_idempotent_registration(submission):
    if submission.registration_type in {
        PlayerRegistration.RegistrationType.FIRST_REGISTRATION,
        PlayerRegistration.RegistrationType.FREE_AGENT_REGISTRATION,
        PlayerRegistration.RegistrationType.SEASON_RENEWAL,
    }:
        registration = UnionPlayerRegistration.objects.filter(
            source_registration=submission,
            workspace=submission.union_workspace,
            player=submission.union_player,
        ).first()
    elif (
        submission.registration_type
        == PlayerRegistration.RegistrationType.COMPETITION_REGISTRATION
    ):
        registration = UnionPlayerRegistration.objects.filter(
            workspace=submission.union_workspace,
            player=submission.union_player,
            club=submission.club,
            status=UnionPlayerRegistration.Status.ACTIVE,
        ).first()
    else:
        registration = None
    if registration is None:
        raise ValidationError(
            {
                "submission_status": (
                    "Approved submission has no consistent authoritative registration."
                )
            }
        )
    return registration


def _review_result(
    submission,
    registration,
    *,
    idempotent_replay,
    eligibility_result,
):
    eligibilities = eligibility_result["eligibilities"]
    return {
        "submission": submission,
        "authoritative_registration": registration,
        "automatic_validation": submission.automatic_validation,
        "idempotent_replay": idempotent_replay,
        "pending_eligibilities": eligibilities,
        "eligibility_created_count": eligibility_result["created_count"],
        "eligibility_existing_count": eligibility_result["existing_count"],
        "eligibility_review_required": any(
            eligibility.status not in TERMINAL_STATUSES for eligibility in eligibilities
        ),
    }


def approve_player_registration_submission(
    *,
    submission_id,
    reviewer,
    membership,
    reason,
):
    written_reason = _decision_reason(reason)
    validation_error = None
    result = None
    with transaction.atomic():
        submission = (
            PlayerRegistration.objects.select_for_update(of=("self",))
            .select_related(
                "union_workspace",
                "club",
                "team",
                "season_record__league",
                "union_player",
                "submitted_by",
            )
            .get(pk=submission_id)
        )
        membership = _require_review_access(
            reviewer=reviewer,
            membership=membership,
            submission=submission,
            permission="union.players.approve",
        )
        if submission.submission_status == PlayerRegistration.SubmissionStatus.APPROVED:
            registration = _resolve_idempotent_registration(submission)
            eligibility_result = create_pending_eligibilities_for_submission(
                submission=submission,
                authoritative_registration=registration,
                actor=reviewer,
                membership=membership,
            )
            return _review_result(
                submission,
                registration,
                idempotent_replay=True,
                eligibility_result=eligibility_result,
            )
        if (
            submission.submission_status
            != PlayerRegistration.SubmissionStatus.UNDER_UNION_REVIEW
        ):
            raise ValidationError(
                {
                    "submission_status": (
                        "Only applications under Union review may be approved."
                    )
                }
            )

        player = (
            UnionPlayer.objects.select_for_update()
            .filter(pk=submission.union_player_id)
            .first()
        )
        active_registrations = (
            list(
                UnionPlayerRegistration.objects.select_for_update(of=("self",))
                .filter(
                    workspace=membership.workspace,
                    player=player,
                    status=UnionPlayerRegistration.Status.ACTIVE,
                )
                .select_related("season", "club")
                .order_by("id")
            )
            if player is not None
            else []
        )
        validation_result = validate_player_registration_for_union_review(
            submission=submission,
            reviewer=reviewer,
            membership=membership,
            required_permission="union.players.approve",
            final_decision=True,
        )
        _store_validation_result(
            submission=submission,
            actor=reviewer,
            validation_result=validation_result,
        )
        if validation_result["blocking_errors"]:
            validation_error = SubmissionValidationError(validation_result)
        else:
            now = timezone.now()
            registration_type = submission.registration_type
            previous_registration = None
            if registration_type in {
                PlayerRegistration.RegistrationType.FIRST_REGISTRATION,
                PlayerRegistration.RegistrationType.FREE_AGENT_REGISTRATION,
            }:
                registration = UnionPlayerRegistration.objects.create(
                    workspace=membership.workspace,
                    player=player,
                    club=submission.club,
                    team=submission.team,
                    season=submission.season_record,
                    source_registration=submission,
                    status=UnionPlayerRegistration.Status.ACTIVE,
                    registration_type=registration_type,
                    effective_from=submission.registered_date,
                    effective_to=submission.expiry_date,
                    approved_by=reviewer,
                    approved_at=now,
                    decision_reason=written_reason,
                )
                if player.status in {
                    UnionPlayer.Status.PROVISIONAL,
                    UnionPlayer.Status.PENDING_VERIFICATION,
                }:
                    player.status = UnionPlayer.Status.APPROVED
                    player.identity_verified_by = reviewer
                    player.identity_verified_at = now
                    player.save(
                        update_fields=[
                            "status",
                            "identity_verified_by",
                            "identity_verified_at",
                            "updated_at",
                        ]
                    )
                authoritative_action = "union_player_registration.created"
            elif (
                registration_type == PlayerRegistration.RegistrationType.SEASON_RENEWAL
            ):
                previous_registration = active_registrations[0]
                previous_registration.status = UnionPlayerRegistration.Status.EXPIRED
                previous_registration.effective_to = (
                    submission.registered_date - timedelta(days=1)
                )
                previous_registration.save(
                    update_fields=["status", "effective_to", "updated_at"]
                )
                registration = UnionPlayerRegistration.objects.create(
                    workspace=membership.workspace,
                    player=player,
                    club=submission.club,
                    team=submission.team,
                    season=submission.season_record,
                    source_registration=submission,
                    status=UnionPlayerRegistration.Status.ACTIVE,
                    registration_type=registration_type,
                    effective_from=submission.registered_date,
                    effective_to=submission.expiry_date,
                    approved_by=reviewer,
                    approved_at=now,
                    decision_reason=written_reason,
                    predecessor=previous_registration,
                )
                authoritative_action = "union_player_registration.renewed"
            else:
                registration = active_registrations[0]
                authoritative_action = None

            submission.submission_status = PlayerRegistration.SubmissionStatus.APPROVED
            submission.status = PlayerRegistration.RegistrationStatus.ACTIVE
            submission.assigned_reviewer = reviewer
            submission.reviewed_at = now
            submission.union_decision_reason = written_reason
            submission.save(
                update_fields=[
                    "submission_status",
                    "status",
                    "assigned_reviewer",
                    "reviewed_at",
                    "union_decision_reason",
                    "updated_at",
                ]
            )
            approval_metadata = {
                "submission_id": submission.id,
                "authoritative_registration_id": registration.id,
                "player_id": player.id,
                "club_id": submission.club_id,
                "season_id": submission.season_record_id,
                "registration_type": registration_type,
                "previous_registration_id": (
                    previous_registration.id if previous_registration else None
                ),
                "idempotent_replay": False,
            }
            log_union_audit_event(
                workspace=membership.workspace,
                actor=reviewer,
                action="player_registration.approved",
                target=submission,
                metadata=approval_metadata,
            )
            if authoritative_action:
                log_union_audit_event(
                    workspace=membership.workspace,
                    actor=reviewer,
                    action=authoritative_action,
                    target=registration,
                    metadata=approval_metadata,
                )
            _schedule_club_notification(
                submission,
                title="Player registration approved",
                message="The Union approved a player registration submission.",
            )
            eligibility_result = create_pending_eligibilities_for_submission(
                submission=submission,
                authoritative_registration=registration,
                actor=reviewer,
                membership=membership,
            )
            result = _review_result(
                submission,
                registration,
                idempotent_replay=False,
                eligibility_result=eligibility_result,
            )
    if validation_error is not None:
        raise validation_error
    return result
