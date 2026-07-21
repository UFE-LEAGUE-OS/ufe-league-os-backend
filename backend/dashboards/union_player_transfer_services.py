"""Destination-Club player-transfer submission lifecycle."""

from functools import partial

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import Notification, NotificationPreference, User
from accounts.rbac import get_user_clubs, has_role_permission
from accounts.services import create_in_app_notification

from .models import (
    ClubAffiliation,
    UnionAuditEvent,
    UnionPlayer,
    UnionPlayerCompetitionEligibility,
    UnionPlayerRegistration,
    UnionPlayerTransfer,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
from .union_governance import log_union_audit_event

CLUB_TRANSFER_PERMISSION = "club.transfers.manage"
UNION_TRANSFER_PERMISSION = "union.transfers.approve"
SUPPORTED_TRANSFER_TYPES = {"PERMANENT", "LOAN", "FREE_TRANSFER"}
NON_TERMINAL_STATUSES = {
    UnionPlayerTransfer.Status.DRAFT,
    UnionPlayerTransfer.Status.SUBMITTED,
    UnionPlayerTransfer.Status.PLAYER_CONSENT_REQUIRED,
    UnionPlayerTransfer.Status.SOURCE_CLUB_RESPONSE_REQUIRED,
    UnionPlayerTransfer.Status.UNDER_AUTOMATIC_REVIEW,
    UnionPlayerTransfer.Status.UNDER_UNION_REVIEW,
    UnionPlayerTransfer.Status.CHANGES_REQUESTED,
}
SUBMITTED_ACTIVE_STATUSES = {
    UnionPlayerTransfer.Status.SUBMITTED,
    UnionPlayerTransfer.Status.PLAYER_CONSENT_REQUIRED,
    UnionPlayerTransfer.Status.SOURCE_CLUB_RESPONSE_REQUIRED,
    UnionPlayerTransfer.Status.UNDER_AUTOMATIC_REVIEW,
    UnionPlayerTransfer.Status.UNDER_UNION_REVIEW,
    UnionPlayerTransfer.Status.CHANGES_REQUESTED,
}


def _is_super_admin(actor):
    return bool(
        actor
        and (
            getattr(actor, "is_superuser", False)
            or getattr(actor, "role", None) == User.Role.SUPER_ADMIN
        )
    )


def _actor_manages_club(actor, club):
    return _is_super_admin(actor) or (
        bool(actor)
        and getattr(actor, "is_authenticated", False)
        and get_user_clubs(actor).filter(pk=club.pk).exists()
        and has_role_permission(actor, CLUB_TRANSFER_PERMISSION)
    )


def _require_club_actor(actor, club, field):
    if not _actor_manages_club(actor, club):
        raise ValidationError(
            {field: "Actor must administer this Club with transfer permission."}
        )


def _active_affiliation(workspace, club):
    return (
        ClubAffiliation.objects.filter(
            workspace=workspace,
            club=club,
            status=ClubAffiliation.Status.ACTIVE,
        )
        .filter(Q(expires_on__isnull=True) | Q(expires_on__gte=timezone.localdate()))
        .exists()
    )


def _validate_workspace_and_clubs(workspace, source_club, destination_club):
    if (
        workspace is None
        or workspace.status != UnionWorkspace.Status.ACTIVE
        or workspace.related_union_id is None
    ):
        raise ValidationError(
            {"workspace": "An active Union-linked workspace is required."}
        )
    if source_club.pk == destination_club.pk:
        raise ValidationError(
            {"destination_club": "Destination Club must differ from source Club."}
        )
    if not _active_affiliation(workspace, source_club):
        raise ValidationError(
            {"source_club": "Source Club needs an active workspace affiliation."}
        )
    if not _active_affiliation(workspace, destination_club):
        raise ValidationError(
            {
                "destination_club": (
                    "Destination Club needs an active workspace affiliation."
                )
            }
        )


def _validate_transfer_type_and_dates(
    *,
    source_registration,
    effective_on,
    transfer_type,
    loan_end_on,
):
    if transfer_type == "END_OF_LOAN":
        raise ValidationError(
            {
                "transfer_type": (
                    "End-of-loan processing requires the dedicated "
                    "loan-return workflow."
                )
            }
        )
    if transfer_type not in SUPPORTED_TRANSFER_TYPES:
        raise ValidationError({"transfer_type": "Unsupported transfer type."})
    if effective_on is None or effective_on <= source_registration.effective_from:
        raise ValidationError(
            {
                "effective_on": (
                    "Transfer effective date must follow the source registration."
                )
            }
        )
    if (
        source_registration.effective_to
        and effective_on > source_registration.effective_to
    ):
        raise ValidationError(
            {
                "effective_on": (
                    "Transfer effective date cannot exceed registration expiry."
                )
            }
        )
    if transfer_type == "LOAN":
        if loan_end_on is None or loan_end_on <= effective_on:
            raise ValidationError(
                {"loan_end_on": "A loan end date after its effective date is required."}
            )
        if (
            source_registration.effective_to is not None
            and loan_end_on >= source_registration.effective_to
        ):
            raise ValidationError(
                {
                    "loan_end_on": (
                        "Loan end date must precede the source registration expiry."
                    )
                }
            )
    elif loan_end_on is not None:
        raise ValidationError(
            {"loan_end_on": "Loan end date is only valid for a loan transfer."}
        )


def _validate_destination_team(destination_team, destination_club):
    if destination_team is not None and destination_team.club_id != destination_club.pk:
        raise ValidationError(
            {"destination_team": "Destination team must belong to destination Club."}
        )


def _validate_registration_and_player(workspace, source_registration):
    if source_registration.workspace_id != workspace.pk:
        raise ValidationError(
            {"source_registration": "Registration must belong to the workspace."}
        )
    if source_registration.status != UnionPlayerRegistration.Status.ACTIVE:
        raise ValidationError(
            {"source_registration": "Source registration must be active."}
        )
    if source_registration.player.union_id != workspace.related_union_id:
        raise ValidationError({"player": "Player must belong to the workspace Union."})
    if source_registration.player.status != UnionPlayer.Status.APPROVED:
        raise ValidationError({"player": "Player identity must be approved."})


def _validate_transfer_structure(transfer):
    _validate_workspace_and_clubs(
        transfer.workspace,
        transfer.source_registration.club,
        transfer.destination_club,
    )
    _validate_registration_and_player(
        transfer.workspace,
        transfer.source_registration,
    )
    if transfer.source_registration.player_id != transfer.player_id:
        raise ValidationError(
            {"player": "Source registration must belong to the transfer player."}
        )
    _validate_destination_team(transfer.destination_team, transfer.destination_club)
    _validate_transfer_type_and_dates(
        source_registration=transfer.source_registration,
        effective_on=transfer.effective_on,
        transfer_type=transfer.transfer_type,
        loan_end_on=transfer.loan_end_on,
    )


def _audit_metadata(transfer, *, previous_status=None):
    return {
        "transfer_id": transfer.id,
        "player_id": transfer.player_id,
        "source_registration_id": transfer.source_registration_id,
        "source_club_id": transfer.source_registration.club_id,
        "destination_club_id": transfer.destination_club_id,
        "destination_team_id": transfer.destination_team_id,
        "transfer_type": transfer.transfer_type,
        "previous_status": previous_status,
        "new_status": transfer.status,
        "submission_revision": transfer.submission_revision,
    }


def _notify_user(user_id, transfer_id, title, message):
    if not user_id:
        return
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
            action_url="/dashboard/club-admin",
            metadata={
                "transfer_id": transfer.id,
                "player_id": transfer.player_id,
                "source_club_id": transfer.source_registration.club_id,
                "destination_club_id": transfer.destination_club_id,
                "status": transfer.status,
            },
        )
    except Exception:
        # Post-commit notification failures do not reverse workflow state.
        return


