import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from governance.models import (
    CompetitionFormat,
    LeagueStandard,
    Rule,
    SportVariant,
)
from dashboards.models import League, Union


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


@pytest.fixture
def super_admin_user(user_model):
    return create_user(
        user_model, "superadmin@example.com", user_model.Role.SUPER_ADMIN
    )


@pytest.fixture
def league_admin_user(user_model):
    return create_user(
        user_model, "leagueadmin@example.com", user_model.Role.LEAGUE_ADMIN
    )


@pytest.fixture
def authenticated_client(super_admin_user):
    """Return an APIClient authenticated as a super admin."""
    client = APIClient()
    client.force_authenticate(user=super_admin_user)
    return client


@pytest.fixture
def league_admin_client(league_admin_user):
    """Return an APIClient authenticated as a league admin."""
    client = APIClient()
    client.force_authenticate(user=league_admin_user)
    return client


@pytest.fixture
def unauthenticated_client():
    return APIClient()


@pytest.fixture
def seeded_sport_variant(db):
    return SportVariant.objects.create(
        name="Football 11-a-side",
        slug="football-11-a-side",
        description="Standard 11v11 association football",
        players_per_team=11,
        max_substitutes=5,
        match_duration_minutes=90,
        has_halftime=True,
        halftime_duration_minutes=15,
        has_extra_time=True,
        extra_time_duration_minutes=30,
        has_penalties=True,
        max_red_cards_default=1,
        points_win=3,
        points_draw=1,
        points_loss=0,
    )


@pytest.fixture
def seeded_competition_format(db):
    return CompetitionFormat.objects.create(
        name="Double Round Robin",
        slug="double-round-robin",
        description="Each team plays every other team twice (home and away)",
        stage_type=CompetitionFormat.StageType.SINGLE_STAGE,
        has_home_and_away=True,
        max_teams_default=16,
        min_teams_default=2,
        tie_breakers=[
            "goal_difference",
            "goals_scored",
            "head_to_head",
        ],
    )


@pytest.fixture
def seeded_rule(db, super_admin_user):
    return Rule.objects.create(
        title="Minimum Stadium Capacity",
        slug="minimum-stadium-capacity",
        rule_number="COMP-001",
        category=Rule.Category.COMPETITION,
        priority=Rule.Priority.MANDATORY,
        description="All clubs must have a stadium with minimum capacity of 5,000 "
        "seated spectators.",
        summary="Stadium capacity minimum 5,000.",
        version="1.0",
        effective_date="2025-01-01",
        created_by=super_admin_user,
    )


@pytest.fixture
def seeded_league(db):
    union = Union.objects.create(
        name="Test Union",
        slug="test-union",
        country="Uganda",
    )
    return League.objects.create(
        name="Test League",
        slug="test-league",
        union=union,
        is_active=True,
    )


@pytest.fixture
def seeded_published_rule(db, super_admin_user):
    return Rule.objects.create(
        title="Player Registration Deadline",
        slug="player-registration-deadline",
        rule_number="REG-001",
        category=Rule.Category.REGISTRATION,
        priority=Rule.Priority.MANDATORY,
        description="All players must be registered at least 48 hours before match "
        "kickoff.",
        summary="Register players 48h before match.",
        version="1.0",
        is_published=True,
        published_at=timezone.now(),
        created_by=super_admin_user,
    )


@pytest.fixture
def seeded_league_standard(db, seeded_published_rule, seeded_league, super_admin_user):
    return LeagueStandard.objects.create(
        rule=seeded_published_rule,
        league=seeded_league,
        assigned_by=super_admin_user,
    )


# ============================================================================
# SPORT VARIANTS CRUD TESTS
# ============================================================================


