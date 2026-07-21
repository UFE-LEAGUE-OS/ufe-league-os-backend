"""Scheduled and immediate activation for approved maintained player transfers."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    UnionPlayer,
    UnionPlayerCompetitionEligibility,
    UnionPlayerRegistration,
    UnionPlayerTransfer,
)
from .union_governance import log_union_audit_event
from .union_player_transfer_review_services import (
    AFFECTED_ELIGIBILITY_STATUSES,
    _eligibility_metadata,
    _result,
    _safe_warnings,
    _schedule_notifications,
    _verify_completed_transfer,
)
from .union_player_transfer_services import (
    _active_affiliation,
    _audit_metadata,
)

ACTIVATABLE_TRANSFER_TYPES = {"PERMANENT", "FREE_TRANSFER", "LOAN"}
ACTIVATION_PLAN_VERSION = 1
LOAN_RETURN_PLAN_VERSION = 1


def _date_value(value):
    return value.isoformat() if value is not None else None


def build_player_transfer_activation_plan(
    transfer,
    affected_eligibilities,
    *,
    original_effective_to=None,
):
    """Freeze primitive relationships used by later scheduled activation."""

    eligibilities = list(affected_eligibilities)
    original_expiry = (
        transfer.source_registration.effective_to
        if original_effective_to is None
        else original_effective_to
    )
    return {
        "version": ACTIVATION_PLAN_VERSION,
        "workspace_id": transfer.workspace_id,
        "player_id": transfer.player_id,
        "source_registration_id": transfer.source_registration_id,
        "source_club_id": transfer.source_registration.club_id,
        "destination_club_id": transfer.destination_club_id,
        "destination_team_id": transfer.destination_team_id,
        "transfer_type": transfer.transfer_type,
        "effective_on": _date_value(transfer.effective_on),
        "loan_end_on": _date_value(transfer.loan_end_on),
        "source_registration_original_effective_to": _date_value(original_expiry),
        "affected_eligibility_ids": sorted(
            {eligibility.id for eligibility in eligibilities}
        ),
        "competition_identity_ids": sorted(
            {eligibility.competition_identity_id for eligibility in eligibilities}
        ),
        "competition_edition_ids": sorted(
            {eligibility.competition_edition_id for eligibility in eligibilities}
        ),
    }


def build_player_loan_return_plan(
    transfer,
    *,
    destination_registration,
    destination_eligibilities,
):
    """Freeze primitive evidence required for the scheduled return leg."""

    eligibilities = list(destination_eligibilities)
    return_effective_on = transfer.loan_end_on + timedelta(days=1)
    return {
        "version": LOAN_RETURN_PLAN_VERSION,
        "workspace_id": transfer.workspace_id,
        "player_id": transfer.player_id,
        "source_registration_id": transfer.source_registration_id,
        "source_club_id": transfer.source_registration.club_id,
        "source_team_id": transfer.source_registration.team_id,
        "destination_registration_id": destination_registration.id,
        "destination_club_id": transfer.destination_club_id,
        "destination_team_id": transfer.destination_team_id,
        "loan_end_on": _date_value(transfer.loan_end_on),
        "return_effective_on": _date_value(return_effective_on),
        "source_registration_original_effective_to": _date_value(
            transfer.source_registration_original_effective_to
        ),
        "destination_eligibility_ids": sorted(
            {eligibility.id for eligibility in eligibilities}
        ),
        "competition_identity_ids": sorted(
            {eligibility.competition_identity_id for eligibility in eligibilities}
        ),
        "competition_edition_ids": sorted(
            {eligibility.competition_edition_id for eligibility in eligibilities}
        ),
    }


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
            "reviewed_by",
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


def _activation_metadata(transfer, *, previous_status):
    return {
        **_audit_metadata(transfer, previous_status=previous_status),
        "destination_registration_id": transfer.destination_registration_id,
        "effective_on": _date_value(transfer.effective_on),
        "loan_end_on": _date_value(transfer.loan_end_on),
    }


def _verify_plan_shape(transfer):
    plan = transfer.activation_plan or {}
    if plan.get("version") != ACTIVATION_PLAN_VERSION:
        raise ValidationError(
            {"activation_plan": "Transfer activation plan is missing or unsupported."}
        )
    if (
        transfer.source_registration_original_effective_to
        != transfer.source_registration.effective_to
    ):
        raise ValidationError(
            {
                "source_registration": (
                    "Source registration expiry changed after transfer approval."
                )
            }
        )
    expected = build_player_transfer_activation_plan(
        transfer,
        [],
        original_effective_to=transfer.source_registration_original_effective_to,
    )
    scalar_keys = {
        "version",
        "workspace_id",
        "player_id",
        "source_registration_id",
        "source_club_id",
        "destination_club_id",
        "destination_team_id",
        "transfer_type",
        "effective_on",
        "loan_end_on",
        "source_registration_original_effective_to",
    }
    if any(plan.get(key) != expected[key] for key in scalar_keys):
        raise ValidationError(
            {"activation_plan": "Transfer no longer matches its activation plan."}
        )
    return plan


def verify_scheduled_transfer_approval(transfer):
    """Fail closed when an APPROVED replay no longer matches frozen evidence."""

    if transfer.status != UnionPlayerTransfer.Status.APPROVED:
        raise ValidationError({"status": "Transfer is not awaiting activation."})
    if (
        transfer.reviewed_by_id is None
        or transfer.reviewed_at is None
        or not transfer.decision_reason.strip()
    ):
        raise ValidationError({"status": "Scheduled transfer lacks approval evidence."})
    if transfer.destination_registration_id is not None:
        raise ValidationError(
            {"status": "Scheduled transfer already has a destination registration."}
        )
    plan = _verify_plan_shape(transfer)
    affected = _current_affected_eligibilities(transfer)
    if (
        build_player_transfer_activation_plan(
            transfer,
            affected,
            original_effective_to=(transfer.source_registration_original_effective_to),
        )
        != plan
    ):
        raise ValidationError(
            {"activation_plan": "Current evidence differs from the approved plan."}
        )
    if UnionPlayerCompetitionEligibility.objects.filter(
        source_transfer=transfer
    ).exists():
        raise ValidationError(
            {"status": "Scheduled transfer already has destination eligibility."}
        )
    return transfer


def _current_affected_eligibilities(transfer):
    return list(
        UnionPlayerCompetitionEligibility.objects.select_for_update(of=("self",))
        .filter(
            registration=transfer.source_registration,
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


def _validate_activation_evidence(transfer, plan, affected):
    actual_plan = build_player_transfer_activation_plan(
        transfer,
        affected,
        original_effective_to=transfer.source_registration_original_effective_to,
    )
    if actual_plan != plan:
        raise ValidationError(
            {
                "activation_plan": "Current transfer evidence differs from the approved plan."
            }
        )
    if transfer.player.status != UnionPlayer.Status.APPROVED:
        raise ValidationError({"player": "Player identity is no longer approved."})
    if transfer.source_registration.status != UnionPlayerRegistration.Status.ACTIVE:
        raise ValidationError(
            {"source_registration": "Source registration is no longer active."}
        )
    if (
        UnionPlayerRegistration.objects.filter(
            player=transfer.player,
            status=UnionPlayerRegistration.Status.ACTIVE,
        )
        .exclude(pk=transfer.source_registration_id)
        .exists()
    ):
        raise ValidationError(
            {
                "source_registration": "Another active registration exists for the player."
            }
        )
    if not _active_affiliation(
        transfer.workspace,
        transfer.source_registration.club,
    ) or not _active_affiliation(transfer.workspace, transfer.destination_club):
        raise ValidationError(
            {"club": "Both Clubs require active workspace affiliations at activation."}
        )
    workspace_union_id = transfer.workspace.related_union_id
    for eligibility in affected:
        if (
            eligibility.workspace_id != transfer.workspace_id
            or eligibility.player_id != transfer.player_id
            or eligibility.registration_id != transfer.source_registration_id
            or eligibility.club_id != transfer.source_registration.club_id
            or eligibility.competition_identity.union_id != workspace_union_id
            or eligibility.competition_edition.identity_id
            != eligibility.competition_identity_id
            or eligibility.competition_edition.competition.league.union_id
            != workspace_union_id
        ):
            raise ValidationError(
                {
                    "eligibility": "Affected eligibility no longer matches the approved plan."
                }
            )
    if transfer.destination_registration_id is not None:
        raise ValidationError(
            {"destination_registration": "Transfer already has destination evidence."}
        )
    if UnionPlayerCompetitionEligibility.objects.filter(
        source_transfer=transfer
    ).exists():
        raise ValidationError(
            {"eligibility": "Transfer already has destination eligibility evidence."}
        )


def _verify_activated_replay(transfer):
    if (
        transfer.status == UnionPlayerTransfer.Status.COMPLETED
        and transfer.transfer_type == "LOAN"
    ):
        from .union_player_transfer_return_services import (
            verify_completed_player_loan_return,
        )

        return verify_completed_player_loan_return(transfer)
    plan = transfer.activation_plan or {}
    if plan.get("version") != ACTIVATION_PLAN_VERSION:
        raise ValidationError(
            {"activation_plan": "Activated transfer lacks a supported plan."}
        )
    expected_scalar_plan = build_player_transfer_activation_plan(
        transfer,
        [],
        original_effective_to=transfer.source_registration_original_effective_to,
    )
    scalar_keys = {
        "version",
        "workspace_id",
        "player_id",
        "source_registration_id",
        "source_club_id",
        "destination_club_id",
        "destination_team_id",
        "transfer_type",
        "effective_on",
        "loan_end_on",
        "source_registration_original_effective_to",
    }
    if any(plan.get(key) != expected_scalar_plan[key] for key in scalar_keys):
        raise ValidationError(
            {"activation_plan": "Activated transfer no longer matches its plan."}
        )
    if transfer.player.status != UnionPlayer.Status.APPROVED:
        raise ValidationError(
            {"status": "Activated transfer player is no longer approved."}
        )
    if transfer.status == UnionPlayerTransfer.Status.COMPLETED:
        if transfer.transfer_type not in {"PERMANENT", "FREE_TRANSFER"}:
            raise ValidationError(
                {"status": "Completed transfer has an unsupported transfer type."}
            )
        destination, destination_eligibilities = _verify_completed_transfer(transfer)
        if (
            destination.status != UnionPlayerRegistration.Status.ACTIVE
            or destination.effective_to
            != transfer.source_registration_original_effective_to
            or transfer.source_registration.status
            != UnionPlayerRegistration.Status.TRANSFERRED
            or transfer.source_registration.effective_to
            != transfer.effective_on - timedelta(days=1)
            or transfer.activated_at is None
            or transfer.completed_at is None
        ):
            raise ValidationError(
                {"status": "Completed transfer has inconsistent activation evidence."}
            )
    elif transfer.status == UnionPlayerTransfer.Status.LOAN_ACTIVE:
        if transfer.transfer_type != "LOAN":
            raise ValidationError(
                {"status": "Active loan has an inconsistent transfer type."}
            )
        destination, destination_eligibilities = _verify_completed_transfer(transfer)
        if (
            destination.status != UnionPlayerRegistration.Status.ACTIVE
            or destination.effective_to != transfer.loan_end_on
            or transfer.source_registration.status
            != UnionPlayerRegistration.Status.SUSPENDED
            or transfer.source_registration.effective_to
            != transfer.effective_on - timedelta(days=1)
            or transfer.activated_at is None
            or transfer.completed_at is not None
        ):
            raise ValidationError(
                {"status": "Active loan has inconsistent activation evidence."}
            )
    else:
        raise ValidationError({"status": "Transfer has not been activated."})
    if sorted(
        {
            eligibility.competition_edition_id
            for eligibility in destination_eligibilities
        }
    ) != plan.get("competition_edition_ids", []):
        raise ValidationError(
            {"status": "Activated eligibility no longer matches the approved plan."}
        )
    if transfer.status == UnionPlayerTransfer.Status.LOAN_ACTIVE:
        expected_return_plan = build_player_loan_return_plan(
            transfer,
            destination_registration=destination,
            destination_eligibilities=destination_eligibilities,
        )
        if transfer.return_plan != expected_return_plan:
            raise ValidationError(
                {"return_plan": "Active loan no longer matches its frozen return plan."}
            )
        if (
            transfer.return_registration_id is not None
            or transfer.returned_at is not None
            or transfer.completed_at is not None
            or UnionPlayerCompetitionEligibility.objects.filter(
                source_loan_return=transfer
            ).exists()
        ):
            raise ValidationError(
                {"status": "Active loan already has return-leg evidence."}
            )
    planned_source_rows = list(
        UnionPlayerCompetitionEligibility.objects.select_for_update(of=("self",))
        .filter(pk__in=plan.get("affected_eligibility_ids", []))
        .order_by("id")
    )
    if len(planned_source_rows) != len(plan.get("affected_eligibility_ids", [])) or any(
        row.status in AFFECTED_ELIGIBILITY_STATUSES for row in planned_source_rows
    ):
        raise ValidationError(
            {"status": "Activated source eligibility evidence is inconsistent."}
        )
    return _result(
        transfer,
        destination_registration=destination,
        destination_eligibilities=destination_eligibilities,
        idempotent_replay=True,
        activation_scheduled=False,
    )


def _create_destination_eligibilities(
    *,
    transfer,
    destination_registration,
    source_eligibilities,
):
    destination_eligibilities = []
    for source_eligibility in source_eligibilities:
        previous_status = source_eligibility.status
        if previous_status == UnionPlayerCompetitionEligibility.Status.PENDING:
            source_eligibility.status = (
                UnionPlayerCompetitionEligibility.Status.CANCELLED
            )
            source_eligibility.decision_reason = (
                "Closed because the player activated a Club transfer."
            )
            reason_field = "decision_reason"
        else:
            source_eligibility.status = UnionPlayerCompetitionEligibility.Status.EXPIRED
            source_eligibility.restriction_reason = (
                "Closed because the player activated a Club transfer."
            )
            reason_field = "restriction_reason"
        source_eligibility.save(update_fields=["status", reason_field, "updated_at"])
        log_union_audit_event(
            workspace=transfer.workspace,
            actor=transfer.reviewed_by,
            action="competition_eligibility.closed_for_transfer",
            target=source_eligibility,
            metadata=_eligibility_metadata(
                source_eligibility,
                previous_status=previous_status,
            ),
        )
        destination = UnionPlayerCompetitionEligibility.objects.create(
            workspace=transfer.workspace,
            player=transfer.player,
            registration=destination_registration,
            source_submission=None,
            source_transfer=transfer,
            club=transfer.destination_club,
            team=transfer.destination_team,
            competition_identity=source_eligibility.competition_identity,
            competition_edition=source_eligibility.competition_edition,
            season=source_eligibility.season,
            status=UnionPlayerCompetitionEligibility.Status.PENDING,
            warnings=_safe_warnings(source_eligibility.warnings),
        )
        log_union_audit_event(
            workspace=transfer.workspace,
            actor=transfer.reviewed_by,
            action="competition_eligibility.pending_created_for_transfer",
            target=destination,
            metadata=_eligibility_metadata(destination),
        )
        destination_eligibilities.append(destination)
    return destination_eligibilities


@transaction.atomic
def activate_approved_player_transfer(*, transfer_id, as_of=None):
    """Activate a due approved transfer or verify an already activated replay."""

    effective_as_of = as_of or timezone.localdate()
    transfer = _locked_transfer(transfer_id)
    if transfer.status in {
        UnionPlayerTransfer.Status.COMPLETED,
        UnionPlayerTransfer.Status.LOAN_ACTIVE,
    }:
        return _verify_activated_replay(transfer)
    if transfer.status != UnionPlayerTransfer.Status.APPROVED:
        raise ValidationError({"status": "Only an approved transfer may activate."})
    if transfer.effective_on > effective_as_of:
        raise ValidationError({"effective_on": "Transfer is not due for activation."})
    if transfer.transfer_type not in ACTIVATABLE_TRANSFER_TYPES:
        raise ValidationError({"transfer_type": "Unsupported activation type."})

    if (
        transfer.reviewed_by_id is None
        or transfer.reviewed_at is None
        or not transfer.decision_reason.strip()
    ):
        raise ValidationError({"status": "Approved transfer lacks decision evidence."})
    plan = _verify_plan_shape(transfer)
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
    planned_ids = plan.get("affected_eligibility_ids")
    if not isinstance(planned_ids, list) or any(
        not isinstance(value, int) for value in planned_ids
    ):
        raise ValidationError(
            {"activation_plan": "Planned eligibility IDs are invalid."}
        )
    list(
        UnionPlayerCompetitionEligibility.objects.select_for_update(of=("self",))
        .filter(pk__in=planned_ids)
        .order_by("id")
    )
    if transfer.destination_registration_id is not None:
        UnionPlayerRegistration.objects.select_for_update(of=("self",)).filter(
            pk=transfer.destination_registration_id
        ).first()
    affected = _current_affected_eligibilities(transfer)
    list(
        UnionPlayerCompetitionEligibility.objects.select_for_update(of=("self",))
        .filter(source_transfer=transfer)
        .order_by("id")
    )
    _validate_activation_evidence(transfer, plan, affected)

    previous_status = transfer.status
    now = timezone.now()
    source_registration = transfer.source_registration
    if transfer.transfer_type == "LOAN":
        source_registration.status = UnionPlayerRegistration.Status.SUSPENDED
        destination_effective_to = transfer.loan_end_on
        destination_status = UnionPlayerTransfer.Status.LOAN_ACTIVE
    else:
        source_registration.status = UnionPlayerRegistration.Status.TRANSFERRED
        destination_effective_to = transfer.source_registration_original_effective_to
        destination_status = UnionPlayerTransfer.Status.COMPLETED
    source_registration.effective_to = transfer.effective_on - timedelta(days=1)
    source_registration.save(update_fields=["status", "effective_to", "updated_at"])

    destination_registration = UnionPlayerRegistration.objects.create(
        workspace=transfer.workspace,
        player=transfer.player,
        club=transfer.destination_club,
        team=transfer.destination_team,
        season=source_registration.season,
        status=UnionPlayerRegistration.Status.ACTIVE,
        registration_type=transfer.transfer_type,
        effective_from=transfer.effective_on,
        effective_to=destination_effective_to,
        approved_by=transfer.reviewed_by,
        approved_at=transfer.reviewed_at,
        decision_reason=transfer.decision_reason,
        predecessor=source_registration,
    )
    transfer.destination_registration = destination_registration
    transfer.status = destination_status
    transfer.activated_at = now
    transfer.completed_at = (
        now if destination_status == UnionPlayerTransfer.Status.COMPLETED else None
    )
    transfer.save(
        update_fields=[
            "destination_registration",
            "status",
            "activated_at",
            "completed_at",
            "updated_at",
        ]
    )
    destination_eligibilities = _create_destination_eligibilities(
        transfer=transfer,
        destination_registration=destination_registration,
        source_eligibilities=affected,
    )
    if transfer.transfer_type == "LOAN":
        transfer.return_plan = build_player_loan_return_plan(
            transfer,
            destination_registration=destination_registration,
            destination_eligibilities=destination_eligibilities,
        )
        transfer.save(update_fields=["return_plan", "updated_at"])

    metadata = _activation_metadata(transfer, previous_status=previous_status)
    log_union_audit_event(
        workspace=transfer.workspace,
        actor=transfer.reviewed_by,
        action="union_player_transfer.activated",
        target=transfer,
        metadata=metadata,
    )
    if transfer.transfer_type == "LOAN":
        events = (
            ("union_player_transfer.loan_started", transfer),
            ("union_player_registration.loaned_out", source_registration),
            (
                "union_player_registration.loan_destination_created",
                destination_registration,
            ),
        )
        title = "Player loan started"
        message = "The approved player loan has started."
    else:
        events = (
            ("union_player_transfer.completed", transfer),
            ("union_player_registration.transferred_out", source_registration),
            (
                "union_player_registration.transfer_successor_created",
                destination_registration,
            ),
        )
        title = "Player transfer completed"
        message = "The approved player transfer has completed."
    for action, target in events:
        log_union_audit_event(
            workspace=transfer.workspace,
            actor=transfer.reviewed_by,
            action=action,
            target=target,
            metadata=metadata,
        )
    _schedule_notifications(
        transfer,
        reviewer=transfer.reviewed_by,
        title=title,
        message=message,
    )
    return _result(
        transfer,
        destination_registration=destination_registration,
        destination_eligibilities=destination_eligibilities,
        idempotent_replay=False,
        activation_scheduled=False,
    )


def _neutral_failure_message(exc):
    if isinstance(exc, ValidationError) and exc.messages:
        return str(exc.messages[0])
    return "Transfer activation failed."


def process_due_player_transfer_activations(*, as_of=None, limit=None):
    effective_as_of = as_of or timezone.localdate()
    if limit is not None and (not isinstance(limit, int) or limit <= 0):
        raise ValidationError({"limit": "Limit must be a positive integer."})
    queryset = UnionPlayerTransfer.objects.filter(
        status=UnionPlayerTransfer.Status.APPROVED,
        effective_on__lte=effective_as_of,
    ).order_by("effective_on", "id")
    due_count = queryset.count()
    transfer_ids = list(
        queryset.values_list("id", flat=True)[:limit]
        if limit is not None
        else queryset.values_list("id", flat=True)
    )
    activated_ids = []
    failures = []
    for transfer_id in transfer_ids:
        try:
            result = activate_approved_player_transfer(
                transfer_id=transfer_id,
                as_of=effective_as_of,
            )
            if not result["idempotent_replay"]:
                activated_ids.append(transfer_id)
        except Exception as exc:
            failures.append(
                {
                    "transfer_id": transfer_id,
                    "error": _neutral_failure_message(exc),
                }
            )
    return {
        "as_of": effective_as_of,
        "due_count": due_count,
        "activated_count": len(activated_ids),
        "failed_count": len(failures),
        "activated_transfer_ids": activated_ids,
        "failures": failures,
    }
