from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Club, User
from dashboards.models import (
    Competition,
    League,
    LeagueAdminScope,
    Match,
    Union,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
from ticketing.models import TicketType


class AdminWorkspaceDashboardTests(APITestCase):
    password = "StrongPass123!"

    def setUp(self):
        self.union = Union.objects.create(
            name="Test Rugby Union",
            slug="test-rugby-union",
        )
        self.other_union = Union.objects.create(
            name="Other Test Union",
            slug="other-test-union",
        )

        self.workspace = UnionWorkspace.objects.create(
            related_union=self.union,
            name="Test Rugby Union Workspace",
            slug="test-rugby-union-workspace",
            acronym="TRU",
            sport="Rugby",
            status=UnionWorkspace.Status.ACTIVE,
        )

        self.league = League.objects.create(
            union=self.union,
            name="Test Premiership",
            slug="test-premiership",
        )
        self.other_league = League.objects.create(
            union=self.other_union,
            name="Other Premiership",
            slug="other-premiership",
        )

        self.competition = Competition.objects.create(
            league=self.league,
            name="Test Premiership 2026",
            slug="test-premiership-2026",
            season="2026",
        )
        self.other_competition = Competition.objects.create(
            league=self.other_league,
            name="Other Premiership 2026",
            slug="other-premiership-2026",
            season="2026",
        )

        self.club = Club.objects.create(
            name="Test KOBS",
            slug="test-kobs",
            short_name="KOBS",
            sport=Club.Sport.RUGBY,
        )
        self.opponent = Club.objects.create(
            name="Test Heathens",
            slug="test-heathens",
            short_name="Heathens",
            sport=Club.Sport.RUGBY,
        )
        self.other_club = Club.objects.create(
            name="Unrelated Club",
            slug="unrelated-club",
            sport=Club.Sport.RUGBY,
        )

        self.match = Match.objects.create(
            competition=self.competition,
            home_club=self.club,
            away_club=self.opponent,
            match_date=timezone.now() + timedelta(days=2),
            venue="Test Stadium",
        )
        self.other_match = Match.objects.create(
            competition=self.other_competition,
            home_club=self.other_club,
            away_club=self.opponent,
            match_date=timezone.now() + timedelta(days=3),
            venue="Other Stadium",
        )

        TicketType.objects.create(
            match=self.match,
            name="Ordinary",
            price="10000.00",
            quantity_available=100,
            status=TicketType.Status.ACTIVE,
        )
        TicketType.objects.create(
            match=self.other_match,
            name="Ordinary",
            price="10000.00",
            quantity_available=100,
            status=TicketType.Status.ACTIVE,
        )

    def create_user(self, email, role, club=None):
        return User.objects.create_user(
            email=email,
            password=self.password,
            first_name="Test",
            last_name="User",
            role=role,
            club=club,
            is_email_verified=True,
        )

    def test_league_admin_workspace_is_competition_scoped(self):
        user = self.create_user(
            "league-admin@leagueos.test",
            User.Role.LEAGUE_ADMIN,
        )
        LeagueAdminScope.objects.create(
            user=user,
            league=self.league,
            competition=self.competition,
            role=LeagueAdminScope.Role.COMPETITION_ADMIN,
        )

        self.client.force_authenticate(user)

        response = self.client.get(
            "/api/dashboards/league-admin/workspace/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["summary"]["competitions"],
            1,
        )
        self.assertEqual(
            len(response.data["upcoming_fixtures"]),
            1,
        )
        self.assertEqual(
            response.data["upcoming_fixtures"][0]["id"],
            self.match.id,
        )

    def test_club_admin_workspace_excludes_other_clubs(self):
        user = self.create_user(
            "club-admin@leagueos.test",
            User.Role.CLUB_ADMIN,
            club=self.club,
        )
        self.club.admin = user
        self.club.save(update_fields=["admin"])

        self.client.force_authenticate(user)

        response = self.client.get(
            "/api/dashboards/club-admin/workspace/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["club"]["id"],
            self.club.id,
        )
        self.assertEqual(
            len(response.data["upcoming_fixtures"]),
            1,
        )
        self.assertEqual(
            response.data["upcoming_fixtures"][0]["id"],
            self.match.id,
        )

    def test_union_ticketing_workspace_excludes_other_union(self):
        user = self.create_user(
            "union-ticketing@leagueos.test",
            User.Role.TICKETING_OFFICER,
        )

        UnionWorkspaceMembership.objects.create(
            user=user,
            workspace=self.workspace,
            role=(
                UnionWorkspaceMembership.Role
                .TICKETING_OFFICER
            ),
            is_active=True,
        )

        self.client.force_authenticate(user)

        response = self.client.get(
            "/api/dashboards/ticketing-officer/workspace/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["selected_scope"]["scope_type"],
            "UNION",
        )
        self.assertEqual(len(response.data["events"]), 1)
        self.assertEqual(
            response.data["events"][0]["id"],
            self.match.id,
        )

    def test_club_ticketing_workspace_excludes_other_clubs(self):
        user = self.create_user(
            "club-ticketing@leagueos.test",
            User.Role.TICKETING_OFFICER,
            club=self.club,
        )

        self.client.force_authenticate(user)

        response = self.client.get(
            "/api/dashboards/ticketing-officer/workspace/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["selected_scope"]["scope_type"],
            "CLUB",
        )
        self.assertEqual(len(response.data["events"]), 1)
        self.assertEqual(
            response.data["events"][0]["id"],
            self.match.id,
        )