class TestSportVariantAuthentication:
    """Test that sport variant APIs require super admin auth."""

    def test_list_requires_authentication(self, db):
        client = APIClient()
        url = reverse("sport-variant-list-create")
        response = client.get(url)
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_create_requires_super_admin(self, db, league_admin_client):
        url = reverse("sport-variant-list-create")
        response = league_admin_client.post(url, {"name": "Futsal", "slug": "futsal"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_requires_authentication(self, db, unauthenticated_client):
        url = reverse("sport-variant-list-create")
        response = unauthenticated_client.post(
            url, {"name": "Futsal", "slug": "futsal"}
        )
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


class TestSportVariantCRUD:
    """Test CRUD operations for sport variants."""

    def test_create_sport_variant(self, db, authenticated_client):
        url = reverse("sport-variant-list-create")
        payload = {
            "name": "Futsal",
            "slug": "futsal",
            "description": "5v5 indoor football",
            "players_per_team": 5,
            "max_substitutes": 7,
            "match_duration_minutes": 40,
            "has_halftime": True,
            "halftime_duration_minutes": 10,
            "points_win": 3,
            "points_draw": 1,
            "points_loss": 0,
        }
        response = authenticated_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data
        assert data["name"] == "Futsal"
        assert data["slug"] == "futsal"
        assert data["players_per_team"] == 5
        assert data["match_duration_minutes"] == 40
        assert data["is_verified"] is False
        assert "id" in data

    def test_create_sport_variant_duplicate_slug(
        self, db, authenticated_client, seeded_sport_variant
    ):
        url = reverse("sport-variant-list-create")
        payload = {
            "name": "Duplicate Slug",
            "slug": "football-11-a-side",
        }
        response = authenticated_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_sport_variants(self, db, authenticated_client, seeded_sport_variant):
        url = reverse("sport-variant-list-create")
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        names = [v["name"] for v in response.data]
        assert "Football 11-a-side" in names

    def test_retrieve_sport_variant(
        self, db, authenticated_client, seeded_sport_variant
    ):
        url = reverse("sport-variant-detail", kwargs={"pk": seeded_sport_variant.pk})
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Football 11-a-side"
        assert response.data["players_per_team"] == 11

    def test_update_sport_variant(self, db, authenticated_client, seeded_sport_variant):
        url = reverse("sport-variant-detail", kwargs={"pk": seeded_sport_variant.pk})
        response = authenticated_client.patch(
            url, {"max_substitutes": 3}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["max_substitutes"] == 3

    def test_full_update_sport_variant(
        self, db, authenticated_client, seeded_sport_variant
    ):
        url = reverse("sport-variant-detail", kwargs={"pk": seeded_sport_variant.pk})
        payload = {
            "name": "Updated Football",
            "slug": "updated-football",
            "description": "Updated",
            "players_per_team": 11,
            "max_substitutes": 5,
            "match_duration_minutes": 90,
            "has_halftime": True,
            "halftime_duration_minutes": 15,
            "has_extra_time": False,
            "extra_time_duration_minutes": 0,
            "has_penalties": False,
            "max_red_cards_default": 1,
            "points_win": 3,
            "points_draw": 1,
            "points_loss": 0,
        }
        response = authenticated_client.put(url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Updated Football"
        assert response.data["has_extra_time"] is False

    def test_delete_sport_variant(self, db, authenticated_client, seeded_sport_variant):
        url = reverse("sport-variant-detail", kwargs={"pk": seeded_sport_variant.pk})
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        # Verify deletion
        get_response = authenticated_client.get(url)
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_verify_sport_variant(self, db, authenticated_client, seeded_sport_variant):
        assert seeded_sport_variant.is_verified is False
        url = reverse("sport-variant-verify", kwargs={"pk": seeded_sport_variant.pk})
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["variant"]["is_verified"] is True
        # Verify it's persisted
        seeded_sport_variant.refresh_from_db()
        assert seeded_sport_variant.is_verified is True

    def test_retrieve_nonexistent_variant(self, db, authenticated_client):
        url = reverse("sport-variant-detail", kwargs={"pk": 99999})
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_verify_nonexistent_variant(self, db, authenticated_client):
        url = reverse("sport-variant-verify", kwargs={"pk": 99999})
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# COMPETITION FORMATS CRUD TESTS
# ============================================================================


class TestCompetitionFormatAuthentication:
    """Test that competition format APIs require super admin auth."""

    def test_list_requires_authentication(self, db):
        client = APIClient()
        url = reverse("competition-format-list-create")
        response = client.get(url)
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_create_requires_super_admin(self, db, league_admin_client):
        url = reverse("competition-format-list-create")
        response = league_admin_client.post(
            url, {"name": "Test Format", "slug": "test-format"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestCompetitionFormatCRUD:
    """Test CRUD operations for competition formats."""

    def test_create_competition_format(self, db, authenticated_client):
        url = reverse("competition-format-list-create")
        payload = {
            "name": "Knockout",
            "slug": "knockout",
            "description": "Single elimination knockout tournament",
            "stage_type": CompetitionFormat.StageType.SINGLE_STAGE,
            "has_home_and_away": False,
            "max_teams_default": 32,
            "min_teams_default": 2,
            "has_third_place_match": True,
            "has_replays": False,
            "tie_breakers": ["extra_time", "penalties"],
        }
        response = authenticated_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Knockout"
        assert response.data["slug"] == "knockout"
        assert response.data["is_verified"] is False

    def test_list_competition_formats(
        self, db, authenticated_client, seeded_competition_format
    ):
        url = reverse("competition-format-list-create")
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_retrieve_competition_format(
        self, db, authenticated_client, seeded_competition_format
    ):
        url = reverse(
            "competition-format-detail", kwargs={"pk": seeded_competition_format.pk}
        )
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Double Round Robin"

    def test_update_competition_format(
        self, db, authenticated_client, seeded_competition_format
    ):
        url = reverse(
            "competition-format-detail", kwargs={"pk": seeded_competition_format.pk}
        )
        response = authenticated_client.patch(
            url, {"max_teams_default": 20}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["max_teams_default"] == 20

    def test_delete_competition_format(
        self, db, authenticated_client, seeded_competition_format
    ):
        url = reverse(
            "competition-format-detail", kwargs={"pk": seeded_competition_format.pk}
        )
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_verify_competition_format(
        self, db, authenticated_client, seeded_competition_format
    ):
        url = reverse(
            "competition-format-verify", kwargs={"pk": seeded_competition_format.pk}
        )
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["format"]["is_verified"] is True

    def test_verify_nonexistent_format(self, db, authenticated_client):
        url = reverse("competition-format-verify", kwargs={"pk": 99999})
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# RULES & STANDARDS CRUD TESTS
# ============================================================================


class TestRuleAuthentication:
    """Test that rules APIs require super admin auth."""

    def test_list_requires_authentication(self, db):
        client = APIClient()
        url = reverse("rule-list-create")
        response = client.get(url)
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_create_requires_super_admin(self, db, league_admin_client):
        url = reverse("rule-list-create")
        response = league_admin_client.post(
            url, {"title": "Test Rule", "slug": "test-rule", "description": "Test"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestRuleCRUD:
    """Test CRUD operations for rules & standards."""

    def test_create_rule(self, db, authenticated_client):
        url = reverse("rule-list-create")
        payload = {
            "title": "Club Licensing Requirement",
            "slug": "club-licensing-requirement",
            "rule_number": "COMP-002",
            "category": Rule.Category.COMPLIANCE,
            "priority": Rule.Priority.MANDATORY,
            "description": "All clubs must obtain annual licensing from the governing body.",
            "summary": "Annual club licensing required.",
            "version": "1.0",
            "effective_date": "2025-06-01",
        }
        response = authenticated_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data
        assert data["title"] == "Club Licensing Requirement"
        assert data["is_published"] is False
        assert data["created_by"] is not None

    def test_list_rules(self, db, authenticated_client, seeded_rule):
        url = reverse("rule-list-create")
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        titles = [r["title"] for r in response.data]
        assert "Minimum Stadium Capacity" in titles

    def test_retrieve_rule(self, db, authenticated_client, seeded_rule):
        url = reverse("rule-detail", kwargs={"pk": seeded_rule.pk})
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Minimum Stadium Capacity"
        assert response.data["rule_number"] == "COMP-001"

    def test_update_rule(self, db, authenticated_client, seeded_rule):
        url = reverse("rule-detail", kwargs={"pk": seeded_rule.pk})
        response = authenticated_client.patch(
            url, {"priority": Rule.Priority.RECOMMENDED}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["priority"] == Rule.Priority.RECOMMENDED

    def test_delete_rule(self, db, authenticated_client, seeded_rule):
        url = reverse("rule-detail", kwargs={"pk": seeded_rule.pk})
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_retrieve_nonexistent_rule(self, db, authenticated_client):
        url = reverse("rule-detail", kwargs={"pk": 99999})
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestRulePublishing:
    """Test rule publish/unpublish workflows."""

    def test_publish_rule(self, db, authenticated_client, seeded_rule):
        assert seeded_rule.is_published is False
        url = reverse("rule-publish", kwargs={"pk": seeded_rule.pk})
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["rule"]["is_published"] is True
        seeded_rule.refresh_from_db()
        assert seeded_rule.is_published is True
        assert seeded_rule.published_at is not None

    def test_publish_already_published_rule(
        self, db, authenticated_client, seeded_published_rule
    ):
        url = reverse("rule-publish", kwargs={"pk": seeded_published_rule.pk})
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already published" in response.data["detail"].lower()

    def test_unpublish_rule(self, db, authenticated_client, seeded_published_rule):
        url = reverse("rule-unpublish", kwargs={"pk": seeded_published_rule.pk})
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        seeded_published_rule.refresh_from_db()
        assert seeded_published_rule.is_published is False
        assert seeded_published_rule.published_at is None

    def test_unpublish_not_published_rule(self, db, authenticated_client, seeded_rule):
        url = reverse("rule-unpublish", kwargs={"pk": seeded_rule.pk})
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not currently published" in response.data["detail"].lower()

    def test_publish_nonexistent_rule(self, db, authenticated_client):
        url = reverse("rule-publish", kwargs={"pk": 99999})
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# PUBLISH STANDARDS TO LEAGUES TESTS
# ============================================================================


class TestLeagueStandards:
    """Test publishing standards to leagues."""

    def test_list_league_standards(
        self, db, authenticated_client, seeded_league_standard
    ):
        url = reverse("league-standard-list-create")
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        assert response.data[0]["rule_title"] == "Player Registration Deadline"
        assert response.data[0]["league_name"] == "Test League"

    def test_publish_standards_to_league(
        self, db, authenticated_client, seeded_published_rule, seeded_league
    ):
        url = reverse("league-standard-list-create")
        payload = {
            "rule_ids": [seeded_published_rule.pk],
            "league_ids": [seeded_league.pk],
            "notes": "Required for compliance",
        }
        response = authenticated_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["created"] != []
        # Verify it's persisted
        assert (
            LeagueStandard.objects.filter(
                rule=seeded_published_rule, league=seeded_league
            ).count()
            == 1
        )

    def test_publish_multiple_rules_to_multiple_leagues(
        self, db, authenticated_client, seeded_published_rule, seeded_league
    ):
        # Create a second league
        union = Union.objects.create(name="Union B", slug="union-b")
        league2 = League.objects.create(
            name="League B", slug="league-b", union=union, is_active=True
        )
        # Create a second published rule
        rule2 = Rule.objects.create(
            title="Kit Sponsorship Rules",
            slug="kit-sponsorship-rules",
            category=Rule.Category.MARKETING,
            priority=Rule.Priority.MANDATORY,
            description="Kit sponsorship rules description",
            version="1.0",
            is_published=True,
            published_at=timezone.now(),
        )

        url = reverse("league-standard-list-create")
        payload = {
            "rule_ids": [seeded_published_rule.pk, rule2.pk],
            "league_ids": [seeded_league.pk, league2.pk],
        }
        response = authenticated_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        # 2 rules x 2 leagues = 4 assignments
        assert len(response.data["created"]) == 4

    def test_publish_unpublished_rule_fails(
        self, db, authenticated_client, seeded_rule, seeded_league
    ):
        """Rules must be published before they can be assigned to leagues."""
        url = reverse("league-standard-list-create")
        payload = {
            "rule_ids": [seeded_rule.pk],
            "league_ids": [seeded_league.pk],
        }
        response = authenticated_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "must be published first" in response.data["detail"].lower()

    def test_publish_duplicate_standards(
        self, db, authenticated_client, seeded_league_standard
    ):
        """Publishing the same rule+league combo should not create duplicates."""
        url = reverse("league-standard-list-create")
        payload = {
            "rule_ids": [seeded_league_standard.rule_id],
            "league_ids": [seeded_league_standard.league_id],
        }
        response = authenticated_client.post(url, payload, format="json")
        # Should still succeed but indicate already exist
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
        )
        if response.status_code == status.HTTP_200_OK:
            assert response.data["already_exist"] != []

    def test_remove_league_standard(
        self, db, authenticated_client, seeded_league_standard
    ):
        url = reverse(
            "league-standard-remove", kwargs={"pk": seeded_league_standard.pk}
        )
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_list_standards_by_league(
        self, db, authenticated_client, seeded_league_standard, seeded_league
    ):
        url = reverse(
            "league-standards-by-league",
            kwargs={"league_pk": seeded_league.pk},
        )
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        assert response.data[0]["league"] == seeded_league.pk

    def test_remove_nonexistent_standard(self, db, authenticated_client):
        url = reverse("league-standard-remove", kwargs={"pk": 99999})
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_publish_standards_requires_auth(self, db, unauthenticated_client):
        url = reverse("league-standard-list-create")
        response = unauthenticated_client.post(
            url, {"rule_ids": [1], "league_ids": [1]}, format="json"
        )
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )
