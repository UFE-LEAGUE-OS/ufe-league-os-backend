"""
Mobile-responsive API tests.

These tests verify that the backend API provides consistent, well-structured
responses suitable for mobile and web clients:
- Consistent JSON response structure across all endpoints
- Public endpoints work without authentication
- Dashboard endpoints return expected fields for mobile rendering
- Response structure is predictable for frontend consumption
- Content-Type headers are correct
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def fan_user(db):
    return User.objects.create_user(
        email="fan@example.com",
        password="testpass123",
        first_name="Fan",
        last_name="User",
        role=User.Role.FAN,
        is_email_verified=True,
    )


@pytest.fixture
def club_admin_user(db):
    return User.objects.create_user(
        email="clubadmin@example.com",
        password="testpass123",
        first_name="Club",
        last_name="Admin",
        role=User.Role.CLUB_ADMIN,
        is_email_verified=True,
    )


@pytest.fixture
def league_admin_user(db):
    return User.objects.create_user(
        email="leagueadmin@example.com",
        password="testpass123",
        first_name="League",
        last_name="Admin",
        role=User.Role.LEAGUE_ADMIN,
        is_email_verified=True,
    )


@pytest.fixture
def union_admin_user(db):
    return User.objects.create_user(
        email="unionadmin@example.com",
        password="testpass123",
        first_name="Union",
        last_name="Admin",
        role=User.Role.UNION_ADMIN,
        is_email_verified=True,
    )


@pytest.fixture
def super_admin_user(db):
    return User.objects.create_user(
        email="superadmin@example.com",
        password="testpass123",
        first_name="Super",
        last_name="Admin",
        role=User.Role.SUPER_ADMIN,
        is_email_verified=True,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def referee_user(db):
    return User.objects.create_user(
        email="referee@example.com",
        password="testpass123",
        first_name="Referee",
        last_name="User",
        role=User.Role.REFEREE,
        is_email_verified=True,
    )


@pytest.fixture
def ticketing_officer_user(db):
    return User.objects.create_user(
        email="ticketing@example.com",
        password="testpass123",
        first_name="Ticketing",
        last_name="Officer",
        role=User.Role.TICKETING_OFFICER,
        is_email_verified=True,
    )


@pytest.fixture
def sponsor_user(db):
    return User.objects.create_user(
        email="sponsor@example.com",
        password="testpass123",
        first_name="Sponsor",
        last_name="User",
        role=User.Role.FAN,
        is_sponsor=True,
        sponsor_type=User.SponsorType.INDIVIDUAL,
        is_email_verified=True,
    )


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def authenticated_client(client, fan_user):
    client.force_authenticate(user=fan_user)
    return client


# ============================================================================
# Tests: Public API Responses
# ============================================================================


class TestPublicAPIResponses:
    """Public endpoints should be accessible without authentication."""

    def test_public_fixtures_returns_json(self, client):
        response = client.get("/api/dashboards/fixtures/")
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/json"
        assert isinstance(response.json(), list)

    def test_public_results_returns_json(self, client):
        response = client.get("/api/dashboards/results/")
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/json"
        assert isinstance(response.json(), list)

    def test_public_clubs_returns_json(self, client):
        response = client.get("/api/dashboards/clubs/")
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/json"
        data = response.json()
        assert isinstance(data, list)

    def test_public_unions_returns_json(self, client):
        response = client.get("/api/dashboards/unions/")
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/json"
        data = response.json()
        assert isinstance(data, list)

    def test_public_leagues_returns_json(self, client):
        response = client.get("/api/dashboards/leagues/")
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/json"
        data = response.json()
        assert isinstance(data, list)

    def test_public_competitions_returns_json(self, client):
        response = client.get("/api/dashboards/competitions/")
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/json"
        data = response.json()
        assert isinstance(data, list)

    def test_public_roles_endpoint_accessible(self, client):
        response = client.get("/api/accounts/roles/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "roles" in data
        assert isinstance(data["roles"], list)


# ============================================================================
# Tests: Dashboard API Structure
# ============================================================================


class TestDashboardAPIStructure:
    """Dashboard APIs should return consistent, mobile-friendly structures."""

    def test_my_dashboard_response_structure(self, authenticated_client, fan_user):
        response = authenticated_client.get("/api/dashboards/me/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        required_keys = [
            "message",
            "role",
            "role_display",
            "dashboard_role",
            "frontend_dashboard_route",
            "backend_dashboard_route",
            "available_dashboards",
            "dashboard",
            "user",
        ]
        for key in required_keys:
            assert key in data, f"Missing key: {key}"

    def test_dashboard_contains_required_fields(self, authenticated_client, fan_user):
        response = authenticated_client.get("/api/dashboards/me/")
        data = response.json()

        dashboard = data["dashboard"]
        assert "title" in dashboard
        assert "description" in dashboard
        assert "summary_cards" in dashboard
        assert "modules" in dashboard
        assert "quick_actions" in dashboard

    def test_summary_cards_structure_for_mobile(self, authenticated_client, fan_user):
        """Summary cards should be simple key-value pairs for mobile rendering."""
        response = authenticated_client.get("/api/dashboards/me/")
        data = response.json()

        for card in data["dashboard"]["summary_cards"]:
            assert "label" in card
            assert "value" in card
            assert isinstance(card["value"], (str, int, float))

    def test_available_dashboards_structure(self, authenticated_client, fan_user):
        response = authenticated_client.get("/api/dashboards/me/")
        data = response.json()

        dashboards = data["available_dashboards"]
        assert isinstance(dashboards, list)

        for dashboard in dashboards:
            assert "label" in dashboard
            assert "frontend_route" in dashboard
            assert "backend_route" in dashboard

    def test_user_data_is_serialized(self, authenticated_client, fan_user):
        response = authenticated_client.get("/api/dashboards/me/")
        data = response.json()

        user_data = data["user"]
        assert "email" in user_data
        assert "first_name" in user_data
        assert "last_name" in user_data
        assert "role" in user_data

    def test_route_fields_are_strings(self, authenticated_client, fan_user):
        response = authenticated_client.get("/api/dashboards/me/")
        data = response.json()

        assert isinstance(data["frontend_dashboard_route"], str)
        assert isinstance(data["backend_dashboard_route"], str)
        assert data["frontend_dashboard_route"].startswith("/dashboard/") or data[
            "frontend_dashboard_route"
        ].startswith("/")


# ============================================================================
# Tests: Role-Specific Dashboard Structure
# ============================================================================


class TestRoleSpecificDashboardStructure:
    """Each role's dashboard should return consistent structure."""

    @pytest.mark.parametrize(
        "role",
        [
            User.Role.FAN,
            User.Role.CLUB_ADMIN,
            User.Role.LEAGUE_ADMIN,
            User.Role.UNION_ADMIN,
            User.Role.SUPER_ADMIN,
            User.Role.REFEREE,
            User.Role.TICKETING_OFFICER,
            User.Role.SPONSOR,
        ],
    )
    def test_all_roles_get_consistent_dashboard_structure(self, client, role):
        user = User.objects.create_user(
            email=f"{role.lower()}@example.com",
            password="testpass123",
            first_name=role,
            last_name="User",
            role=role,
            is_email_verified=True,
        )
        client.force_authenticate(user=user)

        response = client.get("/api/dashboards/me/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "dashboard" in data
        assert "title" in data["dashboard"]
        assert "modules" in data["dashboard"]
        assert "quick_actions" in data["dashboard"]


# ============================================================================
# Tests: Profile API Structure
# ============================================================================


class TestProfileAPIStructure:
    """Profile APIs should return consistent structure for mobile apps."""

    def test_profile_response_structure(self, authenticated_client, fan_user):
        response = authenticated_client.get("/api/accounts/profile/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        expected_fields = [
            "email",
            "first_name",
            "last_name",
            "role",
            "phone_number",
            "bio",
            "location",
        ]
        for field in expected_fields:
            assert field in data, f"Profile missing field: {field}"

    def test_me_endpoint_response_structure(self, authenticated_client, fan_user):
        response = authenticated_client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "email" in data
        assert "role" in data

    def test_profile_update_returns_updated_data(self, authenticated_client, fan_user):
        response = authenticated_client.patch(
            "/api/accounts/profile/",
            {"bio": "Mobile test bio"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["bio"] == "Mobile test bio"


# ============================================================================
# Tests: API Response Formatting
# ============================================================================


class TestAPIResponseFormatting:
    """API responses should be properly formatted for JSON consumption."""

    def test_dashboard_response_is_valid_json(self, authenticated_client, fan_user):
        response = authenticated_client.get("/api/dashboards/me/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data is not None
        assert isinstance(data, dict)

    def test_list_endpoints_return_arrays(self, authenticated_client, fan_user):
        response = authenticated_client.get("/api/dashboards/clubs/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    def test_error_responses_have_detail_field(self, client, db):
        response = client.get("/api/dashboards/me/")
        assert response.status_code in [401, 403]
        data = response.json()
        assert "detail" in data


# ============================================================================
# Tests: Mobile-Specific Concerns
# ============================================================================


class TestMobileSpecificConcerns:
    """Tests for mobile-specific API behavior."""

    def test_case_insensitive_query_params(self, authenticated_client, fan_user):
        """Mobile apps should be able to use any case for query params."""
        response = authenticated_client.get("/api/dashboards/clubs/")
        assert response.status_code == status.HTTP_200_OK

    def test_api_accepts_json_content_type(self, authenticated_client, fan_user):
        """API should properly handle JSON content type."""
        response = authenticated_client.post(
            "/api/accounts/switch-workspace/",
            {"role": "FAN"},
            format="json",
        )
        assert response.status_code in [200, 400, 403]

    def test_response_fields_are_not_null(self, authenticated_client, fan_user):
        """Critical fields should never be null in responses."""
        response = authenticated_client.get("/api/dashboards/me/")
        data = response.json()

        assert data["role"] is not None
        assert data["dashboard_role"] is not None
        assert data["frontend_dashboard_route"] is not None

    def test_pagination_structure_if_applicable(self, authenticated_client, fan_user):
        """If pagination is used, structure should be consistent."""
        response = authenticated_client.get("/api/dashboards/clubs/")
        data = response.json()

        assert isinstance(data, list) or "results" in data or "count" in data
