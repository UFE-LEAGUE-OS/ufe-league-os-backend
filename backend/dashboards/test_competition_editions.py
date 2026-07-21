from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase

from accounts.models import Club, User
from dashboards.models import (
    Competition,
    CompetitionEdition,
    CompetitionIdentity,
    League,
    LeagueClubMembership,
    Season,
    Union,
    UnionAuditEvent,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
from dashboards.union_competitions import (
    create_competition_edition,
    transition_competition_edition,
)


class CompetitionEditionTests(APITestCase):
    def setUp(self):
        self.union = Union.objects.create(
            name="Competition Union", slug="competition-union"
        )
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Competition Workspace",
            slug="competition-workspace",
            acronym="CW",
            sport="Football",
        )
        self.league = League.objects.create(
            union=self.union,
            name="Premier League",
            slug="premier-league",
        )
        self.old_season = Season.objects.create(
            league=self.league,
            name="2025/26",
            slug="2025-26",
        )
        self.new_season = Season.objects.create(
            league=self.league,
            name="2026/27",
            slug="2026-27",
        )
        self.owner = User.objects.create_user(
            email="competition-owner@leagueos.test",
            password="StrongPass123!",
            first_name="Competition",
            last_name="Owner",
            is_email_verified=True,
        )
        UnionWorkspaceMembership.objects.create(
            user=self.owner,
            workspace=self.workspace,
            role=UnionWorkspaceMembership.Role.OWNER,
        )
        self.identity = CompetitionIdentity.objects.create(
            union=self.union,
            primary_league=self.league,
            name="Premier League",
            slug="premier-league",
            sport="Football",
        )
        self.old_competition = Competition.objects.create(
            league=self.league,
            name="Premier League 2025/26",
            slug="premier-league-2025-26",
            season="2025/26",
            season_record=self.old_season,
        )
        self.old_edition = CompetitionEdition.objects.create(
            identity=self.identity,
            competition=self.old_competition,
            season=self.old_season,
            rules={"points_for_win": 3},
            structure={"round_robin": True},
            eligibility_rules={"minimum_squad": 18},
        )
        self.club = Club.objects.create(
            name="Edition Club",
            slug="edition-club",
            sport=Club.Sport.FOOTBALL,
        )
        LeagueClubMembership.objects.create(
            league=self.league,
            club=self.club,
            season=self.old_season,
            status=LeagueClubMembership.Status.ACTIVE,
        )

    def test_new_edition_copies_selected_configuration_without_mutating_source(self):
        new_edition = create_competition_edition(
            workspace=self.workspace,
            identity=self.identity,
            season=self.new_season,
            actor=self.owner,
            copied_from=self.old_edition,
            copy_fields=["rules", "clubs"],
        )

        self.assertEqual(new_edition.competition.season_record, self.new_season)
        self.assertEqual(new_edition.rules, {"points_for_win": 3})
        self.assertEqual(new_edition.structure, {})
        self.assertEqual(new_edition.eligibility_rules, {})
        copied_membership = LeagueClubMembership.objects.get(
            league=self.league,
            club=self.club,
            season=self.new_season,
        )
        self.assertEqual(copied_membership.status, LeagueClubMembership.Status.INVITED)
        self.old_edition.refresh_from_db()
        self.assertEqual(self.old_edition.rules, {"points_for_win": 3})
        self.assertTrue(
            UnionAuditEvent.objects.filter(
                workspace=self.workspace,
                action="competition_edition.created",
                target_id=new_edition.id,
            ).exists()
        )

    def test_lifecycle_rejects_illegal_transition_and_requires_a_reason(self):
        with self.assertRaises(ValidationError):
            transition_competition_edition(
                edition=self.old_edition,
                target_status=CompetitionEdition.Status.ACTIVE,
                actor=self.owner,
                workspace=self.workspace,
                reason="Skipping workflow",
            )
        with self.assertRaises(ValidationError):
            transition_competition_edition(
                edition=self.old_edition,
                target_status=CompetitionEdition.Status.REGISTRATION_OPEN,
                actor=self.owner,
                workspace=self.workspace,
                reason="",
            )

    def test_identity_endpoint_is_workspace_scoped(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(
            "/api/dashboards/union-admin/competition-identities/",
            {"workspace": self.workspace.slug},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.identity.id)
