from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Club, User
from dashboards.models import (
    Competition,
    FixtureOfficialAssignment,
    League,
    LeagueClubMembership,
    Match,
    NationalTeam,
    NationalTeamMember,
    Union,
    UnionMatchOfficial,
    UnionRegistrationApplication,
    UnionWorkspace,
    UnionWorkspaceMembership,
)


class UnionOperationalContractTests(APITestCase):
    password = "StrongPass123!"

    def setUp(self):
        self.union = Union.objects.create(name="Test Union", slug="test-union")
        self.other_union = Union.objects.create(name="Other Union", slug="other-union")
        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Test Union Workspace",
            slug="test-union-workspace",
            acronym="TU",
            sport="Rugby",
        )
        self.other_workspace = UnionWorkspace.objects.create(
            related_union=self.other_union,
            name="Other Union Workspace",
            slug="other-union-workspace",
            acronym="OU",
            sport="Rugby",
        )
        self.league = League.objects.create(
            union=self.union, name="Test League", slug="test-league"
        )
        self.other_league = League.objects.create(
            union=self.other_union,
            name="Other League",
            slug="other-league",
        )
        self.competition = Competition.objects.create(
            league=self.league,
            name="Test Competition",
            slug="test-competition",
            season="2026",
        )
        self.other_competition = Competition.objects.create(
            league=self.other_league,
            name="Other Competition",
            slug="other-competition",
            season="2026",
        )
        self.club = Club.objects.create(
            name="Workspace Club",
            slug="workspace-club",
            sport=Club.Sport.RUGBY,
        )
        self.opponent = Club.objects.create(
            name="Workspace Opponent",
            slug="workspace-opponent",
            sport=Club.Sport.RUGBY,
        )
        self.other_club = Club.objects.create(
            name="Other Workspace Club",
            slug="other-workspace-club",
            sport=Club.Sport.RUGBY,
        )
        LeagueClubMembership.objects.create(league=self.league, club=self.club)
        LeagueClubMembership.objects.create(league=self.league, club=self.opponent)
        LeagueClubMembership.objects.create(
            league=self.other_league, club=self.other_club
        )

        self.owner = User.objects.create_user(
            email="owner@leagueos.test",
            password=self.password,
            first_name="Workspace",
            last_name="Owner",
            role=User.Role.UNION_ADMIN,
            is_email_verified=True,
        )
        self.registrar = User.objects.create_user(
            email="registrar@leagueos.test",
            password=self.password,
            first_name="Workspace",
            last_name="Registrar",
            role=User.Role.UNION_ADMIN,
            is_email_verified=True,
        )
        self.viewer = User.objects.create_user(
            email="viewer@leagueos.test",
            password=self.password,
            role=User.Role.UNION_ADMIN,
            is_email_verified=True,
        )
        UnionWorkspaceMembership.objects.create(
            user=self.owner,
            workspace=self.workspace,
            role=UnionWorkspaceMembership.Role.OWNER,
        )
        UnionWorkspaceMembership.objects.create(
            user=self.registrar,
            workspace=self.workspace,
            role=UnionWorkspaceMembership.Role.REGISTRAR,
        )
        UnionWorkspaceMembership.objects.create(
            user=self.viewer,
            workspace=self.workspace,
            role=UnionWorkspaceMembership.Role.VIEWER,
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def workspace_params(self):
        return {"workspace": self.workspace.slug}

    def test_owner_can_manage_workspace_scoped_national_teams_and_real_counts(self):
        self.authenticate(self.owner)

        create_response = self.client.post(
            "/api/dashboards/union-admin/national-teams/",
            {
                "workspace": self.workspace.slug,
                "name": "Test Rugby Cranes",
                "category": "Senior Men",
                "status": NationalTeam.Status.CAMP,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        team_id = create_response.data["id"]

        player_response = self.client.post(
            f"/api/dashboards/union-admin/national-teams/{team_id}/members/",
            {
                "workspace": self.workspace.slug,
                "full_name": "Test Player",
                "member_type": NationalTeamMember.MemberType.PLAYER,
                "club": self.club.id,
                "role": "Flanker",
            },
            format="json",
        )
        self.assertEqual(player_response.status_code, status.HTTP_201_CREATED)

        staff_response = self.client.post(
            f"/api/dashboards/union-admin/national-teams/{team_id}/members/",
            {
                "workspace": self.workspace.slug,
                "full_name": "Test Coach",
                "member_type": NationalTeamMember.MemberType.STAFF,
                "role": "Assistant Coach",
            },
            format="json",
        )
        self.assertEqual(staff_response.status_code, status.HTTP_201_CREATED)

        list_response = self.client.get(
            "/api/dashboards/union-admin/national-teams/",
            self.workspace_params(),
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(list_response.data["results"][0]["players"], 1)
        self.assertEqual(list_response.data["results"][0]["staff"], 1)

    def test_national_team_member_rejects_club_from_another_workspace(self):
        team = NationalTeam.objects.create(
            workspace=self.workspace,
            name="Scoped Team",
            slug="scoped-team",
            category="Senior",
            created_by=self.owner,
        )
        self.authenticate(self.owner)

        response = self.client.post(
            f"/api/dashboards/union-admin/national-teams/{team.id}/members/",
            {
                "workspace": self.workspace.slug,
                "full_name": "Wrong Club Player",
                "club": self.other_club.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(team.members.exists())

    def test_viewer_cannot_manage_national_teams(self):
        self.authenticate(self.viewer)

        response = self.client.get(
            "/api/dashboards/union-admin/national-teams/",
            self.workspace_params(),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_registrar_reviews_real_registration_application(self):
        self.authenticate(self.registrar)

        create_response = self.client.post(
            "/api/dashboards/union-admin/registration-applications/",
            {
                "workspace": self.workspace.slug,
                "application_type": (
                    UnionRegistrationApplication.ApplicationType.NEW_PLAYER
                ),
                "club": self.club.id,
                "applicant_name": "Registered Player",
                "registration_number": "TU-001",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        application_id = create_response.data["id"]

        blocked_approval = self.client.patch(
            f"/api/dashboards/union-admin/registration-applications/{application_id}/",
            {
                "workspace": self.workspace.slug,
                "status": UnionRegistrationApplication.Status.APPROVED,
            },
            format="json",
        )
        self.assertEqual(blocked_approval.status_code, status.HTTP_400_BAD_REQUEST)

        approval = self.client.patch(
            f"/api/dashboards/union-admin/registration-applications/{application_id}/",
            {
                "workspace": self.workspace.slug,
                "documents_complete": True,
                "status": UnionRegistrationApplication.Status.APPROVED,
                "reviewer_notes": "Eligibility confirmed.",
            },
            format="json",
        )
        self.assertEqual(approval.status_code, status.HTTP_200_OK)
        self.assertEqual(
            approval.data["status"], UnionRegistrationApplication.Status.APPROVED
        )
        self.assertEqual(approval.data["reviewed_by"], self.registrar.id)
        self.assertIsNotNone(approval.data["reviewed_at"])

    def test_registration_list_is_strictly_workspace_scoped(self):
        UnionRegistrationApplication.objects.create(
            workspace=self.workspace,
            club=self.club,
            applicant_name="Workspace Applicant",
            submitted_by=self.owner,
        )
        UnionRegistrationApplication.objects.create(
            workspace=self.other_workspace,
            club=self.other_club,
            applicant_name="Other Applicant",
            submitted_by=self.owner,
        )
        self.authenticate(self.registrar)

        response = self.client.get(
            "/api/dashboards/union-admin/registration-applications/",
            self.workspace_params(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["applicant_name"], "Workspace Applicant"
        )

    def test_overview_uses_maintained_counts_and_does_not_inherit_same_sport_clubs(
        self,
    ):
        NationalTeam.objects.create(
            workspace=self.workspace,
            name="Maintained Team",
            slug="maintained-team",
            category="Senior",
        )
        UnionRegistrationApplication.objects.create(
            workspace=self.workspace,
            club=self.club,
            applicant_name="Pending Applicant",
        )
        UnionMatchOfficial.objects.create(
            union=self.union,
            full_name="Workspace Official",
            email="official@leagueos.test",
        )
        self.authenticate(self.owner)

        response = self.client.get(
            "/api/dashboards/union-admin/workspace/", self.workspace_params()
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["summary"]["member_clubs"], 2)
        self.assertEqual(response.data["summary"]["national_teams"], 1)
        self.assertEqual(response.data["summary"]["pending_approvals"], 1)
        self.assertEqual(response.data["summary"]["referees"], 1)

    def test_official_readiness_reports_actual_workspace_assignments(self):
        match = Match.objects.create(
            competition=self.competition,
            home_club=self.club,
            away_club=self.opponent,
            match_date=timezone.now() + timedelta(days=2),
            venue="Test Stadium",
        )
        other_match = Match.objects.create(
            competition=self.other_competition,
            home_club=self.other_club,
            away_club=self.opponent,
            match_date=timezone.now() + timedelta(days=2),
            venue="Other Stadium",
        )
        official = UnionMatchOfficial.objects.create(
            union=self.union,
            full_name="Assigned Official",
            email="assigned@leagueos.test",
        )
        other_official = UnionMatchOfficial.objects.create(
            union=self.other_union,
            full_name="Other Official",
            email="other-official@leagueos.test",
        )
        FixtureOfficialAssignment.objects.create(
            match=match,
            official=official,
            status=FixtureOfficialAssignment.Status.ASSIGNED,
            assigned_by=self.owner,
        )
        FixtureOfficialAssignment.objects.create(
            match=other_match,
            official=other_official,
            status=FixtureOfficialAssignment.Status.ACCEPTED,
            assigned_by=self.owner,
        )
        self.authenticate(self.owner)

        response = self.client.get(
            "/api/dashboards/union-admin/official-readiness/",
            self.workspace_params(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["summary"]["officials_total"], 1)
        self.assertEqual(response.data["summary"]["upcoming_fixtures"], 1)
        self.assertEqual(response.data["summary"]["fixtures_with_pending_responses"], 1)
        self.assertEqual(len(response.data["fixtures"]), 1)
        self.assertEqual(response.data["fixtures"][0]["id"], match.id)
