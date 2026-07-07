import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User


@pytest.fixture(autouse=True)
def _prepare_test_db(db):
    call_command("migrate", verbosity=0, interactive=False)


@pytest.fixture
def super_admin_user(db):
    return User.objects.create_user(
        email="superadmin-platform@example.com",
        password="StrongPass123!",
        first_name="Platform",
        last_name="Admin",
        role=User.Role.SUPER_ADMIN,
    )


@pytest.fixture
def regular_user(db):
    return User.objects.create_user(
        email="regular-user@example.com",
        password="StrongPass123!",
        first_name="Regular",
        last_name="User",
        role=User.Role.FAN,
    )


@pytest.fixture
def super_admin_client(super_admin_user):
    client = APIClient()
    client.force_authenticate(super_admin_user)
    return client


@pytest.fixture
def regular_client(regular_user):
    client = APIClient()
    client.force_authenticate(regular_user)
    return client


def test_super_admin_can_create_announcement(super_admin_client):
    url = reverse("announcement-list-create")
    response = super_admin_client.post(
        url,
        {
            "title": "Platform maintenance",
            "body": "Scheduled maintenance tonight.",
            "audience": "ALL",
            "is_active": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["title"] == "Platform maintenance"


def test_super_admin_can_create_banner(super_admin_client):
    url = reverse("banner-list-create")
    response = super_admin_client.post(
        url,
        {
            "title": "New season launch",
            "subtitle": "Watch the first match live",
            "cta_text": "Explore",
            "cta_url": "/events",
            "is_active": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["title"] == "New season launch"


def test_super_admin_can_create_system_message(super_admin_client):
    url = reverse("system-message-list-create")
    response = super_admin_client.post(
        url,
        {
            "title": "Maintenance window",
            "body": "The platform will be unavailable for 30 minutes.",
            "severity": "info",
            "is_active": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["title"] == "Maintenance window"


def test_non_super_admin_cannot_create_feature_flag(regular_client):
    url = reverse("feature-flag-list-create")
    response = regular_client.post(
        url,
        {
            "name": "new-dashboard",
            "key": "new_dashboard",
            "enabled": True,
            "description": "Enable the new dashboard",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
