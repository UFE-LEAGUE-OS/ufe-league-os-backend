import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from dashboards.models import Union, League, Competition, Match, Standing
from accounts.models import Club


@pytest.fixture
def user_model():
    """Fixture to provide the User model after Django is ready."""
    return get_user_model()


def create_user(User, email, role):
    """Factory to create a test user with the given role."""
    return User.objects.create_user(
        email=email,
        password="testpass123",
        first_name="Test",
        last_name="User",
        role=role,
    )


class TestDashboardAuthentication:
    """Test dashboard authentication and authorization."""

    def test_my_dashboard_requires_authentication(self, db):
        """Unauthenticated users should not access dashboards."""
        client = APIClient()
        url = reverse("my-dashboard")
        response = client.get(url)
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_fan_can_access_own_dashboard(self, db, user_model):
        """Fan users can access their own dashboard."""
        User = user_model
        user = create_user(User, "fan@example.com", User.Role.FAN)
        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse("my-dashboard")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data.get("role") == User.Role.FAN
        assert "dashboard" in response.data
        assert "user" in response.data

    def test_non_fan_cannot_access_fan_dashboard(self, db, user_model):
        """Non-fan users cannot access fan-only endpoints."""
        User = user_model
        user = create_user(User, "admin@example.com", User.Role.CLUB_ADMIN)
        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse("fan-dashboard")
        response = client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_club_admin_can_access_club_dashboard(self, db, user_model):
        """Club admin users can access their dashboard."""
        User = user_model
        user = create_user(User, "admin@example.com", User.Role.CLUB_ADMIN)
        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse("club-admin-dashboard")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data.get("role") == User.Role.CLUB_ADMIN


