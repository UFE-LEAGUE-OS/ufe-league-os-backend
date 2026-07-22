"""Central workspace and resource-scope enforcement for Union operations."""

from django.core.exceptions import ValidationError

SCOPE_KEYS = {
    "competition": "competition_ids",
    "competition_identity": "competition_identity_ids",
    "competition_edition": "competition_edition_ids",
    "club": "club_ids",
    "national_team": "national_team_ids",
}


def scope_allows(membership, resource_type, resource_id):
    """Return whether a membership's optional scope permits this resource.

    Missing or empty restrictions grant workspace-wide access. A present
    resource key is restrictive, including an intentionally empty list.
    """

    restrictions = membership.scope_restrictions or {}
    key = SCOPE_KEYS.get(resource_type)
    if key is None or key not in restrictions:
        return True
    values = restrictions[key]
    if not isinstance(values, list):
        return False
    return str(resource_id) in {str(value) for value in values}


def require_scope(membership, resource_type, resource_id):
    if not scope_allows(membership, resource_type, resource_id):
        raise ValidationError(
            {"scope": "This resource is outside your assigned scope."}
        )


def subject_belongs_to_workspace(workspace, subject_type, subject_id):
    """Verify a supported generic governance subject without trusting its ID."""

    from .models import (
        ClubAffiliation,
        CompetitionEdition,
        CompetitionIdentity,
        NationalTeam,
        UnionPlayerRegistration,
        UnionPlayerTransfer,
        UnionRegistrationApplication,
    )

    queries = {
        "club_affiliation": ClubAffiliation.objects.filter(
            pk=subject_id, workspace=workspace
        ),
        "competition_identity": CompetitionIdentity.objects.filter(
            pk=subject_id, union=workspace.related_union
        ),
        "competition_edition": CompetitionEdition.objects.filter(
            pk=subject_id, identity__union=workspace.related_union
        ),
        "national_team": NationalTeam.objects.filter(
            pk=subject_id, workspace=workspace
        ),
        "player_registration": UnionPlayerRegistration.objects.filter(
            pk=subject_id, workspace=workspace
        ),
        "transfer": UnionPlayerTransfer.objects.filter(
            pk=subject_id, workspace=workspace
        ),
        "registration_application": UnionRegistrationApplication.objects.filter(
            pk=subject_id, workspace=workspace
        ),
    }
    queryset = queries.get(subject_type)
    return queryset.exists() if queryset is not None else False
