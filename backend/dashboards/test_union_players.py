from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Club, User
from dashboards.models import (
    Union,
    UnionPlayer,
    UnionPlayerRegistration,
    UnionPlayerTransfer,
    UnionWorkspace,
)
from dashboards.union_players import (
    approve_player_registration,
    approve_player_transfer,
    create_or_find_provisional_player,
)


class UnionPlayerWorkflowTests(TestCase):
    def setUp(self):
        self.union = Union.objects.create(name="Players Union", slug="players-union")
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Players Workspace",
            slug="players-workspace",
            acronym="PW",
            sport="Football",
        )
        self.reviewer = User.objects.create_user(
            email="player-reviewer@leagueos.test",
            password="StrongPass123!",
            first_name="Player",
            last_name="Reviewer",
        )
        self.source_club = Club.objects.create(
            name="Source Club",
            slug="source-club",
            sport=Club.Sport.FOOTBALL,
        )
        self.destination_club = Club.objects.create(
            name="Destination Club",
            slug="destination-club",
            sport=Club.Sport.FOOTBALL,
        )

    def test_same_identity_evidence_reuses_permanent_union_player(self):
        first, created = create_or_find_provisional_player(
            workspace=self.workspace,
            first_name="Amina",
            last_name="Nambassa",
            date_of_birth=date(2001, 5, 4),
            nationality="Ugandan",
            identity_reference="NIN-123",
            actor=self.reviewer,
        )
        second, duplicate_created = create_or_find_provisional_player(
            workspace=self.workspace,
            first_name="Amina",
            last_name="Nambassa",
            date_of_birth=date(2001, 5, 4),
            nationality="Ugandan",
            identity_reference="NIN-123",
            actor=self.reviewer,
        )
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(first.id, second.id)
        self.assertEqual(UnionPlayer.objects.count(), 1)

    def test_approval_activates_one_club_registration_and_preserves_transfer_history(
        self,
    ):
        player, _ = create_or_find_provisional_player(
            workspace=self.workspace,
            first_name="Musa",
            last_name="Kato",
            date_of_birth=date(1999, 7, 1),
            nationality="Ugandan",
            actor=self.reviewer,
        )
        pending = UnionPlayerRegistration.objects.create(
            workspace=self.workspace,
            player=player,
            club=self.source_club,
            effective_from=date(2026, 1, 1),
        )
        active = approve_player_registration(
            registration_id=pending.id,
            reviewer=self.reviewer,
            workspace=self.workspace,
            reason="Identity and eligibility verified.",
        )
        transfer = UnionPlayerTransfer.objects.create(
            workspace=self.workspace,
            player=player,
            source_registration=active,
            destination_club=self.destination_club,
            effective_on=date(2026, 7, 1),
            initiated_by=self.reviewer,
            status=UnionPlayerTransfer.Status.UNDER_UNION_REVIEW,
        )
        _, successor = approve_player_transfer(
            transfer_id=transfer.id,
            reviewer=self.reviewer,
            workspace=self.workspace,
            reason="All transfer conditions are met.",
        )
        active.refresh_from_db()
        self.assertEqual(active.status, UnionPlayerRegistration.Status.TRANSFERRED)
        self.assertEqual(successor.status, UnionPlayerRegistration.Status.ACTIVE)
        self.assertEqual(successor.club, self.destination_club)
        self.assertEqual(
            UnionPlayerRegistration.objects.filter(player=player).count(), 2
        )

    def test_transfer_fails_closed_when_source_is_not_active(self):
        player = UnionPlayer.objects.create(
            union=self.union,
            union_player_number="PU-P000001",
            first_name="Closed",
            last_name="Source",
            date_of_birth=date(2000, 1, 1),
            nationality="Ugandan",
            status=UnionPlayer.Status.APPROVED,
        )
        source = UnionPlayerRegistration.objects.create(
            workspace=self.workspace,
            player=player,
            club=self.source_club,
            effective_from=date(2026, 1, 1),
            status=UnionPlayerRegistration.Status.SUSPENDED,
        )
        transfer = UnionPlayerTransfer.objects.create(
            workspace=self.workspace,
            player=player,
            source_registration=source,
            destination_club=self.destination_club,
            effective_on=date(2026, 7, 1),
            initiated_by=self.reviewer,
            status=UnionPlayerTransfer.Status.UNDER_UNION_REVIEW,
        )
        with self.assertRaises(ValidationError):
            approve_player_transfer(
                transfer_id=transfer.id,
                reviewer=self.reviewer,
                workspace=self.workspace,
                reason="Attempting an invalid transfer.",
            )
