from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

# Create your tests here.
User = get_user_model()


class DashboardAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def create_user(self, email, role):
        return User.objects.create_user(
            email=email,
            phone_number=None,
            password="StrongPass123",
            first_name="Test",
            last_name="User",
            role=role,
        )

    def authenticate(self, user):
        login_response = self.client.post(
            "/api/accounts/login/",
            {
                "identifier": user.email,
                "password": "StrongPass123",
            },
            format="json",
        )

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

    def test_club_admin_can_access_club_admin_dashboard(self):
        user = self.create_user(
            "club-admin-dashboard@example.com",
            User.Role.CLUB_ADMIN,
        )
        self.authenticate(user)

        response = self.client.get("/api/dashboards/club-admin/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], User.Role.CLUB_ADMIN)
        self.assertEqual(response.data["dashboard"]["title"], "Club Admin Dashboard")

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

    def test_all_roles_can_resolve_my_dashboard(self):
        role_data = [
            (User.Role.FAN, "/api/dashboards/fan/"),
            (User.Role.CLUB_ADMIN, "/api/dashboards/club-admin/"),
            (User.Role.LEAGUE_ADMIN, "/api/dashboards/league-admin/"),
            (User.Role.UNION_ADMIN, "/api/dashboards/union-admin/"),
            (User.Role.SUPER_ADMIN, "/api/dashboards/super-admin/"),
            (User.Role.REFEREE, "/api/dashboards/referee/"),
            (User.Role.TICKETING_OFFICER, "/api/dashboards/ticketing-officer/"),
            (User.Role.SPONSOR, "/api/dashboards/sponsor/"),
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
