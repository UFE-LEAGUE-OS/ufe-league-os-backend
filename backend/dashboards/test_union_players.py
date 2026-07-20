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

    def test_registration_approval_remains_available(self):
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
        self.assertEqual(active.status, UnionPlayerRegistration.Status.ACTIVE)
        self.assertEqual(player.club_registration_history.count(), 1)

    def test_legacy_transfer_approval_is_disabled(self):
        player = UnionPlayer.objects.create(
            union=self.union,
            union_player_number="PU-P000001",
            first_name="Maintained",
            last_name="Transfer",
            date_of_birth=date(2000, 1, 1),
            nationality="Ugandan",
            status=UnionPlayer.Status.APPROVED,
        )
        active = UnionPlayerRegistration.objects.create(
            workspace=self.workspace,
            player=player,
            club=self.source_club,
            effective_from=date(2026, 1, 1),
            status=UnionPlayerRegistration.Status.ACTIVE,
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
        with self.assertRaisesMessage(
            ValidationError,
            (
                "Legacy transfer approval is disabled. Use the maintained "
                "Union transfer decision service."
            ),
        ):
            approve_player_transfer(
                transfer_id=transfer.id,
                reviewer=self.reviewer,
                workspace=self.workspace,
                reason="Attempt to bypass maintained review.",
            )
        active.refresh_from_db()
        self.assertEqual(active.status, UnionPlayerRegistration.Status.ACTIVE)
        self.assertEqual(
            UnionPlayerRegistration.objects.filter(player=player).count(), 1
        )
        inactive_source = UnionPlayerRegistration.objects.create(
            workspace=self.workspace,
            player=player,
            club=self.source_club,
            effective_from=date(2026, 1, 1),
            status=UnionPlayerRegistration.Status.SUSPENDED,
        )
        inactive_transfer = UnionPlayerTransfer.objects.create(
            workspace=self.workspace,
            player=player,
            source_registration=inactive_source,
            destination_club=self.destination_club,
            effective_on=date(2026, 7, 1),
            initiated_by=self.reviewer,
            status=UnionPlayerTransfer.Status.UNDER_UNION_REVIEW,
        )
        with self.assertRaisesMessage(
            ValidationError,
            "Legacy transfer approval is disabled.",
        ):
            approve_player_transfer(
                transfer_id=inactive_transfer.id,
                reviewer=self.reviewer,
                workspace=self.workspace,
                reason="Attempting an invalid transfer.",
            )
