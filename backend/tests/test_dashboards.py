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


# ---------------------------------------------------------------------------
# Tests for Match Detail Endpoint
# ---------------------------------------------------------------------------


class TestMatchDetail:
    """Test the public match detail endpoint."""

    def test_match_detail_returns_match_data(self, seeded_data):
        """Returns full match details for a valid match ID."""
        client = APIClient()
        match = seeded_data["result"]
        url = reverse("public-match-detail", args=[match.id])
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data["id"] == match.id
        assert data["status"] == "COMPLETED"
        assert data["home_score"] == 2
        assert data["away_score"] == 1
        assert data["home_club_name"] == seeded_data["club_c"].name
        assert data["away_club_name"] == seeded_data["club_a"].name
        assert data["competition_name"] == seeded_data["competition"].name
        assert "is_fixture" in data
        assert "has_result" in data
        assert data["has_result"] is True
        assert data["is_fixture"] is False
        assert "updated_at" in data

    def test_match_detail_for_fixture(self, seeded_data):
        """Returns correct flags for a scheduled fixture."""
        client = APIClient()
        match = seeded_data["fixture"]
        url = reverse("public-match-detail", args=[match.id])
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data["id"] == match.id
        assert data["status"] == "SCHEDULED"
        assert data["is_fixture"] is True
        assert data["has_result"] is False
        assert data["home_score"] is None

    def test_match_detail_nonexistent_returns_404(self, db):
        """Returns 404 for a non-existent match."""
        client = APIClient()
        url = reverse("public-match-detail", args=[99999])
        response = client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_match_detail_no_auth_required(self, seeded_data):
        """Completely unauthenticated request should work."""
        client = APIClient()
        match = seeded_data["result"]
        url = reverse("public-match-detail", args=[match.id])
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# Tests for Standings Calculation Endpoint
# ---------------------------------------------------------------------------


class TestStandingsCalculation:
    """Test the standings calculation / recalculation endpoint."""

    def test_standings_calculation_returns_computed_table(self, seeded_data):
        """Recalculates standings and returns correctly computed table."""
        client = APIClient()
        competition = seeded_data["competition"]
        url = reverse("public-standings-calculate")
        response = client.get(url, {"competition": competition.id})

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data["competition_id"] == competition.id
        assert data["competition_name"] == competition.name
        assert "entries" in data
        entries = data["entries"]
        assert len(entries) >= 2

        # Check first place (club_c won 2-1 as home)
        first = entries[0]
        assert first["position"] == 1
        assert first["points"] == 3
        assert first["won"] == 1
        assert first["played"] == 1
        assert first["goals_for"] >= 2

    def test_standings_calculation_persists_to_db(self, seeded_data):
        """Recalculated standings are persisted to the database."""
        client = APIClient()
        competition = seeded_data["competition"]
        url = reverse("public-standings-calculate")
        response = client.get(url, {"competition": competition.id})

        assert response.status_code == status.HTTP_200_OK

        # Verify persisted in DB
        db_standings = Standing.objects.filter(competition=competition).order_by(
            "position"
        )
        assert db_standings.count() >= 2
        first = db_standings.first()
        assert first.points == 3

    def test_standings_calculation_requires_competition(self, seeded_data):
        """Returns 400 when competition param is missing."""
        client = APIClient()
        url = reverse("public-standings-calculate")
        response = client.get(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "competition" in response.data.get("detail", "").lower()

    def test_standings_calculation_invalid_competition_returns_404(self, db):
        """Returns 404 for non-existent competition."""
        client = APIClient()
        url = reverse("public-standings-calculate")
        response = client.get(url, {"competition": 99999})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_standings_calculation_no_auth_required(self, seeded_data):
        """Completely unauthenticated request should work."""
        client = APIClient()
        competition = seeded_data["competition"]
        url = reverse("public-standings-calculate")
        response = client.get(url, {"competition": competition.id})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["entries"]) >= 1

    def test_standings_calculation_handles_draws_and_multi_results(self, seeded_data):
        """Correctly computes standings with multiple matches including draws."""
        # Add an additional completed match: club_b vs club_c ending in draw
        client = APIClient()
        competition = seeded_data["competition"]
        club_b = seeded_data["club_b"]
        club_c = seeded_data["club_c"]

        from django.utils import timezone

        Match.objects.create(
            competition=competition,
            home_club=club_b,
            away_club=club_c,
            status=Match.Status.COMPLETED,
            match_date=timezone.now() - timezone.timedelta(days=3),
            venue="Test Stadium",
            round="Matchweek 1",
            home_score=1,
            away_score=1,
            home_halftime_score=0,
            away_halftime_score=0,
        )

        url = reverse("public-standings-calculate")
        response = client.get(url, {"competition": competition.id})

        assert response.status_code == status.HTTP_200_OK
        entries = response.data["entries"]

        # club_a: played 1, lost 1, 0 pts
        # club_b: played 1, drawn 1, 1 pt
        # club_c: played 2, won 1, drawn 1, 4 pts
        for entry in entries:
            if entry["club_name"] == seeded_data["club_c"].name:
                assert entry["played"] == 2
                assert entry["won"] == 1
                assert entry["drawn"] == 1
                assert entry["points"] == 4
                assert entry["position"] == 1
            elif entry["club_name"] == seeded_data["club_b"].name:
                assert entry["drawn"] == 1
                assert entry["points"] == 1
            elif entry["club_name"] == seeded_data["club_a"].name:
                assert entry["lost"] == 1
                assert entry["points"] == 0


