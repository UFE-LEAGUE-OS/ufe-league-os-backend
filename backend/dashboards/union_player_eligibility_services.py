"""Maintained competition-eligibility lifecycle for approved Club submissions."""

from functools import partial

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import Notification, NotificationPreference
from accounts.services import create_in_app_notification
from teams.models import PlayerRegistration

from .models import (
    CompetitionEdition,
    UnionPlayer,
    UnionPlayerCompetitionEligibility,
    UnionPlayerRegistration,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
from .union_governance import log_union_audit_event
from .union_scopes import scope_allows

ELIGIBILITY_PERMISSION = "union.players.approve"
TERMINAL_STATUSES = {
    UnionPlayerCompetitionEligibility.Status.INELIGIBLE,
    UnionPlayerCompetitionEligibility.Status.EXPIRED,
    UnionPlayerCompetitionEligibility.Status.REJECTED,
    UnionPlayerCompetitionEligibility.Status.CANCELLED,
}
REVIEWABLE_EDITION_STATUSES = {
    CompetitionEdition.Status.REGISTRATION_OPEN,
    CompetitionEdition.Status.REGISTRATION_CLOSED,
    CompetitionEdition.Status.ENTRIES_UNDER_REVIEW,
    CompetitionEdition.Status.SCHEDULING,
    CompetitionEdition.Status.READY_FOR_PUBLICATION,
    CompetitionEdition.Status.PUBLISHED,
    CompetitionEdition.Status.ACTIVE,
}


def _is_super_admin(user):
    return bool(
        user
        and (
            getattr(user, "is_superuser", False)
            or getattr(user, "role", None) == "SUPER_ADMIN"
        )
    )


def _active_membership(*, actor, membership, permission=ELIGIBILITY_PERMISSION):
    if membership is None or not getattr(membership, "pk", None):
        raise ValidationError({"workspace": "An active Union membership is required."})
    active = (
        UnionWorkspaceMembership.objects.filter(
            pk=membership.pk,
            user=actor,
            is_active=True,
            workspace__status=UnionWorkspace.Status.ACTIVE,
            workspace__related_union__isnull=False,
        )
        .select_related("workspace", "workspace__related_union")
        .first()
    )
    if active is None:
        raise ValidationError({"workspace": "An active Union membership is required."})
    if not _is_super_admin(actor) and permission not in active.effective_permissions:
        raise ValidationError({"permission": f"Reviewer requires {permission}."})
    return active


def _require_scope(membership, *, club_id, identity_id, edition_id):
    if not scope_allows(membership, "club", club_id):
        raise ValidationError({"scope": "Club is outside the reviewer scope."})
    if not scope_allows(membership, "competition_identity", identity_id):
        raise ValidationError(
            {"scope": "Competition identity is outside the reviewer scope."}
        )
    if not scope_allows(membership, "competition_edition", edition_id):
        raise ValidationError(
            {"scope": "Competition edition is outside the reviewer scope."}
        )


def _reason(value):
    written = str(value or "").strip()
    if not written:
        raise ValidationError({"reason": "A written reason is required."})
    return written


def _validation_item(code, field, message, severity):
    return {
        "code": code,
        "field": field,
        "message": message,
        "severity": severity,
    }


class EligibilityValidationError(ValidationError):
    def __init__(self, automatic_validation):
        super().__init__(
            {"detail": "Competition eligibility contains blocking validation errors."}
        )
        self.automatic_validation = automatic_validation


def _audit_metadata(eligibility, *, previous_status=None, idempotent_replay=False):
    return {
        "eligibility_id": eligibility.id,
        "source_submission_id": eligibility.source_submission_id,
        "authoritative_registration_id": eligibility.registration_id,
        "player_id": eligibility.player_id,
        "club_id": eligibility.club_id,
        "competition_identity_id": eligibility.competition_identity_id,
        "competition_edition_id": eligibility.competition_edition_id,
        "season_id": eligibility.season_id,
        "previous_status": previous_status,
        "new_status": eligibility.status,
        "idempotent_replay": idempotent_replay,
    }


def _notify_submitter(eligibility_id, title, message):
    eligibility = (
        UnionPlayerCompetitionEligibility.objects.filter(pk=eligibility_id)
        .select_related("source_submission__submitted_by")
        .first()
    )
    if (
        eligibility is None
        or eligibility.source_submission is None
        or eligibility.source_submission.submitted_by_id is None
    ):
        return
    try:
        create_in_app_notification(
            user=eligibility.source_submission.submitted_by,
            event_type=NotificationPreference.EventType.GOVERNANCE,
            category=Notification.Category.GOVERNANCE,
            title=title,
            message=message,
            action_url="/dashboard/club-admin",
            metadata={
                "eligibility_id": eligibility.id,
                "submission_id": eligibility.source_submission_id,
                "club_id": eligibility.club_id,
                "competition_edition_id": eligibility.competition_edition_id,
                "status": eligibility.status,
            },
        )
    except Exception:
        # Notification delivery is deliberately isolated from the decision.
        return


def _schedule_notification(eligibility, *, title, message):
    if (
        eligibility.source_submission is None
        or eligibility.source_submission.submitted_by_id is None
    ):
        return
    transaction.on_commit(
        partial(
            _notify_submitter,
            eligibility.id,
            title,
            message,
        )
    )


def _locked_eligibility(eligibility_id):
    return (
        UnionPlayerCompetitionEligibility.objects.select_for_update(of=("self",))
        .select_related(
            "workspace__related_union",
            "player",
            "registration",
            "club",
            "team",
            "competition_identity",
            "competition_edition__identity",
            "competition_edition__competition",
            "season",
            "source_submission__submitted_by",
        )
        .get(pk=eligibility_id)
    )


def _require_eligibility_access(*, eligibility, reviewer, membership):
    active = _active_membership(actor=reviewer, membership=membership)
    if eligibility.workspace_id != active.workspace_id:
        raise ValidationError(
            {"workspace": "Eligibility does not belong to the selected workspace."}
        )
    _require_scope(
        active,
        club_id=eligibility.club_id,
        identity_id=eligibility.competition_identity_id,
        edition_id=eligibility.competition_edition_id,
    )
    return active


@transaction.atomic
def create_pending_eligibilities_for_submission(
    *,
    submission,
    authoritative_registration,
    actor,
    membership,
):
    membership = _active_membership(actor=actor, membership=membership)
    submission = (
        PlayerRegistration.objects.select_for_update(of=("self",))
        .select_related(
            "union_workspace__related_union",
            "union_player",
            "club",
            "team",
            "season_record",
        )
        .prefetch_related("requested_competition_editions__identity")
        .get(pk=submission.pk)
    )
    registration = (
        UnionPlayerRegistration.objects.select_for_update(of=("self",))
        .select_related("workspace", "player", "club", "season")
        .get(pk=authoritative_registration.pk)
    )
    if submission.submission_status != PlayerRegistration.SubmissionStatus.APPROVED:
        raise ValidationError({"submission": "Submission must be approved."})
    if (
        submission.union_workspace_id != membership.workspace_id
        or registration.workspace_id != membership.workspace_id
    ):
        raise ValidationError(
            {
                "workspace": "Submission and registration must use the selected workspace."
            }
        )
    if (
        submission.union_player_id is None
        or registration.player_id != submission.union_player_id
    ):
        raise ValidationError(
            {"player": "Registration must belong to the submitted player."}
        )
    if registration.club_id != submission.club_id:
        raise ValidationError(
            {"club": "Registration must belong to the submission Club."}
        )
    if registration.status != UnionPlayerRegistration.Status.ACTIVE:
        raise ValidationError(
            {"registration": "An active authoritative registration is required."}
        )
    if submission.union_player.union_id != membership.workspace.related_union_id:
        raise ValidationError(
            {"player": "Player must belong to the selected workspace Union."}
        )

    editions = list(submission.requested_competition_editions.all())
    if not editions:
        return {
            "eligibilities": [],
            "created_count": 0,
            "existing_count": 0,
            "idempotent_replay": False,
        }

    warnings = list((submission.automatic_validation or {}).get("review_warnings", []))
    eligibilities = []
    created_count = 0
    existing_count = 0
    for edition in editions:
        if (
            edition.identity.union_id != membership.workspace.related_union_id
            or edition.competition.league.union_id
            != membership.workspace.related_union_id
        ):
            raise ValidationError(
                {"competition_edition": "Edition must belong to the workspace Union."}
            )
        if edition.season_id != submission.season_record_id:
            raise ValidationError(
                {"competition_edition": "Edition must match the submission season."}
            )
        _require_scope(
            membership,
            club_id=submission.club_id,
            identity_id=edition.identity_id,
            edition_id=edition.id,
        )
        existing = (
            UnionPlayerCompetitionEligibility.objects.select_for_update(of=("self",))
            .filter(
                source_submission=submission,
                competition_edition=edition,
            )
            .first()
        )
        if existing is not None:
            eligibilities.append(existing)
            existing_count += 1
            continue
        eligibility = UnionPlayerCompetitionEligibility.objects.create(
            workspace=membership.workspace,
            player=submission.union_player,
            registration=registration,
            source_submission=submission,
            club=submission.club,
            team=submission.team,
            competition_identity=edition.identity,
            competition_edition=edition,
            season=submission.season_record,
            status=UnionPlayerCompetitionEligibility.Status.PENDING,
            warnings=warnings,
        )
        log_union_audit_event(
            workspace=membership.workspace,
            actor=actor,
            action="competition_eligibility.pending_created",
            target=eligibility,
            metadata=_audit_metadata(eligibility),
        )
        eligibilities.append(eligibility)
        created_count += 1
    return {
        "eligibilities": eligibilities,
        "created_count": created_count,
        "existing_count": existing_count,
        "idempotent_replay": bool(eligibilities and created_count == 0),
    }


def validate_player_competition_eligibility(*, eligibility, reviewer, membership):
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

    membership_is_active = bool(
        membership
        and getattr(membership, "pk", None)
        and UnionWorkspaceMembership.objects.filter(
            pk=membership.pk,
            user=reviewer,
            is_active=True,
            workspace__status=UnionWorkspace.Status.ACTIVE,
            workspace__related_union__isnull=False,
        ).exists()
    )
    if membership_is_active:
        passed("UNION_MEMBERSHIP_VALID", "workspace", "Union membership is active.")
    else:
        error(
            "UNION_MEMBERSHIP_INVALID",
            "workspace",
            "An active Union membership is required.",
        )

    permission_allowed = _is_super_admin(reviewer) or (
        membership_is_active
        and ELIGIBILITY_PERMISSION in membership.effective_permissions
    )
    if permission_allowed:
        passed(
            "UNION_PERMISSION_VALID",
            None,
            f"Reviewer has {ELIGIBILITY_PERMISSION}.",
        )
    else:
        error(
            "UNION_PERMISSION_DENIED",
            None,
            f"Reviewer requires {ELIGIBILITY_PERMISSION}.",
        )

    workspace = membership.workspace if membership_is_active else None
    if workspace is None or eligibility.workspace_id != workspace.id:
        error(
            "ELIGIBILITY_WORKSPACE_INVALID",
            "workspace",
            "Eligibility does not belong to the selected workspace.",
        )
    else:
        passed(
            "ELIGIBILITY_WORKSPACE_VALID",
            "workspace",
            "Eligibility belongs to the selected workspace.",
        )
        if not scope_allows(membership, "club", eligibility.club_id):
            error("ELIGIBILITY_CLUB_SCOPE_DENIED", "club", "Club is out of scope.")
        if not scope_allows(
            membership,
            "competition_identity",
            eligibility.competition_identity_id,
        ):
            error(
                "ELIGIBILITY_IDENTITY_SCOPE_DENIED",
                "competition_identity",
                "Competition identity is out of scope.",
            )
        if not scope_allows(
            membership,
            "competition_edition",
            eligibility.competition_edition_id,
        ):
            error(
                "ELIGIBILITY_EDITION_SCOPE_DENIED",
                "competition_edition",
                "Competition edition is out of scope.",
            )

    player = eligibility.player
    workspace_union_id = workspace.related_union_id if workspace else None
    if player.union_id != workspace_union_id:
        error(
            "PLAYER_UNION_INVALID",
            "player",
            "Player must belong to the selected workspace Union.",
        )
    elif player.status != UnionPlayer.Status.APPROVED:
        error(
            f"PLAYER_{player.status}",
            "player",
            "Player must be approved for competition eligibility.",
        )
    else:
        passed("PLAYER_APPROVED", "player", "Player identity is approved.")

    registration = eligibility.registration
    if registration.workspace_id != eligibility.workspace_id:
        error(
            "REGISTRATION_WORKSPACE_INVALID",
            "registration",
            "Registration must belong to the eligibility workspace.",
        )
    if registration.player_id != eligibility.player_id:
        error(
            "REGISTRATION_PLAYER_INVALID",
            "registration",
            "Registration must belong to the eligibility player.",
        )
    if registration.club_id != eligibility.club_id:
        error(
            "REGISTRATION_CLUB_INVALID",
            "registration",
            "Registration must belong to the eligibility Club.",
        )
    if registration.status != UnionPlayerRegistration.Status.ACTIVE:
        error(
            "ACTIVE_REGISTRATION_REQUIRED",
            "registration",
            "An active authoritative registration is required.",
        )
    if (
        registration.season_id
        and eligibility.season_id
        and registration.season_id != eligibility.season_id
    ):
        error(
            "REGISTRATION_SEASON_INVALID",
            "season",
            "Registration season must match eligibility season.",
        )

    identity = eligibility.competition_identity
    edition = eligibility.competition_edition
    if identity.union_id != workspace_union_id:
        error(
            "COMPETITION_IDENTITY_UNION_INVALID",
            "competition_identity",
            "Competition identity must belong to the workspace Union.",
        )
    if edition.identity_id != identity.id:
        error(
            "COMPETITION_EDITION_IDENTITY_INVALID",
            "competition_edition",
            "Competition edition must belong to the selected identity.",
        )
    if edition.competition.league.union_id != workspace_union_id:
        error(
            "COMPETITION_EDITION_UNION_INVALID",
            "competition_edition",
            "Competition edition must belong to the workspace Union.",
        )
    if edition.season_id != eligibility.season_id:
        error(
            "COMPETITION_EDITION_SEASON_INVALID",
            "season",
            "Competition edition must match eligibility season.",
        )
    if edition.status not in REVIEWABLE_EDITION_STATUSES:
        error(
            "COMPETITION_EDITION_NOT_REVIEWABLE",
            "competition_edition",
            "Competition edition is not open for eligibility review.",
        )

    if (
        eligibility.eligible_from
        and eligibility.eligible_until
        and eligibility.eligible_until < eligibility.eligible_from
    ):
        error(
            "ELIGIBILITY_DATE_ORDER_INVALID",
            "eligible_until",
            "Eligibility end date cannot precede its start date.",
        )
    if (
        eligibility.eligible_from
        and eligibility.eligible_from < registration.effective_from
    ):
        error(
            "ELIGIBILITY_BEFORE_REGISTRATION",
            "eligible_from",
            "Eligibility cannot begin before the authoritative registration.",
        )
    if (
        eligibility.eligible_until
        and registration.effective_to
        and eligibility.eligible_until > registration.effective_to
    ):
        error(
            "ELIGIBILITY_AFTER_REGISTRATION",
            "eligible_until",
            "Eligibility cannot extend beyond the registration expiry.",
        )
    competition_end = edition.competition.end_date
    if (
        eligibility.eligible_until
        and competition_end
        and eligibility.eligible_until > competition_end
    ):
        error(
            "ELIGIBILITY_AFTER_COMPETITION",
            "eligible_until",
            "Eligibility cannot extend beyond the competition end date.",
        )

    if (
        UnionPlayerCompetitionEligibility.objects.filter(
            player=eligibility.player,
            competition_edition=edition,
            status=UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
        )
        .exclude(pk=eligibility.pk)
        .exists()
    ):
        error(
            "ELIGIBLE_RECORD_CONFLICT",
            "competition_edition",
            "Another eligible record already exists for this player and edition.",
        )

    source_warnings = list(
        (eligibility.source_submission.automatic_validation or {}).get(
            "review_warnings", []
        )
        if eligibility.source_submission
        else []
    )
    for item in source_warnings:
        if item.get("code") in {
            "PLAYER_IDENTITY_PROVISIONAL",
            "PLAYER_IDENTITY_PENDING_VERIFICATION",
        }:
            warning(
                "SOURCE_IDENTITY_INITIAL_REVIEW_REQUIRED",
                "player",
                "The source player identity initially required Union verification.",
            )
        copied = dict(item)
        copied["severity"] = "WARNING"
        if not any(
            existing["code"] == copied.get("code") for existing in review_warnings
        ):
            review_warnings.append(copied)

    closes_at = edition.registration_closes_at
    submitted_at = (
        eligibility.source_submission.submitted_at
        if eligibility.source_submission
        else None
    )
    if closes_at and submitted_at and submitted_at <= closes_at < timezone.now():
        warning(
            "REGISTRATION_CLOSED_AFTER_SUBMISSION",
            "competition_edition",
            "Competition registration closed after the source submission was filed.",
        )
    if eligibility.team_id is None:
        warning("TEAM_NOT_ATTACHED", "team", "No team is attached to eligibility.")
    if edition.eligibility_rules or identity.default_eligibility_rules:
        warning(
            "ELIGIBILITY_RULE_ENGINE_INCOMPLETE",
            "competition_edition",
            "Competition eligibility rules exist without a complete rule engine.",
        )

    for code, field, message in [
        (
            "COMPETITION_SQUAD_LIMIT_CHECK_UNAVAILABLE",
            "team",
            "Competition squad-limit checking is unavailable.",
        ),
        (
            "CUP_TIED_RULE_CHECK_UNAVAILABLE",
            "player",
            "Cup-tied rule checking is unavailable.",
        ),
        (
            "DISCIPLINARY_DETAIL_CHECK_LIMITED",
            "player",
            "Detailed disciplinary checking is limited.",
        ),
        (
            "PAYMENT_CHECK_UNAVAILABLE",
            None,
            "Competition payment checking is unavailable.",
        ),
        (
            "FOREIGN_PLAYER_RULE_ENGINE_UNAVAILABLE",
            "player",
            "Foreign-player rule evaluation is unavailable.",
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


def _default_eligibility_dates(eligibility, eligible_from, eligible_until):
    start = eligible_from or max(
        eligibility.registration.effective_from,
        timezone.localdate(),
    )
    explicit_ends = [
        value
        for value in (
            eligibility.registration.effective_to,
            eligibility.competition_edition.competition.end_date,
        )
        if value is not None
    ]
    end = eligible_until
    if end is None and explicit_ends:
        end = min(explicit_ends)
    return start, end


@transaction.atomic
def approve_player_competition_eligibility(
    *,
    eligibility_id,
    reviewer,
    membership,
    reason,
    eligible_from=None,
    eligible_until=None,
):
    written_reason = _reason(reason)
    eligibility = _locked_eligibility(eligibility_id)
    membership = _require_eligibility_access(
        eligibility=eligibility,
        reviewer=reviewer,
        membership=membership,
    )
    if eligibility.status == UnionPlayerCompetitionEligibility.Status.ELIGIBLE:
        return {
            "eligibility": eligibility,
            "automatic_validation": {
                "review_warnings": eligibility.warnings,
            },
            "idempotent_replay": True,
        }
    if eligibility.status != UnionPlayerCompetitionEligibility.Status.PENDING:
        raise ValidationError({"status": "Only pending eligibility may be approved."})
    eligibility.eligible_from, eligibility.eligible_until = _default_eligibility_dates(
        eligibility, eligible_from, eligible_until
    )
    validation = validate_player_competition_eligibility(
        eligibility=eligibility,
        reviewer=reviewer,
        membership=membership,
    )
    eligibility.warnings = validation["review_warnings"]
    if validation["blocking_errors"]:
        eligibility.save(update_fields=["warnings", "updated_at"])
        raise EligibilityValidationError(validation)
    previous_status = eligibility.status
    eligibility.status = UnionPlayerCompetitionEligibility.Status.ELIGIBLE
    eligibility.reviewed_by = reviewer
    eligibility.reviewed_at = timezone.now()
    eligibility.decision_reason = written_reason
    eligibility.restriction_reason = ""
    eligibility.save(
        update_fields=[
            "status",
            "eligible_from",
            "eligible_until",
            "warnings",
            "reviewed_by",
            "reviewed_at",
            "decision_reason",
            "restriction_reason",
            "updated_at",
        ]
    )
    log_union_audit_event(
        workspace=membership.workspace,
        actor=reviewer,
        action="competition_eligibility.approved",
        target=eligibility,
        metadata=_audit_metadata(eligibility, previous_status=previous_status),
    )
    _schedule_notification(
        eligibility,
        title="Competition eligibility approved",
        message="The Union approved the player's competition eligibility.",
    )
    return {
        "eligibility": eligibility,
        "automatic_validation": validation,
        "idempotent_replay": False,
    }


def _transition(
    *,
    eligibility_id,
    reviewer,
    membership,
    reason,
    allowed_statuses,
    target_status,
    action,
    reason_field,
    notification=None,
):
    written_reason = _reason(reason)
    with transaction.atomic():
        eligibility = _locked_eligibility(eligibility_id)
        membership = _require_eligibility_access(
            eligibility=eligibility,
            reviewer=reviewer,
            membership=membership,
        )
        if eligibility.status not in allowed_statuses:
            raise ValidationError(
                {
                    "status": (
                        f"Cannot transition eligibility from {eligibility.status} "
                        f"to {target_status}."
                    )
                }
            )
        previous_status = eligibility.status
        eligibility.status = target_status
        eligibility.reviewed_by = reviewer
        eligibility.reviewed_at = timezone.now()
        setattr(eligibility, reason_field, written_reason)
        eligibility.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                reason_field,
                "updated_at",
            ]
        )
        log_union_audit_event(
            workspace=membership.workspace,
            actor=reviewer,
            action=action,
            target=eligibility,
            metadata=_audit_metadata(
                eligibility,
                previous_status=previous_status,
            ),
        )
        if notification:
            _schedule_notification(
                eligibility,
                title=notification[0],
                message=notification[1],
            )
        return eligibility


def reject_player_competition_eligibility(
    *,
    eligibility_id,
    reviewer,
    membership,
    reason,
):
    return _transition(
        eligibility_id=eligibility_id,
        reviewer=reviewer,
        membership=membership,
        reason=reason,
        allowed_statuses={UnionPlayerCompetitionEligibility.Status.PENDING},
        target_status=UnionPlayerCompetitionEligibility.Status.REJECTED,
        action="competition_eligibility.rejected",
        reason_field="decision_reason",
        notification=(
            "Competition eligibility rejected",
            "The Union rejected the player's competition eligibility.",
        ),
    )


def suspend_player_competition_eligibility(
    *,
    eligibility_id,
    reviewer,
    membership,
    reason,
):
    return _transition(
        eligibility_id=eligibility_id,
        reviewer=reviewer,
        membership=membership,
        reason=reason,
        allowed_statuses={UnionPlayerCompetitionEligibility.Status.ELIGIBLE},
        target_status=UnionPlayerCompetitionEligibility.Status.SUSPENDED,
        action="competition_eligibility.suspended",
        reason_field="restriction_reason",
        notification=(
            "Competition eligibility suspended",
            "The Union suspended the player's competition eligibility.",
        ),
    )


@transaction.atomic
def reinstate_player_competition_eligibility(
    *,
    eligibility_id,
    reviewer,
    membership,
    reason,
):
    written_reason = _reason(reason)
    eligibility = _locked_eligibility(eligibility_id)
    membership = _require_eligibility_access(
        eligibility=eligibility,
        reviewer=reviewer,
        membership=membership,
    )
    if eligibility.status != UnionPlayerCompetitionEligibility.Status.SUSPENDED:
        raise ValidationError(
            {"status": "Only suspended eligibility may be reinstated."}
        )
    validation = validate_player_competition_eligibility(
        eligibility=eligibility,
        reviewer=reviewer,
        membership=membership,
    )
    eligibility.warnings = validation["review_warnings"]
    if validation["blocking_errors"]:
        eligibility.save(update_fields=["warnings", "updated_at"])
        raise EligibilityValidationError(validation)
    previous_status = eligibility.status
    eligibility.status = UnionPlayerCompetitionEligibility.Status.ELIGIBLE
    eligibility.restriction_reason = ""
    eligibility.reviewed_by = reviewer
    eligibility.reviewed_at = timezone.now()
    evidence = f"Reinstated: {written_reason}"
    eligibility.decision_reason = "\n".join(
        value for value in [eligibility.decision_reason.strip(), evidence] if value
    )
    eligibility.save(
        update_fields=[
            "status",
            "restriction_reason",
            "warnings",
            "reviewed_by",
            "reviewed_at",
            "decision_reason",
            "updated_at",
        ]
    )
    log_union_audit_event(
        workspace=membership.workspace,
        actor=reviewer,
        action="competition_eligibility.reinstated",
        target=eligibility,
        metadata=_audit_metadata(eligibility, previous_status=previous_status),
    )
    _schedule_notification(
        eligibility,
        title="Competition eligibility reinstated",
        message="The Union reinstated the player's competition eligibility.",
    )
    return eligibility


def expire_player_competition_eligibility(
    *,
    eligibility_id,
    reviewer,
    membership,
    reason,
):
    return _transition(
        eligibility_id=eligibility_id,
        reviewer=reviewer,
        membership=membership,
        reason=reason,
        allowed_statuses={
            UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
            UnionPlayerCompetitionEligibility.Status.SUSPENDED,
        },
        target_status=UnionPlayerCompetitionEligibility.Status.EXPIRED,
        action="competition_eligibility.expired",
        reason_field="restriction_reason",
    )


def cancel_player_competition_eligibility(
    *,
    eligibility_id,
    reviewer,
    membership,
    reason,
):
    return _transition(
        eligibility_id=eligibility_id,
        reviewer=reviewer,
        membership=membership,
        reason=reason,
        allowed_statuses={UnionPlayerCompetitionEligibility.Status.PENDING},
        target_status=UnionPlayerCompetitionEligibility.Status.CANCELLED,
        action="competition_eligibility.cancelled",
        reason_field="decision_reason",
    )
