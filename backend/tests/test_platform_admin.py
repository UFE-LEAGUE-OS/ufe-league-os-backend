import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from platform_admin.models import Announcement


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


def test_anonymous_user_can_read_announcements(super_admin_user):
    Announcement.objects.create(
        title="Platform maintenance",
        body="Scheduled maintenance tonight.",
        audience=Announcement.Audience.ALL,
        is_active=True,
        created_by=super_admin_user,
    )

    client = APIClient()
    response = client.get(reverse("announcement-list"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data[0]["title"] == "Platform maintenance"


def test_public_platform_content_endpoint_returns_active_content(super_admin_user):
    Announcement.objects.create(
        title="Platform maintenance",
        body="Scheduled maintenance tonight.",
        audience=Announcement.Audience.ALL,
        is_active=True,
        created_by=super_admin_user,
    )

    client = APIClient()
    response = client.get(reverse("public-platform-content"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["announcements"][0]["title"] == "Platform maintenance"


def test_super_admin_can_create_announcement(super_admin_client):
    url = reverse("announcement-list")
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
    url = reverse("banner-list")
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
    url = reverse("system-message-list")
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


def test_super_admin_can_create_public_content(super_admin_client):
    url = reverse("public-content-list")
    response = super_admin_client.post(
        url,
        {
            "slug": "welcome-message",
            "title": "Welcome",
            "body": "Welcome to the League OS experience.",
            "content_type": "page",
            "is_published": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["slug"] == "welcome-message"


def test_super_admin_can_create_help_center_article(super_admin_client):
    url = reverse("help-center-article-list")
    response = super_admin_client.post(
        url,
        {
            "slug": "how-to-join",
            "title": "How to join",
            "summary": "A quick guide to joining the platform.",
            "body": "Follow the sign-up instructions to get started.",
            "category": "getting-started",
            "is_published": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["slug"] == "how-to-join"


def test_super_admin_can_create_broadcast(super_admin_client):
    url = reverse("broadcast-list")
    response = super_admin_client.post(
        url,
        {
            "title": "Live match reminder",
            "body": "A live match is starting soon.",
            "audience": "ALL",
            "channel": "in_app",
            "is_active": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["title"] == "Live match reminder"


def test_super_admin_can_create_notification_template(super_admin_client):
    url = reverse("notification-template-list")
    response = super_admin_client.post(
        url,
        {
            "name": "welcome-email",
            "subject": "Welcome to League OS",
            "body": "Thanks for joining.",
            "template_type": "email",
            "is_active": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["name"] == "welcome-email"


def test_non_super_admin_cannot_create_feature_flag(regular_client):
    url = reverse("feature-flag-list")
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
