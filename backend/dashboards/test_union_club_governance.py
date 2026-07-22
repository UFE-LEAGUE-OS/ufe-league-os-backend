from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Club, ClubAdminScope

from .models import (
    ClubAffiliation,
    League,
    LeagueClubMembership,
    Season,
    Union,
    UnionWorkspace,
    UnionWorkspaceMembership,
)


class UnionClubGovernanceApiTests(TestCase):
    password = "StrongPass123!"

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            email="owner@clubs.test", password=self.password
        )
        self.union = Union.objects.create(name="Club Union", slug="club-union")
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Club Workspace",
            slug="club-workspace",
            acronym="CW",
            sport="FOOTBALL",
        )
        UnionWorkspaceMembership.objects.create(
            user=self.owner,
            workspace=self.workspace,
            role=UnionWorkspaceMembership.Role.OWNER,
        )
        self.league = League.objects.create(
            union=self.union, name="Premier", slug="premier"
        )
        self.season = Season.objects.create(
            league=self.league, name="2027", slug="2027"
        )
        self.other_union = Union.objects.create(
            name="Other Club Union", slug="other-club-union"
        )
        self.other_workspace = UnionWorkspace.objects.create(
            related_union=self.other_union,
            name="Other Club Workspace",
            slug="other-club-workspace",
            acronym="OCW",
            sport="FOOTBALL",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def payload(self, **overrides):
        data = {
            "workspace": self.workspace.slug,
            "name": "Governance FC",
            "short_name": "GFC",
            "sport": "FOOTBALL",
            "description": "A governed club",
            "contact_email": "club@example.test",
            "phone_number": "+256700000001",
            "website": "https://club.example.test",
            "address": "Kampala",
            "founded_year": 2001,
            "primary_color": "#112233",
            "secondary_color": "#ffffff",
            "is_active": True,
            "affiliation": {
                "status": "PROVISIONAL",
                "compliance_status": "PENDING",
                "compliance_notes": "Documents due",
            },
            "administrator": {
                "account": {
                    "email": "admin@example.test",
                    "first_name": "Club",
                    "last_name": "Admin",
                },
                "role": "CLUB_ADMIN",
            },
        }
        data.update(overrides)
        return data

    def test_atomic_creation_creates_affiliation_scope_and_directory_record(self):
        response = self.client.post(
            "/api/dashboards/union-admin/clubs/", self.payload(), format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        club = Club.objects.get(name="Governance FC")
        self.assertTrue(
            ClubAffiliation.objects.filter(workspace=self.workspace, club=club).exists()
        )
        scope = ClubAdminScope.objects.get(club=club)
        self.assertEqual(scope.user.role, get_user_model().Role.FAN)
        self.assertFalse(
            UnionWorkspaceMembership.objects.filter(user=scope.user).exists()
        )
        self.assertIn("temporary_password", response.data)
        listed = self.client.get(
            "/api/dashboards/union-admin/clubs/", {"workspace": self.workspace.slug}
        )
        self.assertEqual(listed.data["count"], 1)
        self.assertEqual(listed.data["results"][0]["affiliation_status"], "PROVISIONAL")

    def test_optional_league_membership_is_explicit(self):
        response = self.client.post(
            "/api/dashboards/union-admin/clubs/",
            self.payload(
                league_membership={
                    "league": self.league.id,
                    "season": self.season.id,
                    "status": "INVITED",
                    "notes": "Invited",
                }
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(LeagueClubMembership.objects.count(), 1)
        self.assertEqual(response.data["league_membership"]["status"], "INVITED")

    def test_new_club_without_membership_remains_visible(self):
        created = self.client.post(
            "/api/dashboards/union-admin/clubs/", self.payload(), format="json"
        )
        self.assertEqual(created.status_code, 201)
        self.assertFalse(LeagueClubMembership.objects.exists())
        listed = self.client.get(
            "/api/dashboards/union-admin/clubs/", {"workspace": self.workspace.slug}
        )
        self.assertEqual(
            [row["name"] for row in listed.data["results"]], ["Governance FC"]
        )

    def test_cross_workspace_clubs_do_not_leak(self):
        other = Club.objects.create(name="Other FC", slug="other-fc", sport="FOOTBALL")
        ClubAffiliation.objects.create(workspace=self.other_workspace, club=other)
        listed = self.client.get(
            "/api/dashboards/union-admin/clubs/", {"workspace": self.workspace.slug}
        )
        self.assertEqual(listed.data["results"], [])

    def test_sport_mismatch_and_cross_workspace_league_are_rejected(self):
        mismatch = self.client.post(
            "/api/dashboards/union-admin/clubs/",
            self.payload(sport="RUGBY"),
            format="json",
        )
        other_league = League.objects.create(
            union=self.other_union, name="Other League", slug="other-league"
        )
        cross = self.client.post(
            "/api/dashboards/union-admin/clubs/",
            self.payload(
                league_membership={"league": other_league.id, "status": "INVITED"}
            ),
            format="json",
        )
        self.assertEqual(mismatch.status_code, 400)
        self.assertEqual(cross.status_code, 400)
        self.assertFalse(Club.objects.filter(name="Governance FC").exists())

    def test_existing_user_is_attached_without_password(self):
        user = get_user_model().objects.create_user(
            email="admin@example.test", password=self.password
        )
        response = self.client.post(
            "/api/dashboards/union-admin/clubs/", self.payload(), format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn("temporary_password", response.data)
        self.assertEqual(ClubAdminScope.objects.get().user, user)

    def test_profile_and_affiliation_can_be_edited_without_changing_admin(self):
        created = self.client.post(
            "/api/dashboards/union-admin/clubs/", self.payload(), format="json"
        )
        club_id = created.data["club"]["id"]
        scope_id = created.data["administrator_scope"]["id"]
        edited = self.client.patch(
            f"/api/dashboards/union-admin/clubs/{club_id}/",
            {
                "workspace": self.workspace.slug,
                "description": "Updated",
                "affiliation_status": "ACTIVE",
                "compliance_notes": "Approved",
            },
            format="json",
        )
        self.assertEqual(edited.status_code, 200, edited.data)
        self.assertEqual(edited.data["description"], "Updated")
        self.assertEqual(edited.data["affiliation_status"], "ACTIVE")
        self.assertEqual(ClubAdminScope.objects.get().id, scope_id)

    def test_invalid_account_rolls_back_everything(self):
        get_user_model().objects.create_user(
            email="phone-owner@example.test",
            password=self.password,
            phone_number="+256711111111",
        )
        payload = self.payload(
            administrator={
                "account": {
                    "email": "new@example.test",
                    "phone_number": "+256711111111",
                },
                "role": "CHAIRMAN",
            }
        )
        response = self.client.post(
            "/api/dashboards/union-admin/clubs/", payload, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Club.objects.filter(name="Governance FC").exists())
        self.assertFalse(
            ClubAffiliation.objects.filter(workspace=self.workspace).exists()
        )
        self.assertFalse(ClubAdminScope.objects.exists())

    def test_inactive_scope_does_not_remain_primary_after_explicit_change(self):
        created = self.client.post(
            "/api/dashboards/union-admin/clubs/", self.payload(), format="json"
        )
        club_id = created.data["club"]["id"]
        scope_id = created.data["administrator_scope"]["id"]
        response = self.client.patch(
            f"/api/dashboards/union-admin/clubs/{club_id}/administrators/{scope_id}/",
            {"workspace": self.workspace.slug, "is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(ClubAdminScope.objects.get().is_active)