def _schedule_notifications(transfer, users, *, actor, title, message):
    seen = set()
    for user in users:
        user_id = getattr(user, "pk", None)
        if not user_id or user_id == getattr(actor, "pk", None) or user_id in seen:
            continue
        seen.add(user_id)
        transaction.on_commit(
            partial(
                _notify_user,
                user_id,
                transfer.id,
                title,
                message,
            )
        )


def _locked_transfer(transfer_id):
    transfer = (
        UnionPlayerTransfer.objects.select_for_update(of=("self",))
        .select_related(
            "workspace__related_union",
            "player__user",
            "source_registration__club__admin",
            "source_registration__player",
            "destination_club",
            "destination_team",
            "initiated_by",
        )
        .get(pk=transfer_id)
    )
    transfer.source_registration = (
        UnionPlayerRegistration.objects.select_for_update(of=("self",))
        .select_related("workspace", "player", "club")
        .get(pk=transfer.source_registration_id)
    )
    return transfer


@transaction.atomic
def create_player_transfer_draft(
    *,
    actor,
    workspace,
    source_registration,
    destination_club,
    destination_team=None,
    effective_on,
    transfer_type,
    loan_end_on=None,
    documents=None,
    fee_status="",
):
    source_registration = (
        UnionPlayerRegistration.objects.select_for_update(of=("self",))
        .select_related("workspace__related_union", "player", "club")
        .get(pk=source_registration.pk)
    )
    _require_club_actor(actor, destination_club, "destination_club")
    _validate_workspace_and_clubs(
        workspace,
        source_registration.club,
        destination_club,
    )
    _validate_registration_and_player(workspace, source_registration)
    _validate_destination_team(destination_team, destination_club)
    _validate_transfer_type_and_dates(
        source_registration=source_registration,
        effective_on=effective_on,
        transfer_type=transfer_type,
        loan_end_on=loan_end_on,
    )
    duplicate = (
        UnionPlayerTransfer.objects.select_for_update(of=("self",))
        .filter(
            workspace=workspace,
            player=source_registration.player,
            status__in=NON_TERMINAL_STATUSES,
        )
        .exists()
    )
    if duplicate:
        raise ValidationError(
            {"player": "Another non-terminal transfer exists for this player."}
        )
    transfer = UnionPlayerTransfer.objects.create(
        workspace=workspace,
        player=source_registration.player,
        source_registration=source_registration,
        destination_club=destination_club,
        destination_team=destination_team,
        status=UnionPlayerTransfer.Status.DRAFT,
        effective_on=effective_on,
        transfer_type=transfer_type,
        loan_end_on=loan_end_on,
        initiated_by=actor,
        documents=list(documents or []),
        fee_status=str(fee_status or "").strip(),
        source_club_response_status=(
            UnionPlayerTransfer.SourceClubResponseStatus.PENDING
        ),
        player_consent_status=UnionPlayerTransfer.PlayerConsentStatus.PENDING,
    )
    log_union_audit_event(
        workspace=workspace,
        actor=actor,
        action="union_player_transfer.draft_created",
        target=transfer,
        metadata=_audit_metadata(transfer),
    )
    return transfer


