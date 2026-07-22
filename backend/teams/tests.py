from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Club, ClubAdminScope, User
from dashboards.models import (
    ClubAffiliation,
    Competition,
    League,
    LeagueClubMembership,
    Season,
    Union,
    UnionPlayer,
    UnionPlayerRegistration,
    UnionPlayerTransfer,
)
from teams.models import (
    PlayerRegistration,
    PlayerTransfer,
    Squad,
    SquadMember,
    SquadSubmission,
    StaffMember,
    Team,
)


class TeamsAPITestCase(APITestCase):
    def setUp(self):
        # Create users
        self.super_admin = User.objects.create_superuser(
            email="superadmin@example.com",
            password="testpass123",
            first_name="Super",
            last_name="Admin",
        )
        self.club_admin = User.objects.create_user(
            email="clubadmin@example.com",
            password="testpass123",
            first_name="Club",
            last_name="Admin",
            role=User.Role.CLUB_ADMIN,
        )
        self.union_admin = User.objects.create_user(
            email="unionadmin@example.com",
            password="testpass123",
            first_name="Union",
            last_name="Admin",
            role=User.Role.UNION_ADMIN,
        )

        # Create club and assign club admin
        self.club = Club.objects.create(
            name="Test FC",
            slug="test-fc",
            sport=Club.Sport.FOOTBALL,
            admin=self.club_admin,
        )

        # Create league/union structures
        self.union = Union.objects.create(
            name="Test Union",
            slug="test-union",
        )
        self.league = League.objects.create(
            union=self.union,
            name="Test League",
            slug="test-league",
        )
        self.season = Season.objects.create(
            league=self.league,
            name="2025/26",
            slug="2025-26",
            is_active=True,
        )
        self.competition = Competition.objects.create(
            league=self.league,
            name="Test Premier League",
            slug="test-premier-league",
            season="2025/26",
            season_record=self.season,
            is_active=True,
        )
        LeagueClubMembership.objects.create(
            league=self.league,
            club=self.club,
            season=self.season,
        )

        # Create union workspace
        from dashboards.models import UnionWorkspace, UnionWorkspaceMembership

        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Test Union Workspace",
            slug="test-union-workspace",
            acronym="TU",
            sport="Football",
            workspace_type=UnionWorkspace.WorkspaceType.FEDERATION,
        )
        UnionWorkspaceMembership.objects.create(
            user=self.union_admin,
            workspace=self.workspace,
            role=UnionWorkspaceMembership.Role.UNION_ADMIN,
        )

        self.client.force_authenticate(user=self.club_admin)


class TeamTests(TeamsAPITestCase):
    def test_create_team(self):
        url = reverse("team-list-create")
        data = {
            "club": self.club.id,
            "name": "First Team",
            "short_name": "FT",
            "team_type": Team.TeamType.FIRST_TEAM,
            "description": "Main team",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Team.objects.count(), 1)
        self.assertEqual(Team.objects.first().name, "First Team")

    def test_list_teams(self):
        Team.objects.create(
            club=self.club,
            name="First Team",
            team_type=Team.TeamType.FIRST_TEAM,
        )
        url = reverse("team-list-create")
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class SquadTests(TeamsAPITestCase):
    def setUp(self):
        super().setUp()
        self.team = Team.objects.create(
            club=self.club,
            name="First Team",
            team_type=Team.TeamType.FIRST_TEAM,
        )

    def test_create_squad(self):
        url = reverse("squad-list-create")
        data = {
            "team": self.team.id,
            "competition": self.competition.id,
            "name": "2025/26 Squad",
            "season": "2025/26",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Squad.objects.count(), 1)
        self.assertEqual(Squad.objects.first().name, "2025/26 Squad")


class PlayerRegistrationTests(TeamsAPITestCase):
    def setUp(self):
        super().setUp()
        self.team = Team.objects.create(
            club=self.club,
            name="First Team",
            team_type=Team.TeamType.FIRST_TEAM,
        )

    def test_create_player_registration(self):
        url = reverse("player-registration-list-create")
        data = {
            "club": self.club.id,
            "team": self.team.id,
            "registration_number": "REG001",
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "1995-06-15",
            "nationality": "Ugandan",
            "position": "Forward",
            "player_type": PlayerRegistration.PlayerType.PROFESSIONAL,
            "registered_date": "2025-01-01",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PlayerRegistration.objects.count(), 1)
        created = PlayerRegistration.objects.get()
        self.assertEqual(created.full_name, "John Doe")
        self.assertEqual(
            created.submission_status,
            PlayerRegistration.SubmissionStatus.DRAFT,
        )
        self.assertEqual(created.status, PlayerRegistration.RegistrationStatus.INACTIVE)
        self.assertEqual(response.data["workflow"], "PLAYER_REGISTRATION_SUBMISSION")
        self.assertTrue(response.data["deprecated_direct_creation"])


