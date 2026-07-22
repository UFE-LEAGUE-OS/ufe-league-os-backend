from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import (
    Competition,
    League,
    LeagueAdminScope,
    Union,
    UnionWorkspace,
    UnionWorkspaceMembership,
)


class UnionLeagueGovernanceApiTests(TestCase):
    password = "StrongPass123!"

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            email="owner@leagueos.test", password=self.password
        )
        self.union = Union.objects.create(name="Test Union", slug="test-union")
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Test Workspace",
            slug="test-workspace",
            acronym="TW",
            sport="FOOTBALL",
        )
        UnionWorkspaceMembership.objects.create(
            user=self.owner,
            workspace=self.workspace,
            role=UnionWorkspaceMembership.Role.OWNER,
        )
        self.other_union = Union.objects.create(name="Other Union", slug="other-union")
        self.other_workspace = UnionWorkspace.objects.create(
            related_union=self.other_union,
            name="Other Workspace",
            slug="other-workspace",
            acronym="OW",
            sport="RUGBY",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def post(self, path, data):
        return self.client.post(
            path, {"workspace": self.workspace.slug, **data}, format="json"
        )

    def test_governance_options_are_workspace_controlled(self):
        response = self.client.get(
            "/api/dashboards/union-admin/governance-options/",
            {"workspace": self.workspace.slug},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["workspace"]["sport"], "FOOTBALL")
        self.assertFalse(response.data["workspace"]["is_multi_sport"])
        self.assertEqual(
            response.data["supported_sports"],
            [{"value": "FOOTBALL", "label": "Football"}],
        )
        self.assertTrue(response.data["format_templates"]["FOOTBALL"])

    def test_league_create_list_and_edit_are_workspace_scoped(self):
        League.objects.create(
            union=self.other_union, name="Hidden League", slug="hidden"
        )
        created = self.post(
            "/api/dashboards/union-admin/leagues/",
            {
                "name": "Premier League",
                "description": "Top flight",
                "sport": "FOOTBALL",
            },
        )
        self.assertEqual(created.status_code, 201, created.data)
        league_id = created.data["id"]
        listed = self.client.get(
            "/api/dashboards/union-admin/leagues/", {"workspace": self.workspace.slug}
        )
        self.assertEqual(listed.data["count"], 1)
        edited = self.client.patch(
            f"/api/dashboards/union-admin/leagues/{league_id}/",
            {"workspace": self.workspace.slug, "description": "Updated"},
            format="json",
        )
        self.assertEqual(edited.status_code, 200, edited.data)
        self.assertEqual(edited.data["description"], "Updated")

    def test_duplicate_league_and_sport_mismatch_are_rejected(self):
        League.objects.create(union=self.union, name="Premier League", slug="premier")
        duplicate = self.post(
            "/api/dashboards/union-admin/leagues/", {"name": "premier league"}
        )
        mismatch = self.post(
            "/api/dashboards/union-admin/leagues/", {"name": "Cup", "sport": "RUGBY"}
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("name", duplicate.data)
        self.assertEqual(mismatch.status_code, 400)
        self.assertIn("sport", mismatch.data)

    def test_cross_workspace_edit_is_not_found(self):
        other = League.objects.create(
            union=self.other_union, name="Other", slug="other"
        )
        response = self.client.patch(
            f"/api/dashboards/union-admin/leagues/{other.id}/",
            {"workspace": self.workspace.slug, "name": "Intrusion"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_is_blocked_by_history_and_empty_league_can_be_deleted(self):
        blocked = League.objects.create(
            union=self.union, name="Blocked", slug="blocked"
        )
        Competition.objects.create(
            league=blocked, name="Season", slug="season", season="2026"
        )
        blocked_response = self.client.delete(
            f"/api/dashboards/union-admin/leagues/{blocked.id}/",
            {"workspace": self.workspace.slug},
            format="json",
        )
        self.assertEqual(blocked_response.status_code, 409)
        empty = League.objects.create(union=self.union, name="Empty", slug="empty")
        deleted = self.client.delete(
            f"/api/dashboards/union-admin/leagues/{empty.id}/",
            {"workspace": self.workspace.slug},
            format="json",
        )
        self.assertEqual(deleted.status_code, 204)

    def test_existing_user_is_attached_without_union_membership_or_role_overwrite(self):
        User = get_user_model()
        user = User.objects.create_user(
            email="admin@leagueos.test", password=self.password
        )
        league = League.objects.create(union=self.union, name="Premier", slug="premier")
        response = self.post(
            f"/api/dashboards/union-admin/leagues/{league.id}/administrators/",
            {
                "account": {"email": user.email},
                "role": LeagueAdminScope.Role.LEAGUE_ADMIN,
            },
        )
        self.assertEqual(response.status_code, 201, response.data)
        user.refresh_from_db()
        self.assertEqual(user.role, User.Role.FAN)
        self.assertFalse(UnionWorkspaceMembership.objects.filter(user=user).exists())
        self.assertNotIn("temporary_password", response.data)

    def test_new_user_gets_one_time_password_and_scope_is_idempotent(self):
        league = League.objects.create(union=self.union, name="Premier", slug="premier")
        payload = {
            "account": {
                "email": "new-admin@leagueos.test",
                "first_name": "New",
                "last_name": "Admin",
            },
            "role": LeagueAdminScope.Role.REGISTRAR,
        }
        first = self.post(
            f"/api/dashboards/union-admin/leagues/{league.id}/administrators/", payload
        )
        second = self.post(
            f"/api/dashboards/union-admin/leagues/{league.id}/administrators/", payload
        )
        self.assertEqual(first.status_code, 201, first.data)
        self.assertTrue(first.data["created_user"])
        self.assertIn("temporary_password", first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertFalse(second.data["created_user"])
        self.assertNotIn("temporary_password", second.data)
        self.assertEqual(LeagueAdminScope.objects.filter(league=league).count(), 1)

    def test_competition_scope_must_belong_to_league(self):
        league = League.objects.create(union=self.union, name="Premier", slug="premier")
        other = League.objects.create(
            union=self.union, name="Championship", slug="championship"
        )
        competition = Competition.objects.create(
            league=other, name="Cup", slug="cup", season="2026"
        )
        response = self.post(
            f"/api/dashboards/union-admin/leagues/{league.id}/administrators/",
            {
                "account": {"email": "admin@leagueos.test"},
                "competition": competition.id,
                "role": LeagueAdminScope.Role.COMPETITION_ADMIN,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            get_user_model().objects.filter(email="admin@leagueos.test").exists()
        )

    def test_inactive_user_is_rejected_atomically(self):
        User = get_user_model()
        User.objects.create_user(
            email="inactive@leagueos.test", password=self.password, is_active=False
        )
        league = League.objects.create(union=self.union, name="Premier", slug="premier")
        response = self.post(
            f"/api/dashboards/union-admin/leagues/{league.id}/administrators/",
            {
                "account": {"email": "inactive@leagueos.test"},
                "role": LeagueAdminScope.Role.LEAGUE_ADMIN,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(LeagueAdminScope.objects.filter(league=league).exists())

    def test_user_without_manage_permission_is_denied(self):
        User = get_user_model()
        viewer = User.objects.create_user(
            email="viewer@leagueos.test", password=self.password
        )
        UnionWorkspaceMembership.objects.create(
            user=viewer,
            workspace=self.workspace,
            role=UnionWorkspaceMembership.Role.VIEWER,
        )
        self.client.force_authenticate(viewer)
        response = self.post("/api/dashboards/union-admin/leagues/", {"name": "Denied"})
        self.assertEqual(response.status_code, 403)