@transaction.atomic
def update_player_transfer_draft(*, transfer_id, actor, updates):
    transfer = _locked_transfer(transfer_id)
    _require_club_actor(actor, transfer.destination_club, "destination_club")
    started_in_changes_requested = (
        transfer.status == UnionPlayerTransfer.Status.CHANGES_REQUESTED
    )
    if transfer.status not in {
        UnionPlayerTransfer.Status.DRAFT,
        UnionPlayerTransfer.Status.CHANGES_REQUESTED,
    }:
        raise ValidationError(
            {"status": "Only draft or changes-requested transfers may be updated."}
        )
    editable = {
        "destination_team",
        "effective_on",
        "transfer_type",
        "loan_end_on",
        "documents",
        "fee_status",
    }
    invalid_fields = sorted(set(updates) - editable)
    if invalid_fields:
        raise ValidationError(
            {
                "updates": (
                    "These fields are controlled by the workflow: "
                    + ", ".join(invalid_fields)
                )
            }
        )
    updates = dict(updates)
    if "fee_status" in updates:
        updates["fee_status"] = str(updates["fee_status"] or "").strip()
    if "documents" in updates:
        updates["documents"] = list(updates["documents"] or [])
    changed_terms = any(
        getattr(transfer, field) != value for field, value in updates.items()
    )
    for field, value in updates.items():
        setattr(transfer, field, value)
    _validate_transfer_structure(transfer)
    update_fields = list(updates)
    prerequisite_evidence_reset = started_in_changes_requested and changed_terms
    if prerequisite_evidence_reset:
        transfer.source_club_response_status = (
            UnionPlayerTransfer.SourceClubResponseStatus.PENDING
        )
        transfer.source_club_response = ""
        transfer.source_club_response_at = None
        transfer.source_club_responded_by = None
        transfer.player_consent_status = UnionPlayerTransfer.PlayerConsentStatus.PENDING
        transfer.player_consented_at = None
        transfer.player_consent_method = ""
        transfer.player_consent_recorded_by = None
        update_fields.extend(
            [
                "source_club_response_status",
                "source_club_response",
                "source_club_response_at",
                "source_club_responded_by",
                "player_consent_status",
                "player_consented_at",
                "player_consent_method",
                "player_consent_recorded_by",
            ]
        )
    transfer.save(update_fields=[*set(update_fields), "updated_at"])
    log_union_audit_event(
        workspace=transfer.workspace,
        actor=actor,
        action="union_player_transfer.draft_updated",
        target=transfer,
        metadata={
            **_audit_metadata(transfer),
            "prerequisite_evidence_reset": prerequisite_evidence_reset,
        },
    )
    return transfer


