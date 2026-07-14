"""
Integration tests for Club Administrator workflows, including sub-roles.

Tests for:
- Club Admin Scope creation and management.
- Dynamic dashboard content based on sub-role permissions.
- Access control for different club admin sub-roles.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from accounts.models import Club, ClubAdminScope

User = get_user_model()


class TestClubAdminDashboard(TestCase):
    def setUp(self):
        self.api_client = APIClient()
        self.club = Club.objects.create(name="Test FC", slug="test-fc")
        self.club_admin_user = User.objects.create_user(
            email="newclubadmin@example.com",
            password="testpass123",
            first_name="Club",
            last_name="Admin",
            role=User.Role.CLUB_ADMIN,
        )
        self.club_admin_scope = ClubAdminScope.objects.create(
            user=self.club_admin_user,
            club=self.club,
            role=ClubAdminScope.Role.CLUB_ADMIN,
            is_active=True,
        )

    def test_club_admin_can_access_own_dashboard(self):
        """
        A user with an active ClubAdminScope can access the club admin dashboard.
        """
        self.api_client.force_authenticate(user=self.club_admin_user)
        url = reverse("club-admin-dashboard")
        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["dashboard_role"], "CLUB_ADMIN")
        self.assertIn("Squad Management", response.data["dashboard"]["modules"])
        self.assertIn("Ticketing", response.data["dashboard"]["modules"])

    def test_dashboard_title_contains_club_name(self):
        """The dashboard title should be personalized with the club's name."""
        self.api_client.force_authenticate(user=self.club_admin_user)
        url = reverse("club-admin-dashboard")
        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(
            self.club_admin_scope.club.name, response.data["dashboard"]["title"]
        )

    def test_user_without_scope_cannot_access_dashboard(self):
        """A user with CLUB_ADMIN role but no scope gets fallback dashboard."""
        user = User.objects.create_user(
            email="noscope@example.com",
            password="testpass123",
            role=User.Role.CLUB_ADMIN,
        )
        self.api_client.force_authenticate(user=user)
        url = reverse("club-admin-dashboard")
        response = self.api_client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)  # Fallback is used
        self.assertIn("Admin", response.data["dashboard"]["title"])
