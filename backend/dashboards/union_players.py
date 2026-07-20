"""Union player identity, registration, and transfer workflow services."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    UnionPlayer,
    UnionPlayerNumberSequence,
    UnionPlayerRegistration,
    UnionPlayerTransfer,
)
from .union_governance import log_union_audit_event


def _next_union_player_number(union):
    prefix = f"{union.slug.upper()}-P"
    sequence, _ = UnionPlayerNumberSequence.objects.get_or_create(union=union)
    sequence = UnionPlayerNumberSequence.objects.select_for_update().get(pk=sequence.pk)
    value = sequence.next_value
    sequence.next_value = value + 1
    sequence.save(update_fields=["next_value", "updated_at"])
    return f"{prefix}{value:06d}"


@transaction.atomic
def create_or_find_provisional_player(
    *,
    workspace,
    first_name,
    last_name,
    date_of_birth,
    nationality,
    actor,
    identity_reference="",
):
    """Find an existing identity first; only then create a provisional player."""

    if not workspace.related_union_id:
        raise ValidationError({"workspace": "Workspace must be linked to a Union."})
    players = UnionPlayer.objects.select_for_update().filter(
        union=workspace.related_union
    )
    if identity_reference:
        existing = players.filter(identity_reference=identity_reference).first()
        if existing:
            return existing, False
    existing = players.filter(
        first_name__iexact=first_name.strip(),
        last_name__iexact=last_name.strip(),
        date_of_birth=date_of_birth,
    ).first()
    if existing:
        return existing, False

    player = UnionPlayer.objects.create(
        union=workspace.related_union,
        union_player_number=_next_union_player_number(workspace.related_union),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        date_of_birth=date_of_birth,
        nationality=nationality.strip(),
        identity_reference=identity_reference.strip(),
        status=UnionPlayer.Status.PROVISIONAL,
    )
    log_union_audit_event(
        workspace=workspace,
        actor=actor,
        action="union_player.provisional_created",
        target=player,
    )
    return player, True


@transaction.atomic
def approve_player_registration(*, registration_id, reviewer, workspace, reason):
    registration = (
        UnionPlayerRegistration.objects.select_for_update()
        .select_related("player", "workspace")
        .get(pk=registration_id)
    )
    if registration.workspace_id != workspace.id:
        raise ValidationError(
            {"registration": "Registration is outside this workspace."}
        )
    if registration.status != UnionPlayerRegistration.Status.PENDING:
        raise ValidationError({"status": "Only pending registrations can be approved."})
    if not reason.strip():
        raise ValidationError({"reason": "A review reason is required."})
    if UnionPlayerRegistration.objects.filter(
        workspace=workspace,
        player=registration.player,
        status=UnionPlayerRegistration.Status.ACTIVE,
    ).exists():
        raise ValidationError(
            {"player": "Player already has an active Club registration."}
        )

    player = registration.player
    player.status = UnionPlayer.Status.APPROVED
    player.identity_verified_by = reviewer
    player.identity_verified_at = timezone.now()
    player.save(
        update_fields=[
            "status",
            "identity_verified_by",
            "identity_verified_at",
            "updated_at",
        ]
    )
    registration.status = UnionPlayerRegistration.Status.ACTIVE
    registration.approved_by = reviewer
    registration.approved_at = timezone.now()
    registration.notes = reason.strip()
    registration.save(
        update_fields=["status", "approved_by", "approved_at", "notes", "updated_at"]
    )
    log_union_audit_event(
        workspace=workspace,
        actor=reviewer,
        action="union_player_registration.approved",
        target=registration,
        metadata={"player_id": player.id, "reason": reason.strip()},
    )
    return registration


@transaction.atomic
def approve_player_transfer(*, transfer_id, reviewer, workspace, reason):
    """Atomically close the source registration and create a successor record."""

    transfer = (
        UnionPlayerTransfer.objects.select_for_update()
        .select_related("workspace", "player", "source_registration")
        .get(pk=transfer_id)
    )
    if transfer.workspace_id != workspace.id:
        raise ValidationError({"transfer": "Transfer is outside this workspace."})
    if transfer.status == UnionPlayerTransfer.Status.APPROVED:
        successor = UnionPlayerRegistration.objects.filter(
            predecessor=transfer.source_registration,
            club=transfer.destination_club,
            effective_from=transfer.effective_on,
        ).first()
        return transfer, successor
    if transfer.status != UnionPlayerTransfer.Status.UNDER_UNION_REVIEW:
        raise ValidationError(
            {"status": "Only transfers under Union review can be approved."}
        )
    if transfer.source_registration.status != UnionPlayerRegistration.Status.ACTIVE:
        raise ValidationError(
            {"source_registration": "Source registration is no longer active."}
        )
    if not reason.strip():
        raise ValidationError({"reason": "An approval reason is required."})

    source = transfer.source_registration
    source.status = UnionPlayerRegistration.Status.TRANSFERRED
    source.effective_to = transfer.effective_on
    source.save(update_fields=["status", "effective_to", "updated_at"])
    successor = UnionPlayerRegistration.objects.create(
        workspace=workspace,
        player=transfer.player,
        club=transfer.destination_club,
        team=transfer.destination_team,
        status=UnionPlayerRegistration.Status.ACTIVE,
        effective_from=transfer.effective_on,
        approved_by=reviewer,
        approved_at=timezone.now(),
        predecessor=source,
        notes=f"Approved transfer {transfer.id}: {reason.strip()}",
    )
    transfer.status = UnionPlayerTransfer.Status.APPROVED
    transfer.reviewed_by = reviewer
    transfer.reviewed_at = timezone.now()
    transfer.decision_reason = reason.strip()
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
        workspace=workspace,
        actor=reviewer,
        action="union_player_transfer.approved",
        target=transfer,
        metadata={
            "source_registration": source.id,
            "successor_registration": successor.id,
        },
    )
    return transfer, successor