def _validation_item(code, field, message, severity):
    return {
        "code": code,
        "field": field,
        "message": message,
        "severity": severity,
    }


def _build_player_transfer_validation(transfer):
    blocking_errors = []
    review_warnings = []
    passed_checks = []
    capability_notes = []

    def error(code, field, message):
        if not any(item["code"] == code for item in blocking_errors):
            blocking_errors.append(_validation_item(code, field, message, "ERROR"))

    def warning(code, field, message):
        if not any(item["code"] == code for item in review_warnings):
            review_warnings.append(_validation_item(code, field, message, "WARNING"))

    def passed(code, field, message):
        passed_checks.append(_validation_item(code, field, message, "PASS"))

    workspace = transfer.workspace
    if workspace.status == UnionWorkspace.Status.ACTIVE and workspace.related_union_id:
        passed("WORKSPACE_VALID", "workspace", "Workspace is active and Union-linked.")
    else:
        error(
            "WORKSPACE_INVALID",
            "workspace",
            "An active Union-linked workspace is required.",
        )

    source_registration = transfer.source_registration
    source_club = source_registration.club
    if _active_affiliation(workspace, source_club):
        passed(
            "SOURCE_AFFILIATION_VALID",
            "source_registration",
            "Source Club affiliation is active.",
        )
    else:
        error(
            "SOURCE_AFFILIATION_INVALID",
            "source_registration",
            "Source Club affiliation must be active.",
        )
    if _active_affiliation(workspace, transfer.destination_club):
        passed(
            "DESTINATION_AFFILIATION_VALID",
            "destination_club",
            "Destination Club affiliation is active.",
        )
    else:
        error(
            "DESTINATION_AFFILIATION_INVALID",
            "destination_club",
            "Destination Club affiliation must be active.",
        )

    if source_registration.workspace_id != workspace.pk:
        error(
            "SOURCE_REGISTRATION_WORKSPACE_INVALID",
            "source_registration",
            "Source registration must belong to the workspace.",
        )
    if source_registration.status != UnionPlayerRegistration.Status.ACTIVE:
        error(
            "SOURCE_REGISTRATION_INACTIVE",
            "source_registration",
            "Source registration must be active.",
        )
    if source_registration.player_id != transfer.player_id:
        error(
            "SOURCE_REGISTRATION_PLAYER_INVALID",
            "player",
            "Source registration must belong to the transfer player.",
        )
    if source_registration.club_id == transfer.destination_club_id:
        error(
            "SOURCE_DESTINATION_CLUB_CONFLICT",
            "destination_club",
            "Destination Club must differ from source Club.",
        )

    player = transfer.player
    if player.union_id != workspace.related_union_id:
        error(
            "PLAYER_UNION_INVALID",
            "player",
            "Player must belong to the workspace Union.",
        )
    elif player.status != UnionPlayer.Status.APPROVED:
        error(
            f"PLAYER_{player.status}",
            "player",
            "Player identity must be approved.",
        )
    else:
        passed("PLAYER_APPROVED", "player", "Player identity is approved.")

    if (
        transfer.destination_team_id
        and transfer.destination_team.club_id != transfer.destination_club_id
    ):
        error(
            "DESTINATION_TEAM_INVALID",
            "destination_team",
            "Destination team must belong to destination Club.",
        )
    try:
        _validate_transfer_type_and_dates(
            source_registration=source_registration,
            effective_on=transfer.effective_on,
            transfer_type=transfer.transfer_type,
            loan_end_on=transfer.loan_end_on,
        )
    except ValidationError as exc:
        for field, messages in exc.message_dict.items():
            error(
                f"TRANSFER_{field.upper()}_INVALID",
                field,
                messages[0],
            )

    documents = transfer.documents or []
    if not any(
        bool(document) and (not isinstance(document, str) or document.strip())
        for document in documents
    ):
        error(
            "TRANSFER_DOCUMENTS_REQUIRED",
            "documents",
            "At least one non-empty document reference is required.",
        )
    else:
        passed("TRANSFER_DOCUMENTS_PRESENT", "documents", "Documents are present.")

    if (
        UnionPlayerTransfer.objects.filter(
            workspace=workspace,
            player=player,
            status__in=NON_TERMINAL_STATUSES,
        )
        .exclude(pk=transfer.pk)
        .exists()
    ):
        error(
            "DUPLICATE_NON_TERMINAL_TRANSFER",
            "player",
            "Another non-terminal transfer exists for this player.",
        )

    if UnionPlayerCompetitionEligibility.objects.filter(
        registration=source_registration,
        status=UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
    ).exists():
        warning(
            "ACTIVE_COMPETITION_ELIGIBILITY",
            "source_registration",
            "Source registration has active competition eligibility.",
        )
    if transfer.fee_status not in {"PAID", "SETTLED", "COMPLETED"}:
        warning(
            "TRANSFER_FEE_UNRESOLVED",
            "fee_status",
            "Transfer fee status is blank or unresolved.",
        )
    if source_registration.effective_to is None:
        warning(
            "SOURCE_REGISTRATION_NO_EXPIRY",
            "source_registration",
            "Source registration has no expiry date.",
        )
    if transfer.destination_team_id is None:
        warning(
            "DESTINATION_TEAM_PENDING",
            "destination_team",
            "Destination team is not yet selected.",
        )
    if (
        transfer.source_club_response_status
        == UnionPlayerTransfer.SourceClubResponseStatus.PENDING
    ):
        warning(
            "SOURCE_CLUB_RESPONSE_PENDING",
            "source_club_response_status",
            "Source Club response remains pending.",
        )
    if (
        transfer.player_consent_status
        == UnionPlayerTransfer.PlayerConsentStatus.PENDING
    ):
        warning(
            "PLAYER_CONSENT_PENDING",
            "player_consent_status",
            "Player consent remains pending.",
        )

    for code, field, message in [
        (
            "TRANSFER_WINDOW_RULE_ENGINE_UNAVAILABLE",
            "effective_on",
            "Transfer-window rule evaluation is unavailable.",
        ),
        (
            "TRAINING_COMPENSATION_CHECK_UNAVAILABLE",
            None,
            "Training-compensation checking is unavailable.",
        ),
        (
            "PAYMENT_SETTLEMENT_CHECK_UNAVAILABLE",
            "fee_status",
            "Payment-settlement checking is unavailable.",
        ),
        (
            "CROSS_BORDER_CLEARANCE_UNAVAILABLE",
            "workspace",
            "Cross-border clearance is unavailable.",
        ),
        (
            "CONTRACT_DISPUTE_CHECK_UNAVAILABLE",
            "player",
            "Contract-dispute checking is unavailable.",
        ),
    ]:
        capability_notes.append(_validation_item(code, field, message, "INFO"))

    return {
        "blocking_errors": blocking_errors,
        "review_warnings": review_warnings,
        "passed_checks": passed_checks,
        "capability_notes": capability_notes,
        "evaluated_at": timezone.now().isoformat(),
        "version": 1,
    }


