import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model


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
