"""Scheduled completion of maintained player-loan return legs."""

from datetime import timedelta
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
)
from .union_governance import log_union_audit_event
from .union_player_transfer_activation_services import (
    ACTIVATION_PLAN_VERSION,
    LOAN_RETURN_PLAN_VERSION,
    build_player_transfer_activation_plan,
    build_player_loan_return_plan,
)
from .union_player_transfer_review_services import (
    AFFECTED_ELIGIBILITY_STATUSES,
    _eligibility_metadata,
    _notification_user_ids,
    _safe_warnings,
)
from .union_player_transfer_services import _active_affiliation, _audit_metadata

RETURN_REGISTRATION_TYPE = "END_OF_LOAN"


def _date_value(value):
    return value.isoformat() if value is not None else None


def _locked_transfer(transfer_id):
    transfer = (
        UnionPlayerTransfer.objects.select_for_update(of=("self",))
        .select_related(
            "workspace__related_union",
            "player__user",
            "source_registration__club__admin",
            "source_registration__team",
            "destination_club__admin",
            "destination_team",
            "destination_registration",
            "return_registration",
            "initiated_by",
            "reviewed_by",
        )
        .get(pk=transfer_id)
    )
    transfer.source_registration = (
        UnionPlayerRegistration.objects.select_for_update(of=("self",))
        .select_related("workspace", "player", "club", "team", "season")
        .get(pk=transfer.source_registration_id)
    )
    if transfer.destination_registration_id is not None:
        transfer.destination_registration = (
            UnionPlayerRegistration.objects.select_for_update(of=("self",))
            .select_related("workspace", "player", "club", "team", "season")
            .get(pk=transfer.destination_registration_id)
        )
    if transfer.return_registration_id is not None:
        transfer.return_registration = (
            UnionPlayerRegistration.objects.select_for_update(of=("self",))
            .select_related("workspace", "player", "club", "team", "season")
            .get(pk=transfer.return_registration_id)
        )
    return transfer


def _destination_eligibilities(transfer):
    return list(
        UnionPlayerCompetitionEligibility.objects.select_for_update(of=("self",))
        .filter(source_transfer=transfer)
        .select_related(
            "competition_identity",
            "competition_edition",
            "season",
        )
        .order_by("competition_edition_id", "id")
    )


def _return_eligibilities(transfer):
    return list(
        UnionPlayerCompetitionEligibility.objects.select_for_update(of=("self",))
        .filter(source_loan_return=transfer)
        .select_related(
            "competition_identity",
            "competition_edition",
            "registration",
            "season",
        )
        .order_by("competition_edition_id", "id")
    )


def _return_result(
    transfer,
    *,
    return_eligibilities,
    idempotent_replay,
):
    return {
        "transfer": transfer,
        "source_registration": transfer.source_registration,
        "destination_registration": transfer.destination_registration,
        "return_registration": transfer.return_registration,
        "return_eligibilities": return_eligibilities,
        "idempotent_replay": idempotent_replay,
    }


def _validate_return_plan(transfer, destination_eligibilities):
    plan = transfer.return_plan or {}
    if plan.get("version") != LOAN_RETURN_PLAN_VERSION:
        raise ValidationError(
            {"return_plan": "Loan return plan is missing or unsupported."}
        )
    expected = build_player_loan_return_plan(
        transfer,
        destination_registration=transfer.destination_registration,
        destination_eligibilities=destination_eligibilities,
    )
    if plan != expected:
        raise ValidationError(
            {
                "return_plan": "Current loan evidence differs from the frozen return plan."
            }
        )
    return plan


