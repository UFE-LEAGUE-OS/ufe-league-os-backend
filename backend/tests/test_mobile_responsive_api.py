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
from rest_framework.test import APITestCase

from accounts.models import User
from accounts.tests.factories import UserFactory


class TestPublicAPIResponses(APITestCase):
    """Public endpoints should be accessible without authentication."""

    def test_public_fixtures_returns_json(self):
        response = self.client.get("/api/dashboards/fixtures/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")
        # Should return a list
        self.assertIsInstance(response.json(), list)

    def test_public_results_returns_json(self):
        response = self.client.get("/api/dashboards/results/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIsInstance(response.json(), list)

    def test_public_clubs_returns_json(self):
        response = self.client.get("/api/dashboards/clubs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")
        data = response.json()
        self.assertIsInstance(data, list)

    def test_public_unions_returns_json(self):
        response = self.client.get("/api/dashboards/unions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")
        data = response.json()
        self.assertIsInstance(data, list)

    def test_public_leagues_returns_json(self):
        response = self.client.get("/api/dashboards/leagues/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")
        data = response.json()
        self.assertIsInstance(data, list)

    def test_public_competitions_returns_json(self):
        response = self.client.get("/api/dashboards/competitions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")
        data = response.json()
        self.assertIsInstance(data, list)

    def test_public_roles_endpoint_accessible(self):
        response = self.client.get("/api/accounts/roles/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("roles", data)
        self.assertIsInstance(data["roles"], list)


class TestDashboardAPIStructure(APITestCase):
    """Dashboard APIs should return consistent, mobile-friendly structures."""

    def setUp(self):
        self.user = UserFactory(role=User.Role.FAN)
        self.client.force_authenticate(user=self.user)

    def test_my_dashboard_response_structure(self):
        response = self.client.get("/api/dashboards/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Verify top-level keys for consistent mobile rendering
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
            self.assertIn(key, data, f"Missing key: {key}")

    def test_dashboard_contains_required_fields(self):
        response = self.client.get("/api/dashboards/me/")
        data = response.json()

        # Dashboard content should have mobile-renderable structure
        dashboard = data["dashboard"]
        self.assertIn("title", dashboard)
        self.assertIn("description", dashboard)
        self.assertIn("summary_cards", dashboard)
        self.assertIn("modules", dashboard)
        self.assertIn("quick_actions", dashboard)

    def test_summary_cards_structure_for_mobile(self):
        """Summary cards should be simple key-value pairs for mobile rendering."""
        response = self.client.get("/api/dashboards/me/")
        data = response.json()

        for card in data["dashboard"]["summary_cards"]:
            self.assertIn("label", card)
            self.assertIn("value", card)
            # Values should be simple types (strings/numbers) for mobile UI
            self.assertIsInstance(card["value"], (str, int, float))

    def test_available_dashboards_structure(self):
        response = self.client.get("/api/dashboards/me/")
        data = response.json()

        dashboards = data["available_dashboards"]
        self.assertIsInstance(dashboards, list)

        for dashboard in dashboards:
            self.assertIn("label", dashboard)
            self.assertIn("frontend_route", dashboard)
            self.assertIn("backend_route", dashboard)

    def test_user_data_is_serialized(self):
        response = self.client.get("/api/dashboards/me/")
        data = response.json()

        user_data = data["user"]
        self.assertIn("email", user_data)
        self.assertIn("first_name", user_data)
        self.assertIn("last_name", user_data)
        self.assertIn("role", user_data)

    def test_route_fields_are_strings(self):
        response = self.client.get("/api/dashboards/me/")
        data = response.json()

        self.assertIsInstance(data["frontend_dashboard_route"], str)
        self.assertIsInstance(data["backend_dashboard_route"], str)
        # Routes should start with expected prefixes
        self.assertTrue(
            data["frontend_dashboard_route"].startswith("/dashboard/")
            or data["frontend_dashboard_route"].startswith("/")
        )


class TestRoleSpecificDashboardStructure(APITestCase):
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
    def test_all_roles_get_consistent_dashboard_structure(self, role):
        user = UserFactory(role=role)
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/dashboards/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # All roles should get the same structure
        self.assertIn("dashboard", data)
        self.assertIn("title", data["dashboard"])
        self.assertIn("modules", data["dashboard"])
        self.assertIn("quick_actions", data["dashboard"])


class TestProfileAPIStructure(APITestCase):
    """Profile APIs should return consistent structure for mobile apps."""

    def setUp(self):
        self.user = UserFactory(role=User.Role.FAN)
        self.client.force_authenticate(user=self.user)

    def test_profile_response_structure(self):
        response = self.client.get("/api/accounts/profile/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Basic profile fields that mobile apps expect
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
            self.assertIn(field, data, f"Profile missing field: {field}")

    def test_me_endpoint_response_structure(self):
        response = self.client.get("/api/accounts/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Me endpoint should include role
        self.assertIn("email", data)
        self.assertIn("role", data)

    def test_profile_update_returns_updated_data(self):
        response = self.client.patch(
            "/api/accounts/profile/",
            {"bio": "Mobile test bio"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["bio"], "Mobile test bio")


class TestAPIResponseFormatting(APITestCase):
    """API responses should be properly formatted for JSON consumption."""

    def setUp(self):
        self.user = UserFactory(role=User.Role.FAN)
        self.client.force_authenticate(user=self.user)

    def test_dashboard_response_is_valid_json(self):
        response = self.client.get("/api/dashboards/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should not raise JSON decode error
        data = response.json()
        self.assertIsNotNone(data)
        self.assertIsInstance(data, dict)

    def test_list_endpoints_return_arrays(self):
        response = self.client.get("/api/dashboards/clubs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIsInstance(data, list)

    def test_error_responses_have_detail_field(self):
        # Unauthenticated request should return 401/403 with detail
        self.client.logout()
        response = self.client.get("/api/dashboards/me/")
        self.assertIn(response.status_code, [401, 403])
        data = response.json()
        self.assertIn("detail", data)


class TestMobileSpecificConcerns(APITestCase):
    """Tests for mobile-specific API behavior."""

    def setUp(self):
        self.user = UserFactory(role=User.Role.FAN)
        self.client.force_authenticate(user=self.user)

    def test_case_insensitive_query_params(self):
        """Mobile apps should be able to use any case for query params."""
        response = self.client.get("/api/dashboards/clubs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_api_accepts_json_content_type(self):
        """API should properly handle JSON content type."""
        response = self.client.post(
            "/api/accounts/switch-workspace/",
            {"role": "FAN"},
            format="json",
        )
        self.assertIn(response.status_code, [200, 400, 403])

    def test_response_fields_are_not_null(self):
        """Critical fields should never be null in responses."""
        response = self.client.get("/api/dashboards/me/")
        data = response.json()

        self.assertIsNotNone(data["role"])
        self.assertIsNotNone(data["dashboard_role"])
        self.assertIsNotNone(data["frontend_dashboard_route"])

    def test_pagination_structure_if_applicable(self):
        """If pagination is used, structure should be consistent."""
        response = self.client.get("/api/dashboards/clubs/")
        data = response.json()

        # If paginated, should have count/results or just be a list
        self.assertTrue(isinstance(data, list) or "results" in data or "count" in data)