class StaffMemberTests(TeamsAPITestCase):
    def test_create_staff_member(self):
        url = reverse("staff-member-list-create")
        data = {
            "club": self.club.id,
            "first_name": "Jane",
            "last_name": "Smith",
            "role": StaffMember.StaffRole.HEAD_COACH,
            "employment_type": StaffMember.EmploymentType.FULL_TIME,
            "email": "jane@example.com",
            "phone_number": "+256700000000",
            "start_date": "2025-01-01",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(StaffMember.objects.count(), 1)
        self.assertEqual(StaffMember.objects.first().full_name, "Jane Smith")


class PlayerTransferTests(TeamsAPITestCase):
    def setUp(self):
        super().setUp()
        self.team = Team.objects.create(
            club=self.club,
            name="First Team",
            team_type=Team.TeamType.FIRST_TEAM,
        )
        self.player = PlayerRegistration.objects.create(
            club=self.club,
            team=self.team,
            registration_number="REG001",
            first_name="John",
            last_name="Doe",
            date_of_birth="1995-06-15",
            nationality="Ugandan",
            position="Forward",
            player_type=PlayerRegistration.PlayerType.PROFESSIONAL,
            registered_date="2025-01-01",
        )
        self.other_club = Club.objects.create(
            name="Other FC",
            slug="other-fc",
            sport=Club.Sport.FOOTBALL,
            admin=self.club_admin,
        )
        ClubAdminScope.objects.create(
            user=self.club_admin,
            club=self.other_club,
            role=ClubAdminScope.Role.CHAIRMAN,
        )
        for club in (self.club, self.other_club):
            ClubAffiliation.objects.create(
                workspace=self.workspace,
                club=club,
                status=ClubAffiliation.Status.ACTIVE,
            )
        self.union_player = UnionPlayer.objects.create(
            union=self.union,
            union_player_number="TEST-P000001",
            first_name="John",
            last_name="Doe",
            date_of_birth="1995-06-15",
            nationality="Ugandan",
            status=UnionPlayer.Status.APPROVED,
        )
        self.authoritative_registration = UnionPlayerRegistration.objects.create(
            workspace=self.workspace,
            player=self.union_player,
            club=self.club,
            team=self.team,
            season=self.season,
            status=UnionPlayerRegistration.Status.ACTIVE,
            registration_type="FIRST_REGISTRATION",
            effective_from="2026-01-01",
            effective_to="2026-12-31",
            approved_by=self.union_admin,
        )

    def test_create_transfer(self):
        url = reverse("player-transfer-list-create")
        data = {
            "workspace": self.workspace.id,
            "source_registration": self.authoritative_registration.id,
            "destination_club": self.other_club.id,
            "transfer_type": PlayerTransfer.TransferType.PERMANENT,
            "effective_on": "2026-08-01",
            "documents": ["maintained-transfer-reference"],
            "fee_status": "PAID",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PlayerTransfer.objects.count(), 0)
        self.assertEqual(UnionPlayerTransfer.objects.count(), 1)
        created = UnionPlayerTransfer.objects.get()
        self.assertEqual(created.transfer_type, "PERMANENT")
        self.assertEqual(created.status, UnionPlayerTransfer.Status.DRAFT)
        self.assertEqual(response.data["workflow"], "UNION_PLAYER_TRANSFER")
        self.assertTrue(response.data["deprecated_direct_creation"])


class SquadSubmissionTests(TeamsAPITestCase):
    def setUp(self):
        super().setUp()
        self.team = Team.objects.create(
            club=self.club,
            name="First Team",
            team_type=Team.TeamType.FIRST_TEAM,
        )
        self.squad = Squad.objects.create(
            team=self.team,
            competition=self.competition,
            name="2025/26 Squad",
            season="2025/26",
        )
        self.player = PlayerRegistration.objects.create(
            club=self.club,
            team=self.team,
            registration_number="REG001",
            first_name="John",
            last_name="Doe",
            date_of_birth="1995-06-15",
            nationality="Ugandan",
            position="Forward",
            player_type=PlayerRegistration.PlayerType.PROFESSIONAL,
            registered_date="2025-01-01",
        )
        SquadMember.objects.create(
            squad=self.squad,
            player=self.player,
            jersey_number=10,
            position="Forward",
            is_captain=True,
            joined_date="2025-01-01",
        )

    def test_submit_squad(self):
        url = reverse("squad-submission-list-create")
        data = {
            "squad": self.squad.id,
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SquadSubmission.objects.count(), 1)
        self.squad.refresh_from_db()
        self.assertEqual(self.squad.status, Squad.SquadStatus.SUBMITTED)

    def test_union_review_approve(self):
        self.client.force_authenticate(user=self.union_admin)
        submission = SquadSubmission.objects.create(
            squad=self.squad,
            submission_number="SUB001",
            status=SquadSubmission.SubmissionStatus.SUBMITTED,
            submitted_by=self.club_admin,
        )
        url = reverse("squad-submission-review", kwargs={"pk": submission.pk})
        data = {"action": "approve"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        submission.refresh_from_db()
        self.assertEqual(submission.status, SquadSubmission.SubmissionStatus.APPROVED)

    def test_union_review_reject(self):
        self.client.force_authenticate(user=self.union_admin)
        submission = SquadSubmission.objects.create(
            squad=self.squad,
            submission_number="SUB002",
            status=SquadSubmission.SubmissionStatus.SUBMITTED,
            submitted_by=self.club_admin,
        )
        url = reverse("squad-submission-review", kwargs={"pk": submission.pk})
        data = {"action": "reject", "rejection_reason": "Player not eligible"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        submission.refresh_from_db()
        self.assertEqual(submission.status, SquadSubmission.SubmissionStatus.REJECTED)
