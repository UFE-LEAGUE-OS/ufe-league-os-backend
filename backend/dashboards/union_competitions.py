"""Lifecycle services for permanent competitions and their season editions."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify
from django.utils import timezone

from .models import Competition, CompetitionEdition, LeagueClubMembership
from .union_governance import log_union_audit_event, transition_status

COMPETITION_EDITION_TRANSITIONS = {
    CompetitionEdition.Status.DRAFT: {
        CompetitionEdition.Status.REGISTRATION_OPEN,
        CompetitionEdition.Status.CANCELLED,
    },
    CompetitionEdition.Status.REGISTRATION_OPEN: {
        CompetitionEdition.Status.REGISTRATION_CLOSED,
        CompetitionEdition.Status.CANCELLED,
    },
    CompetitionEdition.Status.REGISTRATION_CLOSED: {
        CompetitionEdition.Status.ENTRIES_UNDER_REVIEW,
        CompetitionEdition.Status.SCHEDULING,
        CompetitionEdition.Status.CANCELLED,
    },
    CompetitionEdition.Status.ENTRIES_UNDER_REVIEW: {
        CompetitionEdition.Status.SCHEDULING,
        CompetitionEdition.Status.CANCELLED,
    },
    CompetitionEdition.Status.SCHEDULING: {
        CompetitionEdition.Status.READY_FOR_PUBLICATION,
        CompetitionEdition.Status.CANCELLED,
    },
    CompetitionEdition.Status.READY_FOR_PUBLICATION: {
        CompetitionEdition.Status.PUBLISHED,
        CompetitionEdition.Status.SCHEDULING,
        CompetitionEdition.Status.CANCELLED,
    },
    CompetitionEdition.Status.PUBLISHED: {
        CompetitionEdition.Status.ACTIVE,
        CompetitionEdition.Status.CANCELLED,
    },
    CompetitionEdition.Status.ACTIVE: {
        CompetitionEdition.Status.COMPLETED,
        CompetitionEdition.Status.CANCELLED,
    },
    CompetitionEdition.Status.COMPLETED: {CompetitionEdition.Status.ARCHIVED},
    CompetitionEdition.Status.ARCHIVED: set(),
    CompetitionEdition.Status.CANCELLED: set(),
}


def _competition_slug(league, identity, season):
    base = slugify(f"{identity.slug}-{season.slug}")[:190] or "competition"
    slug = base
    suffix = 2
    while Competition.objects.filter(league=league, slug=slug).exists():
        slug = f"{base[:190 - len(str(suffix))]}-{suffix}"
        suffix += 1
    return slug


@transaction.atomic
def create_competition_edition(
    *, workspace, identity, season, actor, copied_from=None, copy_fields=()
):
    """Create a new edition without mutating any prior season or its records."""

    if (
        not workspace.related_union_id
        or identity.union_id != workspace.related_union_id
    ):
        raise ValidationError(
            {"identity": "Competition identity is outside this workspace."}
        )
    if season.league.union_id != identity.union_id:
        raise ValidationError({"season": "Season is outside the competition Union."})
    if CompetitionEdition.objects.filter(identity=identity, season=season).exists():
        raise ValidationError(
            {"season": "This competition already has an edition for the season."}
        )
    if copied_from and copied_from.identity_id != identity.id:
        raise ValidationError(
            {"copied_from": "Source edition must share the identity."}
        )

    league = identity.primary_league or (
        copied_from.competition.league if copied_from else None
    )
    if league is None:
        raise ValidationError(
            {"identity": "A primary league is required to create an edition."}
        )
    if league.union_id != identity.union_id:
        raise ValidationError(
            {"identity": "Primary league is outside the identity Union."}
        )

    copy_fields = set(copy_fields or ())
    allowed_copy_fields = {"rules", "structure", "eligibility_rules", "clubs"}
    invalid_copy_fields = copy_fields - allowed_copy_fields
    if invalid_copy_fields:
        raise ValidationError(
            {"copy": f"Unsupported copy options: {sorted(invalid_copy_fields)}."}
        )

    source = copied_from
    competition = Competition.objects.create(
        league=league,
        name=identity.name,
        slug=_competition_slug(league, identity, season),
        season=season.name,
        season_record=season,
        is_active=False,
        start_date=season.start_date,
        end_date=season.end_date,
    )
    edition = CompetitionEdition.objects.create(
        identity=identity,
        competition=competition,
        season=season,
        copied_from=source,
        rules=source.rules if source and "rules" in copy_fields else {},
        structure=source.structure if source and "structure" in copy_fields else {},
        eligibility_rules=(
            source.eligibility_rules
            if source and "eligibility_rules" in copy_fields
            else {}
        ),
    )

    if source and "clubs" in copy_fields:
        memberships = LeagueClubMembership.objects.filter(
            league=source.competition.league,
            season=source.season,
            status__in=[
                LeagueClubMembership.Status.ACTIVE,
                LeagueClubMembership.Status.PROMOTED,
            ],
        ).select_related("club")
        LeagueClubMembership.objects.bulk_create(
            [
                LeagueClubMembership(
                    league=league,
                    club=membership.club,
                    season=season,
                    status=LeagueClubMembership.Status.INVITED,
                    notes=f"Copied from edition {source.id}.",
                    created_by=actor,
                )
                for membership in memberships
            ],
            ignore_conflicts=True,
        )

    log_union_audit_event(
        workspace=workspace,
        actor=actor,
        action="competition_edition.created",
        target=edition,
        metadata={
            "identity_id": identity.id,
            "season_id": season.id,
            "copied_from": source.id if source else None,
        },
    )
    return edition


@transaction.atomic
def transition_competition_edition(*, edition, target_status, actor, workspace, reason):
    """Change lifecycle status and keep the legacy public competition flag aligned."""

    edition = transition_status(
        instance=edition,
        target_status=target_status,
        allowed_transitions=COMPETITION_EDITION_TRANSITIONS,
        actor=actor,
        workspace=workspace,
        reason=reason,
    )
    if target_status == CompetitionEdition.Status.PUBLISHED:
        edition.published_at = timezone.now()
        edition.published_by = actor
        edition.save(update_fields=["published_at", "published_by", "updated_at"])
    if target_status in {
        CompetitionEdition.Status.PUBLISHED,
        CompetitionEdition.Status.ACTIVE,
    }:
        edition.competition.is_active = True
    elif target_status in {
        CompetitionEdition.Status.ARCHIVED,
        CompetitionEdition.Status.CANCELLED,
    }:
        edition.competition.is_active = False
    else:
        return edition
    edition.competition.save(update_fields=["is_active", "updated_at"])
    return edition