def validate_player_transfer_submission(*, transfer, actor):
    result = _build_player_transfer_validation(transfer)
    if _actor_manages_club(actor, transfer.destination_club):
        result["passed_checks"].insert(
            0,
            _validation_item(
                "DESTINATION_ACTOR_VALID",
                "destination_club",
                "Actor administers the destination Club with transfer permission.",
                "PASS",
            ),
        )
    else:
        result["blocking_errors"].insert(
            0,
            _validation_item(
                "DESTINATION_ACTOR_INVALID",
                "destination_club",
                "Actor lacks destination Club transfer permission.",
                "ERROR",
            ),
        )
    return result


class TransferSubmissionValidationError(ValidationError):
    def __init__(self, automatic_validation):
        super().__init__(
            {"detail": "Player transfer contains blocking validation errors."}
        )
        self.automatic_validation = automatic_validation


def _refresh_transfer_prerequisite_status(transfer, *, actor):
    previous_status = transfer.status
    if (
        transfer.player_consent_status
        == UnionPlayerTransfer.PlayerConsentStatus.DECLINED
    ):
        return transfer
    if (
        transfer.player_consent_status
        == UnionPlayerTransfer.PlayerConsentStatus.PENDING
    ):
        target = UnionPlayerTransfer.Status.PLAYER_CONSENT_REQUIRED
    elif (
        transfer.source_club_response_status
        == UnionPlayerTransfer.SourceClubResponseStatus.PENDING
    ):
        target = UnionPlayerTransfer.Status.SOURCE_CLUB_RESPONSE_REQUIRED
    else:
        target = UnionPlayerTransfer.Status.UNDER_UNION_REVIEW
    transfer.status = target
    transfer.save(update_fields=["status", "updated_at"])
    if (
        target == UnionPlayerTransfer.Status.UNDER_UNION_REVIEW
        and previous_status != UnionPlayerTransfer.Status.UNDER_UNION_REVIEW
        and not UnionAuditEvent.objects.filter(
            workspace=transfer.workspace,
            action="union_player_transfer.prerequisites_completed",
            target_id=transfer.id,
        ).exists()
    ):
        log_union_audit_event(
            workspace=transfer.workspace,
            actor=actor,
            action="union_player_transfer.prerequisites_completed",
            target=transfer,
            metadata=_audit_metadata(transfer, previous_status=previous_status),
        )
    return transfer