# ---------------------------------------------------------------------------
# Tests for Public (no-auth) Endpoints
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_data(db):
    """Create seed data for public endpoint tests."""
    # Create a couple of clubs
    club_a = Club.objects.create(name="Kampala City FC", slug="kampala-city-fc")
    club_b = Club.objects.create(name="Vipers SC", slug="vipers-sc")
    club_c = Club.objects.create(name="Express FC", slug="express-fc")

    # Create union, league, competition
    union = Union.objects.create(
        name="FUFA", slug="fufa", country="Uganda", website="https://fufa.co.ug"
    )
    league = League.objects.create(
        name="Uganda Premier League",
        slug="uganda-premier-league",
        union=union,
        is_active=True,
    )
    competition = Competition.objects.create(
        league=league,
        name="Uganda Premier League",
        slug="upl-2025-26",
        season="2025/26",
        is_active=True,
        start_date="2025-09-01",
        end_date="2026-05-31",
    )

    now = timezone.now()
    future = now + timezone.timedelta(days=7)
    past = now - timezone.timedelta(days=7)

    # Fixture (future match)
    fixture = Match.objects.create(
        competition=competition,
        home_club=club_a,
        away_club=club_b,
        status=Match.Status.SCHEDULED,
        match_date=future,
        venue="Mandela National Stadium",
        round="Matchweek 1",
    )

    # Completed match (result)
    result = Match.objects.create(
        competition=competition,
        home_club=club_c,
        away_club=club_a,
        status=Match.Status.COMPLETED,
        match_date=past,
        venue="St. Mary's Stadium",
        round="Matchweek 1",
        home_score=2,
        away_score=1,
        home_halftime_score=1,
        away_halftime_score=0,
    )

    # Standings entries
    Standing.objects.create(
        competition=competition,
        club=club_a,
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
        competition=competition,
        club=club_b,
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

    return {
        "club_a": club_a,
        "club_b": club_b,
        "club_c": club_c,
        "union": union,
        "league": league,
        "competition": competition,
        "fixture": fixture,
        "result": result,
    }


class TestPublicFixtures:
    """Test the public fixtures endpoint (no auth required)."""

    def test_public_fixtures_returns_upcoming_matches(self, seeded_data):
        """Unauthenticated users can fetch upcoming fixtures."""
        client = APIClient()
        url = reverse("public-fixtures")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert isinstance(data, list)
        assert len(data) >= 1
        # The fixture should be in the response
        fixture_data = data[0]
        assert fixture_data["status"] == "SCHEDULED"
        assert fixture_data["home_club_name"] == seeded_data["club_a"].name
        assert fixture_data["away_club_name"] == seeded_data["club_b"].name
        assert "home_club" in fixture_data
        assert "away_club" in fixture_data
        assert "home_score" in fixture_data

    def test_public_fixtures_filter_by_competition(self, seeded_data):
        """Fixtures can be filtered by competition ID."""
        client = APIClient()
        url = reverse("public-fixtures")
        response = client.get(url, {"competition": seeded_data["competition"].id})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        for match in response.data:
            assert match["competition"] == seeded_data["competition"].id

    def test_public_fixtures_filter_by_club(self, seeded_data):
        """Fixtures can be filtered by club ID."""
        client = APIClient()
        url = reverse("public-fixtures")
        response = client.get(url, {"club": seeded_data["club_a"].id})

        assert response.status_code == status.HTTP_200_OK
        # Should return matches where club_a is home or away
        assert len(response.data) >= 1

    def test_public_fixtures_no_auth_required(self, seeded_data):
        """Completely unauthenticated request should work."""
        client = APIClient()
        url = reverse("public-fixtures")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK


class TestPublicResults:
    """Test the public results endpoint (no auth required)."""

    def test_public_results_returns_completed_matches(self, seeded_data):
        """Unauthenticated users can fetch completed match results."""
        client = APIClient()
        url = reverse("public-results")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert isinstance(data, list)
        assert len(data) >= 1
        result_data = data[0]
        assert result_data["status"] == "COMPLETED"
        assert result_data["home_score"] == 2
        assert result_data["away_score"] == 1
        assert result_data["home_halftime_score"] == 1
        assert result_data["away_halftime_score"] == 0

    def test_public_results_filter_by_competition(self, seeded_data):
        """Results can be filtered by competition ID."""
        client = APIClient()
        url = reverse("public-results")
        response = client.get(url, {"competition": seeded_data["competition"].id})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_public_results_filter_by_club(self, seeded_data):
        """Results can be filtered by club ID."""
        client = APIClient()
        url = reverse("public-results")
        response = client.get(url, {"club": seeded_data["club_c"].id})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_public_results_no_auth_required(self, seeded_data):
        """Completely unauthenticated request should work."""
        client = APIClient()
        url = reverse("public-results")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK


class TestPublicStandings:
    """Test the public standings endpoint (no auth required)."""

    def test_public_standings_requires_competition(self, seeded_data):
        """Standings request without competition param returns 400."""
        client = APIClient()
        url = reverse("public-standings")
        response = client.get(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "competition" in response.data.get("detail", "").lower()

    def test_public_standings_returns_ordered_table(self, seeded_data):
        """Standings are returned ordered by position."""
        client = APIClient()
        url = reverse("public-standings")
        competition = seeded_data["competition"]
        response = client.get(url, {"competition": competition.id})

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert isinstance(data, list)
        assert len(data) == 2

        # Check ordering by position
        positions = [entry["position"] for entry in data]
        assert positions == sorted(positions)

        # Check first place data
        first = data[0]
        assert first["position"] == 1
        assert first["points"] == 3
        assert first["club_name"] == seeded_data["club_a"].name

    def test_public_standings_no_auth_required(self, seeded_data):
        """Completely unauthenticated request should work."""
        client = APIClient()
        url = reverse("public-standings")
        response = client.get(url, {"competition": seeded_data["competition"].id})
        assert response.status_code == status.HTTP_200_OK


class TestPublicClubs:
    """Test the public clubs endpoint (no auth required)."""

    def test_public_clubs_returns_all_clubs(self, seeded_data):
        """Unauthenticated users can fetch all clubs."""
        client = APIClient()
        url = reverse("public-clubs")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert isinstance(data, list)
        # We created 3 clubs
        assert len(data) == 3
        club_names = {club["name"] for club in data}
        assert "Kampala City FC" in club_names
        assert "Vipers SC" in club_names
        assert "Express FC" in club_names

    def test_public_clubs_no_auth_required(self, seeded_data):
        """Completely unauthenticated request should work."""
        client = APIClient()
        url = reverse("public-clubs")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK


class TestPublicUnions:
    """Test the public unions endpoint (no auth required)."""

    def test_public_unions_returns_all_unions(self, seeded_data):
        """Unauthenticated users can fetch all unions."""
        client = APIClient()
        url = reverse("public-unions")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert isinstance(data, list)
        assert len(data) == 1
        union = data[0]
        assert union["name"] == "FUFA"
        assert union["slug"] == "fufa"
        assert union["country"] == "Uganda"

    def test_public_unions_no_auth_required(self, seeded_data):
        """Completely unauthenticated request should work."""
        client = APIClient()
        url = reverse("public-unions")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK


class TestPublicLeagues:
    """Test the public leagues endpoint (no auth required)."""

    def test_public_leagues_returns_all_leagues(self, seeded_data):
        """Unauthenticated users can fetch all leagues."""
        client = APIClient()
        url = reverse("public-leagues")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert isinstance(data, list)
        assert len(data) == 1
        league = data[0]
        assert league["name"] == "Uganda Premier League"
        assert league["union"] == seeded_data["union"].id
        assert league["union_name"] == "FUFA"

    def test_public_leagues_filter_by_union(self, seeded_data):
        """Leagues can be filtered by union ID."""
        client = APIClient()
        url = reverse("public-leagues")
        response = client.get(url, {"union": seeded_data["union"].id})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_public_leagues_empty_with_invalid_union(self, seeded_data):
        """Invalid union filter returns empty list."""
        client = APIClient()
        url = reverse("public-leagues")
        response = client.get(url, {"union": 99999})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

    def test_public_leagues_no_auth_required(self, seeded_data):
        """Completely unauthenticated request should work."""
        client = APIClient()
        url = reverse("public-leagues")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK


class TestPublicCompetitions:
    """Test the public competitions endpoint (no auth required)."""

    def test_public_competitions_returns_all(self, seeded_data):
        """Unauthenticated users can fetch all competitions."""
        client = APIClient()
        url = reverse("public-competitions")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert isinstance(data, list)
        assert len(data) == 1
        comp = data[0]
        assert comp["name"] == seeded_data["competition"].name
        assert comp["season"] == "2025/26"
        assert comp["league_name"] == "Uganda Premier League"

    def test_public_competitions_filter_by_league(self, seeded_data):
        """Competitions can be filtered by league ID."""
        client = APIClient()
        url = reverse("public-competitions")
        response = client.get(url, {"league": seeded_data["league"].id})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_public_competitions_filter_by_active(self, seeded_data):
        """Competitions can be filtered by is_active flag."""
        client = APIClient()
        url = reverse("public-competitions")
        response = client.get(url, {"is_active": "true"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

        # Filter for inactive
        response = client.get(url, {"is_active": "false"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

    def test_public_competitions_no_auth_required(self, seeded_data):
        """Completely unauthenticated request should work."""
        client = APIClient()
        url = reverse("public-competitions")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