def _validate_activation_plan(transfer, destination_eligibilities):
    plan = transfer.activation_plan or {}
    if plan.get("version") != ACTIVATION_PLAN_VERSION:
        raise ValidationError(
            {"activation_plan": "Loan activation plan is missing or unsupported."}
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
            {"activation_plan": "Completed loan no longer matches its activation plan."}
        )
    if sorted(
        {item.competition_identity_id for item in destination_eligibilities}
    ) != plan.get("competition_identity_ids", []) or sorted(
        {item.competition_edition_id for item in destination_eligibilities}
    ) != plan.get(
        "competition_edition_ids", []
    ):
        raise ValidationError(
            {"activation_plan": "Completed loan eligibility differs from its plan."}
        )
    source_rows = list(
        UnionPlayerCompetitionEligibility.objects.select_for_update(of=("self",))
        .filter(pk__in=plan.get("affected_eligibility_ids", []))
        .order_by("id")
    )
    if [item.id for item in source_rows] != plan.get(
        "affected_eligibility_ids", []
    ) or any(item.status in AFFECTED_ELIGIBILITY_STATUSES for item in source_rows):
        raise ValidationError(
            {"activation_plan": "Completed loan source eligibility is inconsistent."}
        )


def _validate_active_loan_return(transfer, plan, destination_eligibilities):
    if transfer.workspace.status != UnionWorkspace.Status.ACTIVE or (
        transfer.workspace.related_union_id is None
    ):
        raise ValidationError(
            {"workspace": "An active Union-linked workspace is required."}
        )
    if (
        transfer.player.union_id != transfer.workspace.related_union_id
        or transfer.player.status != UnionPlayer.Status.APPROVED
    ):
        raise ValidationError(
            {"player": "Player must remain approved in the workspace Union."}
        )
    source = transfer.source_registration
    destination = transfer.destination_registration
    if (
        source.status != UnionPlayerRegistration.Status.SUSPENDED
        or source.effective_to != transfer.effective_on - timedelta(days=1)
        or source.workspace_id != transfer.workspace_id
        or source.player_id != transfer.player_id
        or source.club_id != plan["source_club_id"]
        or source.team_id != plan["source_team_id"]
    ):
        raise ValidationError(
            {"source_registration": "Pre-loan source evidence is inconsistent."}
        )
    if (
        destination is None
        or destination.status != UnionPlayerRegistration.Status.ACTIVE
        or destination.workspace_id != transfer.workspace_id
        or destination.player_id != transfer.player_id
        or destination.club_id != transfer.destination_club_id
        or destination.team_id != transfer.destination_team_id
        or destination.registration_type != "LOAN"
        or destination.effective_from != transfer.effective_on
        or destination.effective_to != transfer.loan_end_on
        or destination.predecessor_id != source.id
    ):
        raise ValidationError(
            {"destination_registration": "Destination loan evidence is inconsistent."}
        )
    active_ids = list(
        UnionPlayerRegistration.objects.select_for_update(of=("self",))
        .filter(
            player=transfer.player,
            status=UnionPlayerRegistration.Status.ACTIVE,
        )
        .order_by("id")
        .values_list("id", flat=True)
    )
    if active_ids != [destination.id]:
        raise ValidationError(
            {
                "destination_registration": "Destination loan must be the only active row."
            }
        )
    if not _active_affiliation(transfer.workspace, source.club):
        raise ValidationError(
            {"source_club": "Source Club requires an active workspace affiliation."}
        )
    if source.team_id is not None and source.team.club_id != source.club_id:
        raise ValidationError(
            {"source_team": "Source team no longer belongs to the source Club."}
        )
    original_expiry = transfer.source_registration_original_effective_to
    return_effective_on = transfer.loan_end_on + timedelta(days=1)
    if original_expiry is not None and return_effective_on > original_expiry:
        raise ValidationError(
            {"return_effective_on": "Return date exceeds the original registration."}
        )
    if (
        sorted(item.id for item in destination_eligibilities)
        != plan["destination_eligibility_ids"]
    ):
        raise ValidationError(
            {"eligibility": "Destination eligibility set differs from the return plan."}
        )
    for eligibility in destination_eligibilities:
        if (
            eligibility.workspace_id != transfer.workspace_id
            or eligibility.player_id != transfer.player_id
            or eligibility.registration_id != destination.id
            or eligibility.club_id != transfer.destination_club_id
            or eligibility.team_id != transfer.destination_team_id
            or eligibility.competition_identity_id
            not in plan["competition_identity_ids"]
            or eligibility.competition_edition_id not in plan["competition_edition_ids"]
        ):
            raise ValidationError(
                {"eligibility": "Destination eligibility evidence is inconsistent."}
            )
    if (
        transfer.return_registration_id is not None
        or transfer.returned_at is not None
        or transfer.completed_at is not None
        or UnionPlayerCompetitionEligibility.objects.filter(
            source_loan_return=transfer
        ).exists()
    ):
        raise ValidationError({"status": "Loan already has return-leg evidence."})