def submit_player_transfer(*, transfer_id, actor):
    validation_error = None
    result = None
    with transaction.atomic():
        transfer = _locked_transfer(transfer_id)
        _require_club_actor(actor, transfer.destination_club, "destination_club")
        if transfer.status != UnionPlayerTransfer.Status.DRAFT:
            raise ValidationError({"status": "Only a draft transfer may be submitted."})
        validation = validate_player_transfer_submission(
            transfer=transfer,
            actor=actor,
        )
        transfer.automatic_validation = validation
        transfer.save(update_fields=["automatic_validation", "updated_at"])
        log_union_audit_event(
            workspace=transfer.workspace,
            actor=actor,
            action="union_player_transfer.validation_completed",
            target=transfer,
            metadata={
                **_audit_metadata(transfer),
                "blocking_error_count": len(validation["blocking_errors"]),
                "review_warning_count": len(validation["review_warnings"]),
                "validation_version": validation["version"],
            },
        )
        if validation["blocking_errors"]:
            validation_error = TransferSubmissionValidationError(validation)
        else:
            previous_status = transfer.status
            transfer.submitted_at = timezone.now()
            transfer.submission_revision += 1
            transfer.save(
                update_fields=[
                    "submitted_at",
                    "submission_revision",
                    "updated_at",
                ]
            )
            _refresh_transfer_prerequisite_status(transfer, actor=actor)
            log_union_audit_event(
                workspace=transfer.workspace,
                actor=actor,
                action="union_player_transfer.submitted",
                target=transfer,
                metadata=_audit_metadata(
                    transfer,
                    previous_status=previous_status,
                ),
            )
            _schedule_notifications(
                transfer,
                [
                    transfer.player.user,
                    transfer.source_registration.club.admin,
                ],
                actor=actor,
                title="Player transfer submitted",
                message="A destination Club submitted a player transfer request.",
            )
            result = transfer
    if validation_error is not None:
        raise validation_error
    return result


def resubmit_player_transfer(*, transfer_id, actor):
    validation_error = None
    result = None
    with transaction.atomic():
        transfer = _locked_transfer(transfer_id)
        _require_club_actor(actor, transfer.destination_club, "destination_club")
        if transfer.status != UnionPlayerTransfer.Status.CHANGES_REQUESTED:
            raise ValidationError(
                {"status": "Only a changes-requested transfer may be resubmitted."}
            )
        if transfer.submitted_at is None:
            raise ValidationError(
                {"status": "Changes-requested transfer lacks submission evidence."}
            )
        validation = validate_player_transfer_submission(
            transfer=transfer,
            actor=actor,
        )
        transfer.automatic_validation = validation
        transfer.save(update_fields=["automatic_validation", "updated_at"])
        log_union_audit_event(
            workspace=transfer.workspace,
            actor=actor,
            action="union_player_transfer.validation_completed",
            target=transfer,
            metadata={
                **_audit_metadata(transfer),
                "blocking_error_count": len(validation["blocking_errors"]),
                "review_warning_count": len(validation["review_warnings"]),
                "validation_version": validation["version"],
            },
        )
        if validation["blocking_errors"]:
            validation_error = TransferSubmissionValidationError(validation)
        else:
            previous_status = transfer.status
            transfer.last_resubmitted_at = timezone.now()
            transfer.submission_revision += 1
            transfer.change_request_reason = ""
            transfer.save(
                update_fields=[
                    "last_resubmitted_at",
                    "submission_revision",
                    "change_request_reason",
                    "updated_at",
                ]
            )
            _refresh_transfer_prerequisite_status(transfer, actor=actor)
            log_union_audit_event(
                workspace=transfer.workspace,
                actor=actor,
                action="union_player_transfer.resubmitted",
                target=transfer,
                metadata=_audit_metadata(
                    transfer,
                    previous_status=previous_status,
                ),
            )
            result = transfer
    if validation_error is not None:
        raise validation_error
    return result


