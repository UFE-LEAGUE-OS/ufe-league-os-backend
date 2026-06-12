import os
import django

os.environ["DJANGO_SETTINGS_MODULE"] = "config.test_settings"
django.setup()

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model


User = get_user_model()


def create_user(email, role=User.Role.FAN):
    return User.objects.create_user(
        email=email, password="testpass123", first_name="Test", last_name="User", role=role
    )


def test_my_dashboard_requires_authentication(db):
    client = APIClient()
    url = reverse("my-dashboard")

    # unauthenticated should be 401
    response = client.get(url)
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


def test_fan_can_access_own_dashboard(db):
    user = create_user("fan@example.com", role=User.Role.FAN)
    client = APIClient()
    client.force_authenticate(user=user)

    url = reverse("my-dashboard")
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data.get("role") == User.Role.FAN
    assert "dashboard" in response.data


def test_non_fan_cannot_access_fan_dashboard(db):
    user = create_user("admin@example.com", role=User.Role.CLUB_ADMIN)
    client = APIClient()
    client.force_authenticate(user=user)

    url = reverse("fan-dashboard")
    response = client.get(url)

    assert response.status_code == status.HTTP_403_FORBIDDEN