def verify_completed_player_loan_return(transfer):
    """Verify completed-loan replay evidence without creating new rows."""

    if (
        transfer.status != UnionPlayerTransfer.Status.COMPLETED
        or transfer.transfer_type != "LOAN"
    ):
        raise ValidationError({"status": "Transfer is not a completed loan return."})
    transfer.source_registration = (
        UnionPlayerRegistration.objects.select_for_update(of=("self",))
        .select_related("workspace", "player", "club", "team", "season")
        .get(pk=transfer.source_registration_id)
    )
    if transfer.destination_registration_id is not None:
        transfer.destination_registration = (
            UnionPlayerRegistration.objects.select_for_update(of=("self",))
            .select_related("workspace", "player", "club", "team", "season")
            .get(pk=transfer.destination_registration_id)
        )
    if transfer.return_registration_id is not None:
        transfer.return_registration = (
            UnionPlayerRegistration.objects.select_for_update(of=("self",))
            .select_related("workspace", "player", "club", "team", "season")
            .get(pk=transfer.return_registration_id)
        )
    destination_eligibilities = _destination_eligibilities(transfer)
    _validate_activation_plan(transfer, destination_eligibilities)
    plan = _validate_return_plan(transfer, destination_eligibilities)
    source = transfer.source_registration
    destination = transfer.destination_registration
    returned = transfer.return_registration
    return_effective_on = transfer.loan_end_on + timedelta(days=1)
    if (
        source.status != UnionPlayerRegistration.Status.SUSPENDED
        or source.effective_to != transfer.effective_on - timedelta(days=1)
        or destination is None
        or destination.status != UnionPlayerRegistration.Status.EXPIRED
        or destination.effective_to != transfer.loan_end_on
        or destination.predecessor_id != source.id
        or returned is None
        or returned.status != UnionPlayerRegistration.Status.ACTIVE
        or returned.workspace_id != transfer.workspace_id
        or returned.player_id != transfer.player_id
        or returned.club_id != source.club_id
        or returned.team_id != source.team_id
        or returned.registration_type != RETURN_REGISTRATION_TYPE
        or returned.effective_from != return_effective_on
        or returned.effective_to != transfer.source_registration_original_effective_to
        or returned.predecessor_id != destination.id
        or transfer.returned_at is None
        or transfer.completed_at is None
    ):
        raise ValidationError(
            {"status": "Completed loan has inconsistent return evidence."}
        )
    return_eligibilities = _return_eligibilities(transfer)
    destination_by_edition = {
        item.competition_edition_id: item for item in destination_eligibilities
    }
    if sorted(item.competition_edition_id for item in return_eligibilities) != plan[
        "competition_edition_ids"
    ] or any(
        item.workspace_id != transfer.workspace_id
        or item.player_id != transfer.player_id
        or item.registration_id != returned.id
        or item.club_id != source.club_id
        or item.team_id != source.team_id
        or item.source_loan_return_id != transfer.id
        or item.source_submission_id is not None
        or item.source_transfer_id is not None
        or item.competition_identity_id
        != destination_by_edition[item.competition_edition_id].competition_identity_id
        or item.season_id
        != destination_by_edition[item.competition_edition_id].season_id
        for item in return_eligibilities
    ):
        raise ValidationError(
            {"status": "Completed loan has inconsistent return eligibility."}
        )
    return _return_result(
        transfer,
        return_eligibilities=return_eligibilities,
        idempotent_replay=True,
    )


def _eligibility_return_metadata(eligibility, transfer, *, previous_status=None):
    return {
        **_eligibility_metadata(
            eligibility,
            previous_status=previous_status,
        ),
        "transfer_id": transfer.id,
        "return_registration_id": transfer.return_registration_id,
        "return_effective_on": _date_value(transfer.loan_end_on + timedelta(days=1)),
    }