def _require_submitted_non_terminal(transfer):
    if (
        transfer.submitted_at is None
        or transfer.status not in SUBMITTED_ACTIVE_STATUSES
    ):
        raise ValidationError(
            {"status": "Transfer must be submitted and non-terminal."}
        )


@transaction.atomic
def record_source_club_transfer_response(
    *,
    transfer_id,
    actor,
    response_status,
    response,
):
    transfer = _locked_transfer(transfer_id)
    _require_submitted_non_terminal(transfer)
    _require_club_actor(
        actor,
        transfer.source_registration.club,
        "source_club",
    )
    if (
        not _is_super_admin(actor)
        and get_user_clubs(actor).filter(pk=transfer.destination_club_id).exists()
    ):
        raise ValidationError(
            {
                "source_club": "Destination Club administrators cannot record this response."
            }
        )
    if (
        transfer.source_club_response_status
        != UnionPlayerTransfer.SourceClubResponseStatus.PENDING
    ):
        raise ValidationError(
            {"response_status": "Source Club response has already been recorded."}
        )
    allowed = {
        UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED,
        UnionPlayerTransfer.SourceClubResponseStatus.OBJECTED,
    }
    if response_status not in allowed:
        raise ValidationError({"response_status": "Unsupported response status."})
    written_response = str(response or "").strip()
    if (
        response_status == UnionPlayerTransfer.SourceClubResponseStatus.OBJECTED
        and not written_response
    ):
        raise ValidationError(
            {"response": "A written response is required for an objection."}
        )
    transfer.source_club_response_status = response_status
    transfer.source_club_response = written_response
    transfer.source_club_responded_by = actor
    transfer.source_club_response_at = timezone.now()
    transfer.save(
        update_fields=[
            "source_club_response_status",
            "source_club_response",
            "source_club_responded_by",
            "source_club_response_at",
            "updated_at",
        ]
    )
    action = (
        "union_player_transfer.source_club_acknowledged"
        if response_status == UnionPlayerTransfer.SourceClubResponseStatus.ACKNOWLEDGED
        else "union_player_transfer.source_club_objected"
    )
    log_union_audit_event(
        workspace=transfer.workspace,
        actor=actor,
        action=action,
        target=transfer,
        metadata=_audit_metadata(transfer),
    )
    _refresh_transfer_prerequisite_status(transfer, actor=actor)
    _schedule_notifications(
        transfer,
        [transfer.initiated_by],
        actor=actor,
        title="Source Club responded to transfer",
        message="The source Club recorded its transfer response.",
    )
    return transfer


def _authorised_consent_actor(
    *,
    transfer,
    actor,
    membership,
    evidence_reference,
):
    if transfer.player.user_id == getattr(actor, "pk", None):
        return "DIRECT"
    if membership is None or not getattr(membership, "pk", None):
        raise ValidationError(
            {"actor": "Only the linked player or authorised Union officer may consent."}
        )
    active = (
        UnionWorkspaceMembership.objects.filter(
            pk=membership.pk,
            user=actor,
            workspace=transfer.workspace,
            is_active=True,
            workspace__status=UnionWorkspace.Status.ACTIVE,
        )
        .select_related("workspace")
        .first()
    )
    if active is None or UNION_TRANSFER_PERMISSION not in active.effective_permissions:
        raise ValidationError(
            {"actor": "Union officer lacks offline consent authority."}
        )
    if not str(evidence_reference or "").strip():
        raise ValidationError(
            {"evidence_reference": "Verified offline evidence is required."}
        )
    return "OFFLINE"


@transaction.atomic
def record_player_transfer_consent(
    *,
    transfer_id,
    actor,
    consent_method,
    membership=None,
    evidence_reference="",
):
    transfer = _locked_transfer(transfer_id)
    _require_submitted_non_terminal(transfer)
    method = str(consent_method or "").strip()
    if not method:
        raise ValidationError({"consent_method": "Consent method is required."})
    _authorised_consent_actor(
        transfer=transfer,
        actor=actor,
        membership=membership,
        evidence_reference=evidence_reference,
    )
    if (
        transfer.player_consent_status
        != UnionPlayerTransfer.PlayerConsentStatus.PENDING
    ):
        raise ValidationError({"player_consent": "Player consent is already recorded."})
    transfer.player_consent_status = UnionPlayerTransfer.PlayerConsentStatus.CONSENTED
    transfer.player_consented_at = timezone.now()
    transfer.player_consent_method = method
    transfer.player_consent_recorded_by = actor
    transfer.save(
        update_fields=[
            "player_consent_status",
            "player_consented_at",
            "player_consent_method",
            "player_consent_recorded_by",
            "updated_at",
        ]
    )
    log_union_audit_event(
        workspace=transfer.workspace,
        actor=actor,
        action="union_player_transfer.player_consented",
        target=transfer,
        metadata=_audit_metadata(transfer),
    )
    _refresh_transfer_prerequisite_status(transfer, actor=actor)
    _schedule_notifications(
        transfer,
        [
            transfer.initiated_by,
            transfer.source_registration.club.admin,
        ],
        actor=actor,
        title="Player consent recorded",
        message="Player consent was recorded for a transfer request.",
    )
    return transfer


