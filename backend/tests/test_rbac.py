import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from accounts.models import AuditLog
from accounts.rbac import log_role_change


@pytest.fixture
def user_model():
    return get_user_model()


def create_user(User, email, role):
    return User.objects.create_user(
        email=email,
        password="testpass123",
        first_name="Test",
        last_name="User",
        role=role,
    )


class TestRBACAuditLogging:
    def test_access_violation_creates_audit_log(self, db, user_model):
        User = user_model
        user = create_user(User, "club-admin@example.com", User.Role.CLUB_ADMIN)
        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse("fan-dashboard")
        response = client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

        audit = AuditLog.objects.filter(
            action="access_denied",
            path=url,
            status_code=403,
            actor=user,
        ).first()

        assert audit is not None
        assert audit.category == AuditLog.Category.ACCESS_VIOLATION
        assert audit.details["permission"] == "dashboard.fan"

    def test_role_change_log_entry_can_be_created(self, db, user_model):
        User = user_model
        actor = create_user(User, "admin@example.com", User.Role.SUPER_ADMIN)
        target = create_user(User, "fan@example.com", User.Role.FAN)

        audit = log_role_change(
            target_user=target,
            previous_role=User.Role.FAN,
            new_role=User.Role.CLUB_ADMIN,
            actor=actor,
            reason="role_promotion",
        )

        assert audit.category == AuditLog.Category.ROLE_CHANGE
        assert audit.action == "role_change"
        assert audit.actor == actor
        assert audit.target_user == target
        assert audit.details["previous_role"] == User.Role.FAN
        assert audit.details["new_role"] == User.Role.CLUB_ADMIN
        assert audit.details["reason"] == "role_promotion"