def _return_audit_metadata(transfer, *, previous_status):
    return {
        **_audit_metadata(transfer, previous_status=previous_status),
        "destination_registration_id": transfer.destination_registration_id,
        "return_registration_id": transfer.return_registration_id,
        "loan_end_on": _date_value(transfer.loan_end_on),
        "return_effective_on": _date_value(transfer.loan_end_on + timedelta(days=1)),
    }


def _notify_return_user(user_id, transfer_id):
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
            title="Player loan completed",
            message=(
                "The loan ended, the destination registration expired, and the "
                "player returned to the source Club. Competition eligibility "
                "requires fresh Union review."
            ),
            action_url="",
            metadata={
                "transfer_id": transfer.id,
                "player_id": transfer.player_id,
                "source_club_id": transfer.source_registration.club_id,
                "destination_club_id": transfer.destination_club_id,
                "status": transfer.status,
                "destination_registration_id": transfer.destination_registration_id,
                "return_registration_id": transfer.return_registration_id,
                "return_effective_on": _date_value(
                    transfer.loan_end_on + timedelta(days=1)
                ),
            },
        )
    except Exception:
        # Post-commit notification failure cannot reverse a loan return.
        return


def _schedule_return_notifications(transfer):
    for user_id in sorted(_notification_user_ids(transfer)):
        if user_id == transfer.reviewed_by_id:
            continue
        transaction.on_commit(partial(_notify_return_user, user_id, transfer.id))


def _create_return_eligibilities(
    transfer,
    *,
    return_registration,
    destination_eligibilities,
):
    created_rows = []
    close_reason = "Closed because the approved player loan ended."
    for destination in destination_eligibilities:
        previous_status = destination.status
        if previous_status == UnionPlayerCompetitionEligibility.Status.PENDING:
            destination.status = UnionPlayerCompetitionEligibility.Status.CANCELLED
            destination.decision_reason = close_reason
            reason_field = "decision_reason"
        elif previous_status in {
            UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
            UnionPlayerCompetitionEligibility.Status.SUSPENDED,
        }:
            destination.status = UnionPlayerCompetitionEligibility.Status.EXPIRED
            destination.restriction_reason = close_reason
            reason_field = "restriction_reason"
        else:
            reason_field = None
        if reason_field is not None:
            destination.save(update_fields=["status", reason_field, "updated_at"])
            log_union_audit_event(
                workspace=transfer.workspace,
                actor=transfer.reviewed_by,
                action="competition_eligibility.closed_for_loan_return",
                target=destination,
                metadata=_eligibility_return_metadata(
                    destination,
                    transfer,
                    previous_status=previous_status,
                ),
            )
        returned = UnionPlayerCompetitionEligibility.objects.create(
            workspace=transfer.workspace,
            player=transfer.player,
            registration=return_registration,
            source_submission=None,
            source_transfer=None,
            source_loan_return=transfer,
            club=transfer.source_registration.club,
            team=transfer.source_registration.team,
            competition_identity=destination.competition_identity,
            competition_edition=destination.competition_edition,
            season=destination.season,
            status=UnionPlayerCompetitionEligibility.Status.PENDING,
            warnings=_safe_warnings(destination.warnings),
        )
        log_union_audit_event(
            workspace=transfer.workspace,
            actor=transfer.reviewed_by,
            action="competition_eligibility.pending_created_for_loan_return",
            target=returned,
            metadata=_eligibility_return_metadata(returned, transfer),
        )
        created_rows.append(returned)
    return created_rows


