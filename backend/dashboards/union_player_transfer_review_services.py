"""Union review and authoritative completion for maintained player transfers."""

from functools import partial

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import Notification, NotificationPreference, User
from accounts.services import create_in_app_notification

from .models import (
    UnionPlayer,
    UnionPlayerCompetitionEligibility,
    UnionPlayerRegistration,
    UnionPlayerTransfer,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
from .union_governance import log_union_audit_event
from .union_player_transfer_services import (
    UNION_TRANSFER_PERMISSION,
    _audit_metadata,
    _build_player_transfer_validation,
    _validation_item,
)
from .union_scopes import scope_allows

AFFECTED_ELIGIBILITY_STATUSES = {
    UnionPlayerCompetitionEligibility.Status.PENDING,
    UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
    UnionPlayerCompetitionEligibility.Status.SUSPENDED,
}
COMPLETABLE_TRANSFER_TYPES = {"PERMANENT", "FREE_TRANSFER", "LOAN"}


def _is_super_admin(user):
    return bool(
        user
        and (
            getattr(user, "is_superuser", False)
            or getattr(user, "role", None) == User.Role.SUPER_ADMIN
        )
    )


def _reason(value):
    written = str(value or "").strip()
    if not written:
        raise ValidationError({"reason": "A written reason is required."})
    return written


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
    if (
        not _is_super_admin(reviewer)
        and UNION_TRANSFER_PERMISSION not in active.effective_permissions
    ):
        raise ValidationError(
            {"permission": f"Reviewer requires {UNION_TRANSFER_PERMISSION}."}
        )
    return active


def _affected_eligibilities(transfer, *, lock=False):
    queryset = (
        UnionPlayerCompetitionEligibility.objects.filter(
            registration_id=transfer.source_registration_id,
            status__in=AFFECTED_ELIGIBILITY_STATUSES,
        )
        .select_related(
            "competition_identity",
            "competition_edition__identity",
            "competition_edition__competition__league",
            "season",
        )
        .order_by("competition_edition_id", "id")
    )
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    return queryset


def _scope_allows_transfer(membership, transfer, eligibilities):
    if transfer.workspace_id != membership.workspace_id:
        return False
    if _is_super_admin(membership.user):
        return True
    club_ids = {
        transfer.source_registration.club_id,
        transfer.destination_club_id,
    }
    if any(not scope_allows(membership, "club", club_id) for club_id in club_ids):
        return False
    for eligibility in eligibilities:
        if not scope_allows(
            membership,
            "competition_identity",
            eligibility.competition_identity_id,
        ) or not scope_allows(
            membership,
            "competition_edition",
            eligibility.competition_edition_id,
        ):
            return False
    return True


def _require_review_access(*, reviewer, membership, transfer):
    active = _active_membership(reviewer=reviewer, membership=membership)
    eligibilities = list(_affected_eligibilities(transfer))
    if not _scope_allows_transfer(active, transfer, eligibilities):
        raise ValidationError(
            {"scope": "Transfer is outside the selected workspace or resource scope."}
        )
    return active


def _require_independent_reviewer(transfer, reviewer):
    if transfer.initiated_by_id == getattr(reviewer, "pk", None):
        raise ValidationError(
            {"reviewer": "A transfer initiator cannot make the Union decision."}
        )


def _locked_transfer(transfer_id):
    transfer = (
        UnionPlayerTransfer.objects.select_for_update(of=("self",))
        .select_related(
            "workspace__related_union",
            "player__user",
            "source_registration__club__admin",
            "source_registration__player",
            "destination_club__admin",
            "destination_team",
            "initiated_by",
            "destination_registration",
        )
        .get(pk=transfer_id)
    )
    transfer.source_registration = (
        UnionPlayerRegistration.objects.select_for_update(of=("self",))
        .select_related("workspace", "player", "club", "team", "season")
        .get(pk=transfer.source_registration_id)
    )
    return transfer


def _append_validation(result, bucket, item):
    if not any(existing["code"] == item["code"] for existing in result[bucket]):
        result[bucket].append(item)


def validate_player_transfer_for_union_review(
    *,
    transfer,
    reviewer,
    membership,
):
    """Return fresh shared data checks plus Union decision-specific checks."""

    result = _build_player_transfer_validation(transfer)

    def error(code, field, message):
        _append_validation(
            result,
            "blocking_errors",
            _validation_item(code, field, message, "ERROR"),
        )

    def warning(code, field, message):
        _append_validation(
            result,
            "review_warnings",
            _validation_item(code, field, message, "WARNING"),
        )

    def passed(code, field, message):
        _append_validation(
            result,
            "passed_checks",
            _validation_item(code, field, message, "PASS"),
        )

    active = None
    if membership is not None and getattr(membership, "pk", None):
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
        error(
            "UNION_MEMBERSHIP_INVALID",
            "workspace",
            "An active Union membership is required.",
        )
    else:
        passed("UNION_MEMBERSHIP_VALID", "workspace", "Union membership is active.")

    if active is not None and (
        _is_super_admin(reviewer)
        or UNION_TRANSFER_PERMISSION in active.effective_permissions
    ):
        passed(
            "UNION_TRANSFER_PERMISSION_VALID",
            None,
            f"Reviewer has {UNION_TRANSFER_PERMISSION}.",
        )
    else:
        error(
            "UNION_TRANSFER_PERMISSION_DENIED",
            None,
            f"Reviewer requires {UNION_TRANSFER_PERMISSION}.",
        )

    affected = list(_affected_eligibilities(transfer))
    if active is None or transfer.workspace_id != active.workspace_id:
        error(
            "TRANSFER_WORKSPACE_INVALID",
            "workspace",
            "Transfer must belong to the selected workspace.",
        )
    elif not _scope_allows_transfer(active, transfer, affected):
        error(
            "TRANSFER_RESOURCE_SCOPE_DENIED",
            "scope",
            "Source Club, destination Club, and affected competitions must be in scope.",
        )
    else:
        passed(
            "TRANSFER_RESOURCE_SCOPE_VALID",
            "scope",
            "Transfer resources are within the reviewer scope.",
        )

    if transfer.status != UnionPlayerTransfer.Status.UNDER_UNION_REVIEW:
        error(
            "TRANSFER_NOT_UNDER_UNION_REVIEW",
            "status",
            "Only a transfer under Union review may receive a decision.",
        )
    else:
        passed(
            "TRANSFER_UNDER_UNION_REVIEW",
            "status",
            "Transfer is under Union review.",
        )

    if transfer.player_consent_status != (
        UnionPlayerTransfer.PlayerConsentStatus.CONSENTED
    ):
        error(
            "PLAYER_CONSENT_REQUIRED",
            "player_consent_status",
            "Maintained player consent is required.",
        )
    else:
        passed(
            "PLAYER_CONSENT_VALID",
            "player_consent_status",
            "Player consent is recorded.",
        )

    valid_source_responses = {
        UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED,
        UnionPlayerTransfer.SourceClubResponseStatus.OBJECTED,
    }
    if transfer.source_club_response_status not in valid_source_responses:
        error(
            "SOURCE_CLUB_RESPONSE_REQUIRED",
            "source_club_response_status",
            "A maintained source Club response is required.",
        )
    elif (
        transfer.source_club_response_status
        == UnionPlayerTransfer.SourceClubResponseStatus.OBJECTED
    ):
        warning(
            "SOURCE_CLUB_OBJECTED",
            "source_club_response_status",
            "The source Club objected; the Union must assess the evidence.",
        )
    else:
        passed(
            "SOURCE_CLUB_RESPONSE_VALID",
            "source_club_response_status",
            "Source Club acknowledgement is recorded.",
        )

    if transfer.initiated_by_id == getattr(reviewer, "pk", None):
        error(
            "REVIEWER_IS_INITIATOR",
            "reviewer",
            "A transfer initiator cannot make the Union decision.",
        )
    else:
        passed(
            "REVIEWER_INDEPENDENT",
            "reviewer",
            "Reviewer did not initiate the transfer.",
        )

    if transfer.transfer_type not in COMPLETABLE_TRANSFER_TYPES:
        error(
            "TRANSFER_TYPE_COMPLETION_UNSUPPORTED",
            "transfer_type",
            "Transfer type is not supported by the maintained decision workflow.",
        )
    else:
        passed(
            "TRANSFER_TYPE_COMPLETABLE",
            "transfer_type",
            "Transfer type supports authoritative completion.",
        )
    if (
        transfer.transfer_type == "LOAN"
        and transfer.loan_end_on is not None
        and transfer.loan_end_on > transfer.effective_on
        and (
            transfer.source_registration.effective_to is None
            or transfer.loan_end_on < transfer.source_registration.effective_to
        )
    ):
        passed(
            "LOAN_PERIOD_VALID",
            "loan_end_on",
            "Loan period fits within the source registration.",
        )

    if transfer.effective_on > timezone.localdate():
        warning(
            "TRANSFER_ACTIVATION_SCHEDULED",
            "effective_on",
            "The approved transfer will activate on its effective date.",
        )

    conflicting_active = (
        UnionPlayerRegistration.objects.filter(
            player=transfer.player,
            status=UnionPlayerRegistration.Status.ACTIVE,
        )
        .exclude(pk=transfer.source_registration_id)
        .exists()
    )
    if conflicting_active:
        error(
            "CONFLICTING_ACTIVE_REGISTRATION",
            "source_registration",
            "Another active registration exists for this player.",
        )

    conflicting_successor = (
        UnionPlayerTransfer.objects.filter(
            workspace=transfer.workspace,
            player=transfer.player,
            status=UnionPlayerTransfer.Status.COMPLETED,
        )
        .exclude(pk=transfer.pk)
        .exists()
    )
    if conflicting_successor:
        error(
            "CONFLICTING_COMPLETED_TRANSFER",
            "destination_registration",
            "Another completed transfer already created a successor.",
        )
    if transfer.destination_registration_id is not None:
        error(
            "TRANSFER_SUCCESSOR_ALREADY_LINKED",
            "destination_registration",
            "An incomplete transfer cannot already have a destination registration.",
        )

    if affected:
        warning(
            "SOURCE_ELIGIBILITY_REVIEW_REQUIRED",
            "source_registration",
            "Source registration has non-terminal competition eligibility.",
        )
    for eligibility in affected:
        if (
            eligibility.workspace_id != transfer.workspace_id
            or eligibility.player_id != transfer.player_id
            or eligibility.registration_id != transfer.source_registration_id
            or eligibility.club_id != transfer.source_registration.club_id
        ):
            error(
                "SOURCE_ELIGIBILITY_RELATIONSHIP_INVALID",
                "source_registration",
                "Affected eligibility must belong to the source registration.",
            )
        if (
            eligibility.competition_identity.union_id
            != transfer.workspace.related_union_id
            or eligibility.competition_edition.identity_id
            != eligibility.competition_identity_id
            or eligibility.competition_edition.competition.league.union_id
            != transfer.workspace.related_union_id
        ):
            error(
                "SOURCE_ELIGIBILITY_COMPETITION_INVALID",
                "competition_edition",
                "Affected eligibility competition must belong to the workspace Union.",
            )
    result["evaluated_at"] = timezone.now().isoformat()
    return result


class TransferReviewValidationError(ValidationError):
    def __init__(self, automatic_validation):
        super().__init__(
            {"detail": "Player transfer contains blocking Union review errors."}
        )
        self.automatic_validation = automatic_validation


def _store_review_validation(transfer, reviewer, validation):
    transfer.automatic_validation = validation
    transfer.save(update_fields=["automatic_validation", "updated_at"])
    log_union_audit_event(
        workspace=transfer.workspace,
        actor=reviewer,
        action="union_player_transfer.validation_completed",
        target=transfer,
        metadata={
            **_audit_metadata(transfer),
            "blocking_error_count": len(validation["blocking_errors"]),
            "review_warning_count": len(validation["review_warnings"]),
            "validation_version": validation["version"],
        },
    )


def _notification_user_ids(transfer):
    return {
        user_id
        for user_id in (
            transfer.initiated_by_id,
            transfer.player.user_id,
            transfer.source_registration.club.admin_id,
            transfer.destination_club.admin_id,
        )
        if user_id
    }


def _notify_user(user_id, transfer_id, title, message):
    transfer = (
        UnionPlayerTransfer.objects.filter(pk=transfer_id)
        .select_related("source_registration")
        .first()
    )
    if transfer is None:
        return
    try:
        user = User.objects.get(pk=user_id)
        create_in_app_notification(
            user=user,
            event_type=NotificationPreference.EventType.GOVERNANCE,
            category=Notification.Category.GOVERNANCE,
            title=title,
            message=message,
            action_url="",
            metadata={
                "transfer_id": transfer.id,
                "player_id": transfer.player_id,
                "source_club_id": transfer.source_registration.club_id,
                "destination_club_id": transfer.destination_club_id,
                "status": transfer.status,
                "destination_registration_id": transfer.destination_registration_id,
                "effective_on": transfer.effective_on.isoformat(),
            },
        )
    except Exception:
        # Post-commit delivery cannot reverse a completed decision.
        return


def _schedule_notifications(transfer, *, reviewer, title, message):
    for user_id in sorted(_notification_user_ids(transfer)):
        if user_id == getattr(reviewer, "pk", None):
            continue
        transaction.on_commit(
            partial(
                _notify_user,
                user_id,
                transfer.id,
                title,
                message,
            )
        )


@transaction.atomic
def request_player_transfer_changes(
    *,
    transfer_id,
    reviewer,
    membership,
    reason,
):
    written_reason = _reason(reason)
    transfer = _locked_transfer(transfer_id)
    membership = _require_review_access(
        reviewer=reviewer,
        membership=membership,
        transfer=transfer,
    )
    _require_independent_reviewer(transfer, reviewer)
    if transfer.status != UnionPlayerTransfer.Status.UNDER_UNION_REVIEW:
        raise ValidationError(
            {"status": "Only a transfer under Union review may request changes."}
        )
    previous_status = transfer.status
    transfer.status = UnionPlayerTransfer.Status.CHANGES_REQUESTED
    transfer.change_request_reason = written_reason
    transfer.reviewed_by = reviewer
    transfer.reviewed_at = timezone.now()
    transfer.save(
        update_fields=[
            "status",
            "change_request_reason",
            "reviewed_by",
            "reviewed_at",
            "updated_at",
        ]
    )
    log_union_audit_event(
        workspace=membership.workspace,
        actor=reviewer,
        action="union_player_transfer.changes_requested",
        target=transfer,
        metadata=_audit_metadata(transfer, previous_status=previous_status),
    )
    _schedule_notifications(
        transfer,
        reviewer=reviewer,
        title="Player transfer changes requested",
        message="The Union requested changes to a player transfer.",
    )
    return transfer


@transaction.atomic
def reject_player_transfer(
    *,
    transfer_id,
    reviewer,
    membership,
    reason,
):
    written_reason = _reason(reason)
    transfer = _locked_transfer(transfer_id)
    membership = _require_review_access(
        reviewer=reviewer,
        membership=membership,
        transfer=transfer,
    )
    _require_independent_reviewer(transfer, reviewer)
    if transfer.status != UnionPlayerTransfer.Status.UNDER_UNION_REVIEW:
        raise ValidationError(
            {"status": "Only a transfer under Union review may be rejected."}
        )
    validation = validate_player_transfer_for_union_review(
        transfer=transfer,
        reviewer=reviewer,
        membership=membership,
    )
    _store_review_validation(transfer, reviewer, validation)
    previous_status = transfer.status
    transfer.status = UnionPlayerTransfer.Status.REJECTED
    transfer.reviewed_by = reviewer
    transfer.reviewed_at = timezone.now()
    transfer.decision_reason = written_reason
    transfer.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "decision_reason",
            "updated_at",
        ]
    )
    log_union_audit_event(
        workspace=membership.workspace,
        actor=reviewer,
        action="union_player_transfer.rejected",
        target=transfer,
        metadata=_audit_metadata(transfer, previous_status=previous_status),
    )
    _schedule_notifications(
        transfer,
        reviewer=reviewer,
        title="Player transfer rejected",
        message="The Union rejected a player transfer.",
    )
    return {
        "transfer": transfer,
        "automatic_validation": validation,
    }


