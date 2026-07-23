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
    LeagueAdminScope,
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
        self.assertEqual(response.data["results"][0]["default_format"], {})

    def test_editions_endpoint_preserves_legacy_and_empty_structure_verbatim(self):
        self.client.force_authenticate(self.owner)

        stored_structures = (
            {"round_robin": True},
            {},
        )

        for stored_structure in stored_structures:
            with self.subTest(stored_structure=stored_structure):
                self.old_edition.structure = stored_structure
                self.old_edition.save(update_fields=["structure"])

                response = self.client.get(
                    (
                        "/api/dashboards/union-admin/"
                        f"competition-identities/{self.identity.id}/editions/"
                    ),
                    {"workspace": self.workspace.slug},
                )

                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data["count"], 1)
                self.assertEqual(
                    response.data["results"][0]["id"],
                    self.old_edition.id,
                )
                self.assertEqual(
                    response.data["results"][0]["structure"],
                    stored_structure,
                )

    def _creation_payload(self, **overrides):
        payload = {
            "workspace": self.workspace.slug,
            "identity": {
                "name": "Championship",
                "primary_league": self.league.id,
                "sport": "Football",
                "competition_type": "LEAGUE",
                "description": "National second tier",
                "default_format": {
                    "format": "DOUBLE_ROUND_ROBIN",
                    "number_of_legs": 2,
                    "home_and_away": True,
                    "match_duration_minutes": 90,
                    "minimum_clubs": 8,
                    "maximum_clubs": 16,
                    "promotion_enabled": True,
                    "number_promoted": 2,
                    "relegation_enabled": True,
                    "number_relegated": 2,
                    "tie_break_order": ["POINTS", "SCORE_DIFFERENCE"],
                },
            },
            "first_edition": {"season": self.new_season.id, "currency": "UGX"},
            "administrators": [{"user": self.owner.id, "role": "COMPETITION_ADMIN"}],
        }
        payload.update(overrides)
        return payload

    def test_atomic_creation_creates_identity_edition_and_real_scope(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            "/api/dashboards/union-admin/competition-create/",
            self._creation_payload(),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        created = CompetitionIdentity.objects.get(name="Championship")
        edition = CompetitionEdition.objects.get(identity=created)
        scope = LeagueAdminScope.objects.get(competition=edition.competition)
        self.assertEqual(scope.user, self.owner)
        self.assertEqual(scope.role, LeagueAdminScope.Role.COMPETITION_ADMIN)
        self.assertEqual(edition.structure["version"], 1)
        self.assertEqual(
            response.data["identity"]["default_format"], created.default_format
        )
        self.assertEqual(
            response.data["identity"]["default_format"]["format"],
            "DOUBLE_ROUND_ROBIN",
        )
        self.assertCountEqual(
            response.data["edition"]["allowed_transitions"],
            ["CANCELLED", "REGISTRATION_OPEN"],
        )

    def test_invalid_administrator_rolls_back_all_creation(self):
        outsider = User.objects.create_user(
            email="outside@leagueos.test", password="StrongPass123!"
        )
        self.client.force_authenticate(self.owner)
        payload = self._creation_payload(
            administrators=[{"user": outsider.id, "role": "REGISTRAR"}]
        )
        response = self.client.post(
            "/api/dashboards/union-admin/competition-create/", payload, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            CompetitionIdentity.objects.filter(name="Championship").exists()
        )

    def test_cross_workspace_administrator_is_rejected(self):
        other_union = Union.objects.create(name="Other Union", slug="other-union")
        other_workspace = UnionWorkspace.objects.create(
            related_union=other_union,
            name="Other Workspace",
            slug="other-workspace",
            acronym="OW",
            sport="Football",
        )
        outsider = User.objects.create_user(
            email="other-workspace@leagueos.test", password="StrongPass123!"
        )
        UnionWorkspaceMembership.objects.create(
            user=outsider,
            workspace=other_workspace,
            role=UnionWorkspaceMembership.Role.OWNER,
        )
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            "/api/dashboards/union-admin/competition-create/",
            self._creation_payload(
                administrators=[
                    {"user": outsider.id, "role": LeagueAdminScope.Role.REGISTRAR}
                ]
            ),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("administrators", response.data)
        self.assertFalse(
            CompetitionIdentity.objects.filter(name="Championship").exists()
        )
        self.assertFalse(LeagueAdminScope.objects.filter(user=outsider).exists())

    def test_inactive_user_cannot_be_assigned(self):
        inactive = User.objects.create_user(
            email="inactive@leagueos.test",
            password="StrongPass123!",
            is_active=False,
        )
        UnionWorkspaceMembership.objects.create(
            user=inactive,
            workspace=self.workspace,
            role=UnionWorkspaceMembership.Role.UNION_ADMIN,
        )
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            "/api/dashboards/union-admin/competition-create/",
            self._creation_payload(
                administrators=[
                    {
                        "user": inactive.id,
                        "role": LeagueAdminScope.Role.FIXTURES_MANAGER,
                    }
                ]
            ),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("administrators", response.data)
        self.assertFalse(
            CompetitionIdentity.objects.filter(name="Championship").exists()
        )
        self.assertFalse(LeagueAdminScope.objects.filter(user=inactive).exists())

    def test_administrator_role_is_limited_to_model_choices(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            "/api/dashboards/union-admin/competition-create/",
            self._creation_payload(
                administrators=[{"user": self.owner.id, "role": "SUPER_ADMIN"}]
            ),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("administrators", response.data)
        self.assertFalse(
            CompetitionIdentity.objects.filter(name="Championship").exists()
        )

    def test_role_choices_preserve_existing_values_and_add_maintained_roles(self):
        self.assertEqual(
            {value for value, _label in LeagueAdminScope.Role.choices},
            {
                "LEAGUE_ADMIN",
                "COMPETITION_ADMIN",
                "FIXTURES_MANAGER",
                "REGISTRAR",
                "OFFICIALS_COORDINATOR",
                "VIEWER",
            },
        )

    def test_format_rejects_unknown_fields_and_inconsistent_promotion(self):
        self.client.force_authenticate(self.owner)
        payload = self._creation_payload()
        payload["identity"]["default_format"]["unvalidated_rule"] = True
        payload["identity"]["default_format"]["promotion_enabled"] = False
        response = self.client.post(
            "/api/dashboards/union-admin/competition-create/", payload, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("identity", response.data)
        self.assertFalse(
            CompetitionIdentity.objects.filter(name="Championship").exists()
        )