@transaction.atomic
def return_loaned_player_to_source(*, transfer_id, as_of=None):
    effective_as_of = as_of or timezone.localdate()
    transfer = _locked_transfer(transfer_id)
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
    if (
        transfer.status == UnionPlayerTransfer.Status.COMPLETED
        and transfer.transfer_type == "LOAN"
    ):
        return verify_completed_player_loan_return(transfer)
    if (
        transfer.status != UnionPlayerTransfer.Status.LOAN_ACTIVE
        or transfer.transfer_type != "LOAN"
    ):
        raise ValidationError({"status": "Only an active loan may be returned."})
    if transfer.loan_end_on >= effective_as_of:
        raise ValidationError({"loan_end_on": "Loan is not due for return."})

    destination_eligibilities = _destination_eligibilities(transfer)
    planned_ids = (transfer.return_plan or {}).get("destination_eligibility_ids", [])
    if not isinstance(planned_ids, list) or any(
        not isinstance(item, int) for item in planned_ids
    ):
        raise ValidationError({"return_plan": "Planned eligibility IDs are invalid."})
    list(
        UnionPlayerCompetitionEligibility.objects.select_for_update(of=("self",))
        .filter(pk__in=planned_ids)
        .order_by("id")
    )
    _return_eligibilities(transfer)
    plan = _validate_return_plan(transfer, destination_eligibilities)
    _validate_active_loan_return(transfer, plan, destination_eligibilities)

    return_effective_on = transfer.loan_end_on + timedelta(days=1)
    destination = transfer.destination_registration
    destination.status = UnionPlayerRegistration.Status.EXPIRED
    destination.effective_to = transfer.loan_end_on
    destination.save(update_fields=["status", "effective_to", "updated_at"])

    return_registration = UnionPlayerRegistration.objects.create(
        workspace=transfer.workspace,
        player=transfer.player,
        club=transfer.source_registration.club,
        team=transfer.source_registration.team,
        season=transfer.source_registration.season,
        status=UnionPlayerRegistration.Status.ACTIVE,
        registration_type=RETURN_REGISTRATION_TYPE,
        effective_from=return_effective_on,
        effective_to=transfer.source_registration_original_effective_to,
        approved_by=transfer.reviewed_by,
        approved_at=transfer.reviewed_at,
        decision_reason=transfer.decision_reason,
        predecessor=destination,
    )
    previous_status = transfer.status
    now = timezone.now()
    transfer.status = UnionPlayerTransfer.Status.COMPLETED
    transfer.return_registration = return_registration
    transfer.returned_at = now
    transfer.completed_at = now
    transfer.save(
        update_fields=[
            "status",
            "return_registration",
            "returned_at",
            "completed_at",
            "updated_at",
        ]
    )
    return_eligibilities = _create_return_eligibilities(
        transfer,
        return_registration=return_registration,
        destination_eligibilities=destination_eligibilities,
    )
    metadata = _return_audit_metadata(
        transfer,
        previous_status=previous_status,
    )
    for action, target in (
        ("union_player_transfer.loan_returned", transfer),
        ("union_player_transfer.completed", transfer),
        ("union_player_registration.loan_destination_expired", destination),
        ("union_player_registration.loan_return_created", return_registration),
    ):
        log_union_audit_event(
            workspace=transfer.workspace,
            actor=transfer.reviewed_by,
            action=action,
            target=target,
            metadata=metadata,
        )
    _schedule_return_notifications(transfer)
    return _return_result(
        transfer,
        return_eligibilities=return_eligibilities,
        idempotent_replay=False,
    )


def _neutral_failure_message(exc):
    if isinstance(exc, ValidationError) and exc.messages:
        return str(exc.messages[0])
    return "Player loan return failed."


def process_due_player_loan_returns(*, as_of=None, limit=None):
    effective_as_of = as_of or timezone.localdate()
    if limit is not None and (not isinstance(limit, int) or limit <= 0):
        raise ValidationError({"limit": "Limit must be a positive integer."})
    queryset = UnionPlayerTransfer.objects.filter(
        status=UnionPlayerTransfer.Status.LOAN_ACTIVE,
        transfer_type="LOAN",
        loan_end_on__lt=effective_as_of,
    ).order_by("loan_end_on", "id")
    due_count = queryset.count()
    transfer_ids = list(
        queryset.values_list("id", flat=True)[:limit]
        if limit is not None
        else queryset.values_list("id", flat=True)
    )
    returned_ids = []
    failures = []
    for transfer_id in transfer_ids:
        try:
            result = return_loaned_player_to_source(
                transfer_id=transfer_id,
                as_of=effective_as_of,
            )
            if not result["idempotent_replay"]:
                returned_ids.append(transfer_id)
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
        "returned_count": len(returned_ids),
        "failed_count": len(failures),
        "returned_transfer_ids": returned_ids,
        "failures": failures,
    }