def _safe_warnings(warnings):
    safe = []
    for item in warnings or []:
        if not isinstance(item, dict):
            continue
        safe.append(
            {
                key: item[key]
                for key in ("code", "field", "message", "severity")
                if key in item
            }
        )
    return safe


def _eligibility_metadata(eligibility, *, previous_status=None):
    return {
        "eligibility_id": eligibility.id,
        "source_transfer_id": eligibility.source_transfer_id,
        "authoritative_registration_id": eligibility.registration_id,
        "player_id": eligibility.player_id,
        "club_id": eligibility.club_id,
        "competition_identity_id": eligibility.competition_identity_id,
        "competition_edition_id": eligibility.competition_edition_id,
        "season_id": eligibility.season_id,
        "previous_status": previous_status,
        "new_status": eligibility.status,
    }


def _verify_completed_transfer(transfer):
    destination = (
        UnionPlayerRegistration.objects.select_for_update(of=("self",))
        .filter(pk=transfer.destination_registration_id)
        .first()
    )
    if (
        destination is None
        or destination.workspace_id != transfer.workspace_id
        or destination.player_id != transfer.player_id
        or destination.club_id != transfer.destination_club_id
        or destination.predecessor_id != transfer.source_registration_id
        or destination.effective_from != transfer.effective_on
    ):
        raise ValidationError(
            {"status": "Completed transfer has inconsistent successor evidence."}
        )
    destination_eligibilities = list(
        UnionPlayerCompetitionEligibility.objects.select_for_update(of=("self",))
        .filter(source_transfer=transfer)
        .select_related("competition_identity", "competition_edition")
        .order_by("competition_edition_id", "id")
    )
    if any(
        eligibility.workspace_id != transfer.workspace_id
        or eligibility.player_id != transfer.player_id
        or eligibility.registration_id != destination.id
        or eligibility.club_id != transfer.destination_club_id
        for eligibility in destination_eligibilities
    ):
        raise ValidationError(
            {"status": "Completed transfer has inconsistent eligibility evidence."}
        )
    return destination, destination_eligibilities