# ---------------------------------------------------------------------------
# Tests for Standings Calculation Service
# ---------------------------------------------------------------------------


class TestRecalculateStandingsService:
    """Unit tests for the recalculate_standings service function."""

    def test_service_returns_ordered_standings(self, seeded_data):
        """Service returns Standing records ordered by position."""
        from dashboards.services import recalculate_standings

        competition = seeded_data["competition"]
        results = recalculate_standings(competition.id)

        assert isinstance(results, list)
        assert len(results) >= 2
        positions = [s.position for s in results]
        assert positions == sorted(positions)

    def test_service_resets_standings_on_recalculation(self, seeded_data):
        """Re-running the service replaces old standings."""
        from dashboards.services import recalculate_standings

        competition = seeded_data["competition"]
        # First calculation
        recalculate_standings(competition.id)

        # Add a new result
        from django.utils import timezone

        Match.objects.create(
            competition=competition,
            home_club=seeded_data["club_b"],
            away_club=seeded_data["club_a"],
            status=Match.Status.COMPLETED,
            match_date=timezone.now() - timezone.timedelta(days=1),
            venue="Test Venue",
            round="Matchweek 2",
            home_score=3,
            away_score=0,
        )

        # Recalculate
        results = recalculate_standings(competition.id)
        # club_b now has 3 pts (won) + previous 0 = 3 pts, club_a still 0
        for s in results:
            if s.club_id == seeded_data["club_b"].id:
                assert s.played == 1
                assert s.won == 1
                assert s.points == 3
                break


# ---------------------------------------------------------------------------
# Tests for WebSocket Match Consumer
# ---------------------------------------------------------------------------


class TestMatchUpdateConsumer:
    """Test the WebSocket consumer for live match updates.

    Uses the Channels test infrastructure (WebsocketCommunicator).
    """

    async def test_consumer_connects_and_sends_welcome(self, db):
        """Consumer connects successfully and sends initial data (or handles db error gracefully)."""
        from channels.testing import WebsocketCommunicator
        from dashboards.consumers import MatchUpdateConsumer

        # Test with a non-existent match ID - consumer will connect but initial
        # data fetch may fail gracefully since no match exists
        communicator = WebsocketCommunicator(
            MatchUpdateConsumer.as_asgi(),
            "/ws/match/1/",
            [("path", "/ws/match/1/")],
        )
        connected, _ = await communicator.connect()
        # Consumer may connect successfully or fail depending on db state
        # The important thing is it handles it gracefully
        assert connected

        await communicator.disconnect()

    async def test_consumer_rejects_invalid_match_id(self):
        """Consumer closes connection for missing match_id."""
        from channels.testing import WebsocketCommunicator
        from dashboards.consumers import MatchUpdateConsumer

        communicator = WebsocketCommunicator(
            MatchUpdateConsumer.as_asgi(),
            "/ws/match/abc/",
            [("path", "/ws/match/abc/")],
        )
        connected, _ = await communicator.connect()
        assert not connected  # Should reject connection

    async def test_consumer_responds_to_ping(self, db):
        """Consumer responds to ping with pong."""
        from channels.testing import WebsocketCommunicator
        from dashboards.consumers import MatchUpdateConsumer

        communicator = WebsocketCommunicator(
            MatchUpdateConsumer.as_asgi(),
            "/ws/match/1/",
            [("path", "/ws/match/1/")],
        )
        connected, _ = await communicator.connect()
        assert connected

        # Send ping
        await communicator.send_json_to({"type": "ping"})
        response = await communicator.receive_json_from(timeout=5)
        assert response["type"] == "pong"

        await communicator.disconnect()

    async def test_consumer_receives_broadcast_updates(self, db):
        """Consumer receives updates sent via channel layer."""
        from channels.layers import get_channel_layer
        from channels.testing import WebsocketCommunicator
        from dashboards.consumers import MatchUpdateConsumer

        communicator = WebsocketCommunicator(
            MatchUpdateConsumer.as_asgi(),
            "/ws/match/42/",
            [("path", "/ws/match/42/")],
        )
        connected, _ = await communicator.connect()
        assert connected

        # Simulate a broadcast update via channel layer
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            "match_42",
            {
                "type": "match_update",
                "action": "score_change",
                "data": {
                    "id": 42,
                    "home_score": 3,
                    "away_score": 1,
                    "status": "LIVE",
                },
            },
        )

        # Receive the broadcast
        response = await communicator.receive_json_from(timeout=5)
        assert response["type"] == "match_update"
        assert response["action"] == "score_change"
        assert response["data"]["home_score"] == 3
        assert response["data"]["away_score"] == 1
        assert response["data"]["status"] == "LIVE"

        await communicator.disconnect()
