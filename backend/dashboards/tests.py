from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import AuditLog, Club, ClubAdminScope

from .models import Competition, League, Match, Standing, Union

# Create your tests here.
User = get_user_model()


class DashboardAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "StrongPass123"

    def create_user(self, email, role):
        return User.objects.create_user(
            email=email,
            phone_number=None,
            password=self.password,
            first_name="Test",
            last_name="User",
            role=role,
        )

    def authenticate(self, user):
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

        login_response = self.client.post(
            "/api/accounts/login/",
            {
                "identifier": user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(login_response.status_code, 200)

        access_token = login_response.data["access"]

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

    def test_my_dashboard_requires_authentication(self):
        response = self.client.get("/api/dashboards/me/")

        self.assertEqual(response.status_code, 401)

    def test_fan_can_access_fan_dashboard(self):
        user = self.create_user("fan-dashboard@example.com", User.Role.FAN)
        self.authenticate(user)

        response = self.client.get("/api/dashboards/fan/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], User.Role.FAN)
        self.assertEqual(response.data["dashboard"]["title"], "Fan Dashboard")

    def test_fan_cannot_access_club_admin_dashboard(self):
        user = self.create_user("fan-blocked@example.com", User.Role.FAN)
        self.authenticate(user)

        response = self.client.get("/api/dashboards/club-admin/")

        self.assertEqual(response.status_code, 403)
        audit = AuditLog.objects.get(
            action="access_denied",
            path="/api/dashboards/club-admin/",
            actor=user,
        )
        self.assertEqual(audit.category, AuditLog.Category.ACCESS_VIOLATION)
        self.assertEqual(audit.status_code, 403)
        self.assertEqual(
            audit.details,
            {"permission": "dashboard.club_admin"},
        )

    def test_club_admin_can_access_club_admin_dashboard(self):
        user = self.create_user(
            "club-admin-dashboard@example.com",
            User.Role.CLUB_ADMIN,
        )
        club = Club.objects.create(
            name="Entitled Club",
            slug="entitled-club",
        )
        ClubAdminScope.objects.create(
            user=user,
            club=club,
            role=ClubAdminScope.Role.CLUB_ADMIN,
        )
        self.authenticate(user)

        response = self.client.get("/api/dashboards/club-admin/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], User.Role.CLUB_ADMIN)
        self.assertIn("Admin", response.data["dashboard"]["title"])

    def test_unscoped_club_admin_cannot_access_club_admin_dashboard(self):
        user = self.create_user(
            "unscoped-club-admin@example.com",
            User.Role.CLUB_ADMIN,
        )
        self.authenticate(user)

        response = self.client.get("/api/dashboards/club-admin/")

        self.assertEqual(response.status_code, 403)

    def test_my_dashboard_resolves_fan_routes(self):
        user = self.create_user("my-fan-dashboard@example.com", User.Role.FAN)
        self.authenticate(user)

        response = self.client.get("/api/dashboards/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["frontend_dashboard_route"], "/dashboard/fan")
        self.assertEqual(
            response.data["backend_dashboard_route"], "/api/dashboards/fan/"
        )
        self.assertEqual(response.data["dashboard"]["title"], "Fan Dashboard")

    def test_unscoped_referee_my_dashboard_has_no_destination(self):
        user = self.create_user(
            "referee-dashboard-route@example.com",
            User.Role.REFEREE,
        )
        self.authenticate(user)

        response = self.client.get("/api/dashboards/me/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["frontend_dashboard_route"])
        self.assertIsNone(response.data["backend_dashboard_route"])
        self.assertEqual(
            response.data["user"]["dashboard_access"],
            {
                "version": 1,
                "default_entitlement_id": None,
                "entitlements": [],
            },
        )

    def test_all_roles_can_resolve_my_dashboard(self):
        role_data = [
            (User.Role.FAN, "/api/dashboards/fan/"),
            (User.Role.CLUB_ADMIN, None),
            (User.Role.LEAGUE_ADMIN, None),
            (User.Role.UNION_ADMIN, None),
            (User.Role.SUPER_ADMIN, "/api/dashboards/super-admin/"),
            (User.Role.REFEREE, None),
            (User.Role.TICKETING_OFFICER, None),
            (User.Role.SPONSOR, None),
        ]

        for index, role_info in enumerate(role_data):
            role, expected_backend_route = role_info

            with self.subTest(role=role):
                self.client.credentials()

                user = self.create_user(
                    email=f"role-{index}@example.com",
                    role=role,
                )
                self.authenticate(user)

                response = self.client.get("/api/dashboards/me/")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["role"], role)
                self.assertEqual(
                    response.data["backend_dashboard_route"],
                    expected_backend_route,
                )


class PublicDashboardEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @classmethod
    def setUpTestData(cls):
        cls.club_a = Club.objects.create(
            name="Kampala City FC",
            slug="kampala-city-fc",
        )
        cls.club_b = Club.objects.create(
            name="Vipers SC",
            slug="vipers-sc",
        )
        cls.club_c = Club.objects.create(
            name="Express FC",
            slug="express-fc",
        )

        cls.union = Union.objects.create(
            name="FUFA",
            slug="fufa",
            country="Uganda",
            website="https://fufa.co.ug",
        )

        cls.league = League.objects.create(
            name="Uganda Premier League",
            slug="uganda-premier-league",
            union=cls.union,
            is_active=True,
        )

        cls.competition = Competition.objects.create(
            league=cls.league,
            name="Uganda Premier League",
            slug="upl-2025-26",
            season="2025/26",
            is_active=True,
            start_date=date(2025, 9, 1),
            end_date=date(2026, 5, 31),
        )

        cls.future_match_date = timezone.now() + timedelta(days=7)
        cls.past_match_date = timezone.now() - timedelta(days=7)

        cls.fixture = Match.objects.create(
            competition=cls.competition,
            home_club=cls.club_a,
            away_club=cls.club_b,
            status=Match.Status.SCHEDULED,
            match_date=cls.future_match_date,
            venue="Mandela National Stadium",
            round="Matchweek 1",
        )

        cls.result = Match.objects.create(
            competition=cls.competition,
            home_club=cls.club_c,
            away_club=cls.club_a,
            status=Match.Status.COMPLETED,
            match_date=cls.past_match_date,
            venue="St. Mary's Stadium",
            round="Matchweek 1",
            home_score=2,
            away_score=1,
            home_halftime_score=1,
            away_halftime_score=0,
        )

        Standing.objects.create(
            competition=cls.competition,
            club=cls.club_a,
            position=1,
            played=1,
            won=1,
            drawn=0,
            lost=0,
            goals_for=2,
            goals_against=1,
            goal_difference=1,
            points=3,
            form="W",
        )

        Standing.objects.create(
            competition=cls.competition,
            club=cls.club_b,
            position=2,
            played=1,
            won=0,
            drawn=1,
            lost=0,
            goals_for=1,
            goals_against=1,
            goal_difference=0,
            points=1,
            form="D",
        )

    def test_public_fixtures_returns_upcoming_matches_without_authentication(self):
        response = self.client.get("/api/dashboards/public/fixtures/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

        fixture_data = response.data[0]

        self.assertEqual(fixture_data["status"], Match.Status.SCHEDULED)
        self.assertEqual(fixture_data["home_club_name"], self.club_a.name)
        self.assertEqual(fixture_data["away_club_name"], self.club_b.name)
        self.assertIn("home_club", fixture_data)
        self.assertIn("away_club", fixture_data)
        self.assertIn("home_score", fixture_data)

    def test_public_fixtures_can_filter_by_competition(self):
        response = self.client.get(
            "/api/dashboards/public/fixtures/",
            {"competition": self.competition.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

        for match in response.data:
            self.assertEqual(match["competition"], self.competition.id)

    def test_public_fixtures_can_filter_by_club(self):
        response = self.client.get(
            "/api/dashboards/public/fixtures/",
            {"club": self.club_a.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_public_match_detail_serializes_club_logo_fields(self):
        response = self.client.get(f"/api/dashboards/public/matches/{self.fixture.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("home_club_logo_url", response.data)
        self.assertIn("away_club_logo_url", response.data)

    def test_public_results_returns_completed_matches_without_authentication(self):
        response = self.client.get("/api/dashboards/public/results/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

        result_data = response.data[0]

        self.assertEqual(result_data["status"], Match.Status.COMPLETED)
        self.assertEqual(result_data["home_score"], 2)
        self.assertEqual(result_data["away_score"], 1)
        self.assertEqual(result_data["home_halftime_score"], 1)
        self.assertEqual(result_data["away_halftime_score"], 0)

    def test_public_results_can_filter_by_competition(self):
        response = self.client.get(
            "/api/dashboards/public/results/",
            {"competition": self.competition.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

        for match in response.data:
            self.assertEqual(match["competition"], self.competition.id)

    def test_public_results_can_filter_by_club(self):
        response = self.client.get(
            "/api/dashboards/public/results/",
            {"club": self.club_c.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_public_standings_requires_competition_query_parameter(self):
        response = self.client.get("/api/dashboards/public/standings/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("competition", response.data["detail"].lower())

    def test_public_standings_returns_ordered_table_without_authentication(self):
        response = self.client.get(
            "/api/dashboards/public/standings/",
            {"competition": self.competition.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        positions = [entry["position"] for entry in response.data]

        self.assertEqual(positions, sorted(positions))
        self.assertEqual(response.data[0]["position"], 1)
        self.assertEqual(response.data[0]["points"], 3)
        self.assertEqual(response.data[0]["club_name"], self.club_a.name)

    def test_public_clubs_returns_all_clubs_without_authentication(self):
        response = self.client.get("/api/dashboards/public/clubs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        club_names = {club["name"] for club in response.data}

        self.assertIn("Kampala City FC", club_names)
        self.assertIn("Vipers SC", club_names)
        self.assertIn("Express FC", club_names)

    def test_public_unions_returns_all_unions_without_authentication(self):
        response = self.client.get("/api/dashboards/public/unions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "FUFA")
        self.assertEqual(response.data[0]["slug"], "fufa")
        self.assertEqual(response.data[0]["country"], "Uganda")

    def test_public_leagues_returns_all_leagues_without_authentication(self):
        response = self.client.get("/api/dashboards/public/leagues/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Uganda Premier League")
        self.assertEqual(response.data[0]["union"], self.union.id)
        self.assertEqual(response.data[0]["union_name"], "FUFA")

    def test_public_leagues_can_filter_by_union(self):
        response = self.client.get(
            "/api/dashboards/public/leagues/",
            {"union": self.union.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_public_leagues_returns_empty_list_for_unknown_union(self):
        response = self.client.get(
            "/api/dashboards/public/leagues/",
            {"union": 99999},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_public_competitions_returns_all_competitions_without_authentication(self):
        response = self.client.get("/api/dashboards/public/competitions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], self.competition.name)
        self.assertEqual(response.data[0]["season"], "2025/26")
        self.assertEqual(response.data[0]["league_name"], "Uganda Premier League")

    def test_public_competitions_can_filter_by_league(self):
        response = self.client.get(
            "/api/dashboards/public/competitions/",
            {"league": self.league.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_public_competitions_can_filter_by_active_status(self):
        active_response = self.client.get(
            "/api/dashboards/public/competitions/",
            {"is_active": "true"},
        )

        inactive_response = self.client.get(
            "/api/dashboards/public/competitions/",
            {"is_active": "false"},
        )

        self.assertEqual(active_response.status_code, status.HTTP_200_OK)
        self.assertEqual(inactive_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(active_response.data), 1)
        self.assertEqual(len(inactive_response.data), 0)