def _result(
    transfer,
    *,
    destination_registration,
    destination_eligibilities,
    idempotent_replay,
    activation_scheduled=False,
):
    return {
        "transfer": transfer,
        "source_registration": transfer.source_registration,
        "destination_registration": destination_registration,
        "destination_eligibilities": destination_eligibilities,
        "activation_scheduled": activation_scheduled,
        "idempotent_replay": idempotent_replay,
    }


def approve_player_transfer_decision(
    *,
    transfer_id,
    reviewer,
    membership,
    reason,
):
    written_reason = _reason(reason)
    validation_error = None
    result = None
    with transaction.atomic():
        transfer = _locked_transfer(transfer_id)
        membership = _require_review_access(
            reviewer=reviewer,
            membership=membership,
            transfer=transfer,
        )
        _require_independent_reviewer(transfer, reviewer)

        from .union_player_transfer_activation_services import (
            activate_approved_player_transfer,
            build_player_transfer_activation_plan,
            verify_scheduled_transfer_approval,
        )

        if transfer.status == UnionPlayerTransfer.Status.APPROVED:
            verify_scheduled_transfer_approval(transfer)
            return _result(
                transfer,
                destination_registration=None,
                destination_eligibilities=[],
                activation_scheduled=True,
                idempotent_replay=True,
            )
        if transfer.status in {
            UnionPlayerTransfer.Status.COMPLETED,
            UnionPlayerTransfer.Status.LOAN_ACTIVE,
        }:
            activated = activate_approved_player_transfer(
                transfer_id=transfer.id,
                as_of=timezone.localdate(),
            )
            scoped_eligibilities = activated.get("destination_eligibilities")
            if scoped_eligibilities is None:
                scoped_eligibilities = activated.get("return_eligibilities", [])
            if not _scope_allows_transfer(
                membership,
                transfer,
                scoped_eligibilities,
            ):
                raise ValidationError(
                    {"scope": "Activated transfer evidence is outside reviewer scope."}
                )
            return activated
        if transfer.status != UnionPlayerTransfer.Status.UNDER_UNION_REVIEW:
            raise ValidationError(
                {"status": "Only a transfer under Union review may be approved."}
            )

        transfer.player = (
            UnionPlayer.objects.select_for_update(of=("self",))
            .select_related("user")
            .get(pk=transfer.player_id)
        )
        list(
            UnionPlayerRegistration.objects.select_for_update(of=("self",))
            .filter(
                player=transfer.player,
                status=UnionPlayerRegistration.Status.ACTIVE,
            )
            .order_by("id")
        )
        affected_eligibilities = list(_affected_eligibilities(transfer, lock=True))

        validation = validate_player_transfer_for_union_review(
            transfer=transfer,
            reviewer=reviewer,
            membership=membership,
        )
        _store_review_validation(transfer, reviewer, validation)
        if validation["blocking_errors"]:
            validation_error = TransferReviewValidationError(validation)
        else:
            now = timezone.now()
            previous_transfer_status = transfer.status
            transfer.source_registration_original_effective_to = (
                transfer.source_registration.effective_to
            )
            transfer.activation_plan = build_player_transfer_activation_plan(
                transfer,
                affected_eligibilities,
                original_effective_to=(
                    transfer.source_registration_original_effective_to
                ),
            )
            transfer.status = UnionPlayerTransfer.Status.APPROVED
            transfer.reviewed_by = reviewer
            transfer.reviewed_at = now
            transfer.decision_reason = written_reason
            transfer.save(
                update_fields=[
                    "source_registration_original_effective_to",
                    "activation_plan",
                    "status",
                    "reviewed_by",
                    "reviewed_at",
                    "decision_reason",
                    "updated_at",
                ]
            )
            transfer_metadata = {
                **_audit_metadata(
                    transfer,
                    previous_status=previous_transfer_status,
                ),
                "effective_on": transfer.effective_on.isoformat(),
                "loan_end_on": (
                    transfer.loan_end_on.isoformat()
                    if transfer.loan_end_on is not None
                    else None
                ),
            }
            log_union_audit_event(
                workspace=transfer.workspace,
                actor=reviewer,
                action="union_player_transfer.approved",
                target=transfer,
                metadata=transfer_metadata,
            )
            if transfer.effective_on > timezone.localdate():
                log_union_audit_event(
                    workspace=transfer.workspace,
                    actor=reviewer,
                    action="union_player_transfer.activation_scheduled",
                    target=transfer,
                    metadata=transfer_metadata,
                )
                _schedule_notifications(
                    transfer,
                    reviewer=reviewer,
                    title="Player transfer approved and scheduled",
                    message=(
                        "The Union approved the transfer. Registration movement "
                        "will occur on its effective date."
                    ),
                )
                result = _result(
                    transfer,
                    destination_registration=None,
                    destination_eligibilities=[],
                    activation_scheduled=True,
                    idempotent_replay=False,
                )
            else:
                result = activate_approved_player_transfer(
                    transfer_id=transfer.id,
                    as_of=timezone.localdate(),
                )
    if validation_error is not None:
        raise validation_error
    return result