@transaction.atomic
def decline_player_transfer_consent(
    *,
    transfer_id,
    actor,
    reason,
    membership=None,
    evidence_reference="",
):
    transfer = _locked_transfer(transfer_id)
    _require_submitted_non_terminal(transfer)
    written_reason = str(reason or "").strip()
    if not written_reason:
        raise ValidationError({"reason": "A written decline reason is required."})
    actor_type = _authorised_consent_actor(
        transfer=transfer,
        actor=actor,
        membership=membership,
        evidence_reference=evidence_reference,
    )
    if (
        transfer.player_consent_status
        != UnionPlayerTransfer.PlayerConsentStatus.PENDING
    ):
        raise ValidationError({"player_consent": "Player consent is already recorded."})
    now = timezone.now()
    previous_status = transfer.status
    transfer.player_consent_status = UnionPlayerTransfer.PlayerConsentStatus.DECLINED
    transfer.player_consent_recorded_by = actor
    transfer.player_consented_at = now
    transfer.player_consent_method = (
        "DIRECT_DECLINE" if actor_type == "DIRECT" else "VERIFIED_OFFLINE_DECLINE"
    )
    transfer.status = UnionPlayerTransfer.Status.CANCELLED
    transfer.cancellation_reason = written_reason
    transfer.cancelled_by = actor
    transfer.cancelled_at = now
    transfer.save(
        update_fields=[
            "player_consent_status",
            "player_consent_recorded_by",
            "player_consented_at",
            "player_consent_method",
            "status",
            "cancellation_reason",
            "cancelled_by",
            "cancelled_at",
            "updated_at",
        ]
    )
    metadata = _audit_metadata(transfer, previous_status=previous_status)
    log_union_audit_event(
        workspace=transfer.workspace,
        actor=actor,
        action="union_player_transfer.player_declined",
        target=transfer,
        metadata=metadata,
    )
    log_union_audit_event(
        workspace=transfer.workspace,
        actor=actor,
        action="union_player_transfer.cancelled",
        target=transfer,
        metadata=metadata,
    )
    _schedule_notifications(
        transfer,
        [
            transfer.initiated_by,
            transfer.source_registration.club.admin,
        ],
        actor=actor,
        title="Player declined transfer",
        message="The player declined a transfer request.",
    )
    return transfer


@transaction.atomic
def cancel_player_transfer_request(*, transfer_id, actor, reason):
    transfer = _locked_transfer(transfer_id)
    _require_club_actor(actor, transfer.destination_club, "destination_club")
    written_reason = str(reason or "").strip()
    if not written_reason:
        raise ValidationError({"reason": "A cancellation reason is required."})
    allowed = {
        UnionPlayerTransfer.Status.DRAFT,
        UnionPlayerTransfer.Status.SUBMITTED,
        UnionPlayerTransfer.Status.PLAYER_CONSENT_REQUIRED,
        UnionPlayerTransfer.Status.SOURCE_CLUB_RESPONSE_REQUIRED,
    }
    if transfer.status not in allowed:
        raise ValidationError(
            {"status": "Destination Club cannot cancel at this workflow stage."}
        )
    previous_status = transfer.status
    transfer.status = UnionPlayerTransfer.Status.CANCELLED
    transfer.cancelled_by = actor
    transfer.cancelled_at = timezone.now()
    transfer.cancellation_reason = written_reason
    transfer.save(
        update_fields=[
            "status",
            "cancelled_by",
            "cancelled_at",
            "cancellation_reason",
            "updated_at",
        ]
    )
    log_union_audit_event(
        workspace=transfer.workspace,
        actor=actor,
        action="union_player_transfer.cancelled",
        target=transfer,
        metadata=_audit_metadata(transfer, previous_status=previous_status),
    )
    return transfer
