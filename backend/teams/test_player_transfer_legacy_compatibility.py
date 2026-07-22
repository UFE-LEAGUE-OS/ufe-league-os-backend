from datetime import date
from pathlib import Path

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Club, ClubAdminScope, User
from dashboards.models import (
    ClubAffiliation,
    League,
    Season,
    Union,
    UnionPlayer,
    UnionPlayerRegistration,
    UnionPlayerTransfer,
    UnionWorkspace,
)

from .models import PlayerRegistration, PlayerTransfer, Team


class PlayerTransferLegacyCompatibilityTests(APITestCase):
    list_url = "/api/teams/transfers/"

    def setUp(self):
        self.union = Union.objects.create(
            name="Legacy Transfer Union", slug="legacy-tu"
        )
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Legacy Transfer Workspace",
            slug="legacy-transfer-workspace",
            acronym="LTW",
            sport="Football",
        )
        self.league = League.objects.create(
            union=self.union,
            name="Legacy Transfer League",
            slug="legacy-transfer-league",
        )
        self.season = Season.objects.create(
            league=self.league,
            name="2026",
            slug="legacy-transfer-2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.source_actor = self._user("legacy-source")
        self.destination_actor = self._user("legacy-destination")
        self.other_actor = self._user("legacy-other")
        self.source_club = self._club("Legacy Source", self.source_actor)
        self.destination_club = self._club(
            "Legacy Destination",
            self.destination_actor,
        )
        self.other_club = self._club("Legacy Other", self.other_actor)
        self.source_team = Team.objects.create(
            club=self.source_club,
            name="Legacy Source Team",
        )
        self.destination_team = Team.objects.create(
            club=self.destination_club,
            name="Legacy Destination Team",
        )
        self.other_team = Team.objects.create(
            club=self.other_club,
            name="Legacy Other Team",
        )
        for club in (self.source_club, self.destination_club):
            ClubAffiliation.objects.create(
                workspace=self.workspace,
                club=club,
                status=ClubAffiliation.Status.ACTIVE,
            )
        self.legacy_player = PlayerRegistration.objects.create(
            club=self.source_club,
            team=self.source_team,
            registration_number="LEGACY-PLAYER-1",
            first_name="Legacy",
            last_name="Player",
            date_of_birth=date(2000, 1, 1),
            nationality="Ugandan",
            position="MID",
            registered_date=date(2026, 1, 1),
            submission_status=PlayerRegistration.SubmissionStatus.LEGACY,
        )
        self.legacy_transfer = PlayerTransfer.objects.create(
            transfer_number="LEGACY-TRF-1",
            player=self.legacy_player,
            from_club=self.source_club,
            to_club=self.destination_club,
            transfer_type=PlayerTransfer.TransferType.PERMANENT,
            transfer_date=date(2026, 7, 1),
            requested_by=self.destination_actor,
        )
        other_player = PlayerRegistration.objects.create(
            club=self.other_club,
            team=self.other_team,
            registration_number="LEGACY-OTHER-PLAYER",
            first_name="Other",
            last_name="Player",
            date_of_birth=date(2001, 1, 1),
            nationality="Ugandan",
            position="FW",
            registered_date=date(2026, 1, 1),
            submission_status=PlayerRegistration.SubmissionStatus.LEGACY,
        )
        self.other_transfer = PlayerTransfer.objects.create(
            transfer_number="LEGACY-TRF-OTHER",
            player=other_player,
            from_club=self.other_club,
            to_club=self.other_club,
            transfer_type=PlayerTransfer.TransferType.LOAN,
            transfer_date=date(2026, 7, 1),
            requested_by=self.other_actor,
        )
        self.player_user = User.objects.create_user(
            email="maintained-player@legacy-transfer.test",
            password="StrongPass123!",
            role=User.Role.FAN,
        )
        self.union_player = UnionPlayer.objects.create(
            union=self.union,
            user=self.player_user,
            union_player_number="LT-P000001",
            first_name="Maintained",
            last_name="Player",
            date_of_birth=date(2002, 1, 1),
            nationality="Ugandan",
            status=UnionPlayer.Status.APPROVED,
        )
        self.registration = UnionPlayerRegistration.objects.create(
            workspace=self.workspace,
            player=self.union_player,
            club=self.source_club,
            team=self.source_team,
            season=self.season,
            status=UnionPlayerRegistration.Status.ACTIVE,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
        )
        self.client.force_authenticate(self.destination_actor)

    def _user(self, prefix):
        return User.objects.create_user(
            email=f"{prefix}@legacy-transfer.test",
            password="StrongPass123!",
            role=User.Role.CLUB_ADMIN,
        )

    def _club(self, prefix, actor):
        club = Club.objects.create(
            name=f"{prefix} Club",
            slug=f"{prefix.lower().replace(' ', '-')}-club",
            admin=actor,
        )
        ClubAdminScope.objects.create(
            user=actor,
            club=club,
            role=ClubAdminScope.Role.CHAIRMAN,
        )
        return club

    def _maintained_payload(self):
        return {
            "workspace": self.workspace.id,
            "source_registration": self.registration.id,
            "destination_club": self.destination_club.id,
            "destination_team": self.destination_team.id,
            "effective_on": "2026-08-01",
            "transfer_type": "PERMANENT",
            "documents": ["maintained-reference"],
            "fee_status": "PAID",
        }

    def test_legacy_get_list_remains_readable_for_related_club(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data],
            [self.legacy_transfer.id],
        )

    def test_legacy_get_list_excludes_other_club_records(self):
        response = self.client.get(self.list_url)
        ids = {item["id"] for item in response.data}
        self.assertNotIn(self.other_transfer.id, ids)

    def test_legacy_detail_is_readable_by_related_club(self):
        response = self.client.get(f"/api/teams/transfers/{self.legacy_transfer.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["transfer_number"], "LEGACY-TRF-1")

    def test_cross_club_legacy_detail_returns_404(self):
        response = self.client.get(f"/api/teams/transfers/{self.other_transfer.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_legacy_post_creates_maintained_transfer(self):
        response = self.client.post(
            self.list_url,
            self._maintained_payload(),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(UnionPlayerTransfer.objects.count(), 1)
        self.assertEqual(
            UnionPlayerTransfer.objects.get().status,
            UnionPlayerTransfer.Status.DRAFT,
        )

    def test_legacy_post_creates_no_legacy_row(self):
        before = PlayerTransfer.objects.count()
        response = self.client.post(
            self.list_url,
            self._maintained_payload(),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PlayerTransfer.objects.count(), before)

    def test_legacy_post_returns_deprecation_marker(self):
        response = self.client.post(
            self.list_url,
            self._maintained_payload(),
            format="json",
        )
        self.assertEqual(response.data["workflow"], "UNION_PLAYER_TRANSFER")
        self.assertTrue(response.data["deprecated_direct_creation"])
        self.assertEqual(response.data["submission"]["status"], "DRAFT")

    def test_old_broad_direct_write_payload_is_rejected(self):
        response = self.client.post(
            self.list_url,
            {
                "player": self.legacy_player.id,
                "from_club": self.source_club.id,
                "to_club": self.destination_club.id,
                "transfer_fee": "100.00",
                "currency": "USD",
                "transfer_date": "2026-08-01",
                "status": "APPROVED",
                "approved_by": self.destination_actor.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for field in (
            "player",
            "from_club",
            "to_club",
            "status",
            "approved_by",
        ):
            self.assertIn(field, response.data)
        self.assertFalse(UnionPlayerTransfer.objects.exists())

    def test_legacy_patch_returns_405(self):
        response = self.client.patch(
            f"/api/teams/transfers/{self.legacy_transfer.id}/",
            {"status": "APPROVED"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_legacy_put_returns_405(self):
        response = self.client.put(
            f"/api/teams/transfers/{self.legacy_transfer.id}/",
            {"status": "APPROVED"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_legacy_delete_returns_405(self):
        response = self.client.delete(
            f"/api/teams/transfers/{self.legacy_transfer.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(
            PlayerTransfer.objects.filter(pk=self.legacy_transfer.id).exists()
        )

    def test_legacy_status_and_approval_fields_cannot_change(self):
        original = (
            self.legacy_transfer.status,
            self.legacy_transfer.approved_by_id,
            self.legacy_transfer.approved_at,
        )
        for method in ("patch", "put"):
            with self.subTest(method=method):
                getattr(self.client, method)(
                    f"/api/teams/transfers/{self.legacy_transfer.id}/",
                    {
                        "status": "APPROVED",
                        "approved_by": self.destination_actor.id,
                        "approved_at": "2026-08-01T00:00:00Z",
                    },
                    format="json",
                )
        self.legacy_transfer.refresh_from_db()
        self.assertEqual(
            (
                self.legacy_transfer.status,
                self.legacy_transfer.approved_by_id,
                self.legacy_transfer.approved_at,
            ),
            original,
        )

    def test_no_broad_writable_transfer_serializer_production_reference(self):
        broad_name = "Player" + "TransferSerializer"
        teams_path = Path(__file__).resolve().parent
        production_files = [
            teams_path / "serializers.py",
            teams_path / "views.py",
            teams_path / "transfer_serializers.py",
            teams_path / "transfer_views.py",
        ]
        for path in production_files:
            with self.subTest(path=path.name):
                self.assertNotIn(broad_name, path.read_text(encoding="utf-8"))
