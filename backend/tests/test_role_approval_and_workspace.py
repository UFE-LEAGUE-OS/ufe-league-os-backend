"""
Tests for:
1. Role Approval Workflow (dual-admin approval for sensitive roles)
2. Switch Workspace / Account API
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import RoleApproval, AuditLog

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def fan_user(db):
    return User.objects.create_user(
        email="fan@example.com",
        password="testpass123",
        first_name="Test",
        last_name="Fan",
        role=User.Role.FAN,
        is_email_verified=True,
    )


@pytest.fixture
def super_admin_1(db):
    """First super admin - can create users and request role approvals."""
    return User.objects.create_user(
        email="super1@leagueos.com",
        password="testpass123",
        first_name="Super",
        last_name="Admin One",
        role=User.Role.SUPER_ADMIN,
        is_email_verified=True,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def super_admin_2(db):
    """Second super admin - can approve/reject role requests."""
    return User.objects.create_user(
        email="super2@leagueos.com",
        password="testpass123",
        first_name="Super",
        last_name="Admin Two",
        role=User.Role.SUPER_ADMIN,
        is_email_verified=True,
        is_staff=True,
        is_superuser=True,
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


# ---------------------------------------------------------------------------
# Tests: Switch Workspace API
# ---------------------------------------------------------------------------


class TestSwitchWorkspaceAPI:
    def test_switch_workspace_requires_auth(self, api_client, db):
        """Unauthenticated users should get 401."""
        response = api_client.post(
            "/api/accounts/switch-workspace/", {"role": "SPONSOR"}, format="json"
        )
        assert response.status_code in (401, 403)

    def test_switch_to_own_role(self, api_client, fan_user):
        """A FAN should be able to switch to FAN workspace."""
        api_client.force_authenticate(user=fan_user)
        response = api_client.post(
            "/api/accounts/switch-workspace/",
            {"role": "FAN"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["role"] == "FAN"
        assert response.data["frontend_dashboard_route"] == "/dashboard/fan"

    def test_switch_to_unavailable_role(self, api_client, fan_user):
        """A FAN should NOT be able to switch to a role they don't have."""
        api_client.force_authenticate(user=fan_user)
        response = api_client.post(
            "/api/accounts/switch-workspace/",
            {"role": "SUPER_ADMIN"},
            format="json",
        )
        assert response.status_code == 400
        assert "role" in response.data

    def test_switch_to_sponsor_workspace_with_sponsor_memberships(self, api_client, db):
        """A user with sponsor memberships should be able to switch to SPONSOR."""
        user = User.objects.create_user(
            email="sponsoruser@example.com",
            password="testpass123",
            first_name="Sponsor",
            last_name="User",
            role=User.Role.FAN,
            is_email_verified=True,
            is_sponsor=True,
        )
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/accounts/switch-workspace/",
            {"role": "SPONSOR"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["role"] == "SPONSOR"
        assert response.data["frontend_dashboard_route"] == "/dashboard/sponsor"

    def test_switch_returns_available_dashboards(self, api_client, fan_user):
        """The response should include available_dashboards."""
        api_client.force_authenticate(user=fan_user)
        response = api_client.post(
            "/api/accounts/switch-workspace/",
            {"role": "FAN"},
            format="json",
        )
        assert response.status_code == 200
        assert "available_dashboards" in response.data
        assert len(response.data["available_dashboards"]) >= 1


# ---------------------------------------------------------------------------
# Tests: Role Approval Workflow
# ---------------------------------------------------------------------------


class TestRoleApprovalCreate:
    """Tests for the superadmin_create_user_view with role approval."""

    def test_create_non_sensitive_role_immediately_applied(
        self, api_client, super_admin_1
    ):
        """CLUB_ADMIN is non-sensitive and should be applied immediately."""
        api_client.force_authenticate(user=super_admin_1)
        response = api_client.post(
            "/api/accounts/superadmin/create-user/",
            {
                "email": "newclubadmin@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "first_name": "New",
                "last_name": "ClubAdmin",
                "role": "CLUB_ADMIN",
            },
            format="json",
        )
        assert response.status_code == 201
        assert "requires_approval" not in response.data
        user = User.objects.get(email="newclubadmin@example.com")
        assert user.role == User.Role.CLUB_ADMIN

    def test_create_sensitive_role_creates_approval_request(
        self, api_client, super_admin_1
    ):
        """UNION_ADMIN is sensitive and should create a PENDING approval request."""
        api_client.force_authenticate(user=super_admin_1)
        response = api_client.post(
            "/api/accounts/superadmin/create-user/",
            {
                "email": "newunionadmin@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "first_name": "New",
                "last_name": "UnionAdmin",
                "role": "UNION_ADMIN",
            },
            format="json",
        )
        assert response.status_code == 201
        assert response.data["requires_approval"] is True
        assert response.data["approval"]["status"] == "PENDING"
        assert response.data["approval"]["requested_role"] == "UNION_ADMIN"

        # User should still be FAN until approval
        user = User.objects.get(email="newunionadmin@example.com")
        assert user.role == User.Role.FAN

        # RoleApproval record should exist
        assert RoleApproval.objects.filter(
            target_user=user,
            requested_role="UNION_ADMIN",
            status=RoleApproval.Status.PENDING,
        ).exists()

    def test_create_super_admin_sensitive_creates_approval(
        self, api_client, super_admin_1
    ):
        """SUPER_ADMIN is sensitive and should create a PENDING approval request."""
        api_client.force_authenticate(user=super_admin_1)
        response = api_client.post(
            "/api/accounts/superadmin/create-user/",
            {
                "email": "newsuperadmin@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "first_name": "New",
                "last_name": "SuperAdmin",
                "role": "SUPER_ADMIN",
            },
            format="json",
        )
        assert response.status_code == 201
        assert response.data["requires_approval"] is True
        assert response.data["approval"]["status"] == "PENDING"

    def test_create_sensitive_role_logs_audit(self, api_client, super_admin_1):
        """Creating a sensitive role should log a governance audit entry."""
        api_client.force_authenticate(user=super_admin_1)
        api_client.post(
            "/api/accounts/superadmin/create-user/",
            {
                "email": "audituser@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "first_name": "Audit",
                "last_name": "User",
                "role": "UNION_ADMIN",
            },
            format="json",
        )
        assert AuditLog.objects.filter(
            category=AuditLog.Category.GOVERNANCE,
            action="role_approval_requested",
            actor=super_admin_1,
        ).exists()


class TestRoleApprovalList:
    """Tests for listing role approval requests."""

    def test_list_requires_super_admin(self, api_client, fan_user, db):
        """Only SUPER_ADMIN can list approval requests."""
        api_client.force_authenticate(user=fan_user)
        response = api_client.get("/api/accounts/role-approvals/")
        assert response.status_code == 403

    def test_list_all(self, api_client, super_admin_1, super_admin_2):
        """List all approval requests."""
        api_client.force_authenticate(user=super_admin_1)

        # Create a couple of approval requests
        target = User.objects.create_user(
            email="target1@example.com",
            password="testpass123",
            first_name="Target",
            last_name="One",
            role=User.Role.FAN,
        )
        RoleApproval.objects.create(
            target_user=target,
            requested_role="UNION_ADMIN",
            requested_by=super_admin_1,
        )

        target2 = User.objects.create_user(
            email="target2@example.com",
            password="testpass123",
            first_name="Target",
            last_name="Two",
            role=User.Role.FAN,
        )
        RoleApproval.objects.create(
            target_user=target2,
            requested_role="SUPER_ADMIN",
            requested_by=super_admin_2,
        )

        response = api_client.get("/api/accounts/role-approvals/")
        assert response.status_code == 200
        assert len(response.data) >= 2

    def test_list_filter_by_status(self, api_client, super_admin_1):
        """Filter approval requests by status."""
        api_client.force_authenticate(user=super_admin_1)

        target = User.objects.create_user(
            email="filtertarget@example.com",
            password="testpass123",
            first_name="Filter",
            last_name="Target",
            role=User.Role.FAN,
        )
        RoleApproval.objects.create(
            target_user=target,
            requested_role="UNION_ADMIN",
            requested_by=super_admin_1,
            status=RoleApproval.Status.APPROVED,
        )

        response = api_client.get("/api/accounts/role-approvals/?status=APPROVED")
        assert response.status_code == 200
        assert all(r["status"] == "APPROVED" for r in response.data)

    def test_pending_count(self, api_client, super_admin_1):
        """Pending count endpoint."""
        api_client.force_authenticate(user=super_admin_1)

        target = User.objects.create_user(
            email="pendingcount@example.com",
            password="testpass123",
            first_name="Pending",
            last_name="Count",
            role=User.Role.FAN,
        )
        RoleApproval.objects.create(
            target_user=target,
            requested_role="UNION_ADMIN",
            requested_by=super_admin_1,
        )

        response = api_client.get("/api/accounts/role-approvals/pending-count/")
        assert response.status_code == 200
        assert response.data["pending_count"] >= 1


class TestRoleApprovalReview:
    """Tests for approving/rejecting role approval requests."""

    def test_approve_by_same_admin_fails(self, api_client, super_admin_1):
        """A SUPER_ADMIN cannot approve their own request."""
        api_client.force_authenticate(user=super_admin_1)

        target = User.objects.create_user(
            email="selfapprove@example.com",
            password="testpass123",
            first_name="Self",
            last_name="Approve",
            role=User.Role.FAN,
        )
        approval = RoleApproval.objects.create(
            target_user=target,
            requested_role="UNION_ADMIN",
            requested_by=super_admin_1,
        )

        response = api_client.post(
            f"/api/accounts/role-approvals/{approval.id}/review/",
            {"action": "approve"},
            format="json",
        )
        assert response.status_code == 400
        assert "cannot approve" in response.data["detail"].lower()

    def test_approve_by_different_admin_succeeds(
        self, api_client, super_admin_1, super_admin_2
    ):
        """A different SUPER_ADMIN can approve the request."""
        api_client.force_authenticate(user=super_admin_1)

        target = User.objects.create_user(
            email="approveme@example.com",
            password="testpass123",
            first_name="Approve",
            last_name="Me",
            role=User.Role.FAN,
        )
        approval = RoleApproval.objects.create(
            target_user=target,
            requested_role="UNION_ADMIN",
            requested_by=super_admin_1,
        )

        # Switch to super_admin_2 to approve
        api_client.force_authenticate(user=super_admin_2)
        response = api_client.post(
            f"/api/accounts/role-approvals/{approval.id}/review/",
            {"action": "approve"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["approval"]["status"] == "APPROVED"

        # Check user's role was updated
        target.refresh_from_db()
        assert target.role == User.Role.UNION_ADMIN

    def test_reject_requires_reason(self, api_client, super_admin_1, super_admin_2):
        """Rejecting a request requires a rejection_reason."""
        api_client.force_authenticate(user=super_admin_1)

        target = User.objects.create_user(
            email="rejectme@example.com",
            password="testpass123",
            first_name="Reject",
            last_name="Me",
            role=User.Role.FAN,
        )
        approval = RoleApproval.objects.create(
            target_user=target,
            requested_role="UNION_ADMIN",
            requested_by=super_admin_1,
        )

        api_client.force_authenticate(user=super_admin_2)
        response = api_client.post(
            f"/api/accounts/role-approvals/{approval.id}/review/",
            {"action": "reject"},
            format="json",
        )
        assert response.status_code == 400
        assert "rejection_reason" in response.data

    def test_reject_succeeds_with_reason(
        self, api_client, super_admin_1, super_admin_2
    ):
        """Rejecting with a reason should succeed."""
        api_client.force_authenticate(user=super_admin_1)

        target = User.objects.create_user(
            email="rejectwithreason@example.com",
            password="testpass123",
            first_name="Reject",
            last_name="Reason",
            role=User.Role.FAN,
        )
        approval = RoleApproval.objects.create(
            target_user=target,
            requested_role="UNION_ADMIN",
            requested_by=super_admin_1,
        )

        api_client.force_authenticate(user=super_admin_2)
        response = api_client.post(
            f"/api/accounts/role-approvals/{approval.id}/review/",
            {"action": "reject", "rejection_reason": "Insufficient qualifications."},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["approval"]["status"] == "REJECTED"
        assert (
            response.data["approval"]["rejection_reason"]
            == "Insufficient qualifications."
        )

        # User's role should NOT have changed
        target.refresh_from_db()
        assert target.role == User.Role.FAN

    def test_approve_already_reviewed_fails(
        self, api_client, super_admin_1, super_admin_2
    ):
        """Cannot approve an already-approved request."""
        api_client.force_authenticate(user=super_admin_1)

        target = User.objects.create_user(
            email="alreadydone@example.com",
            password="testpass123",
            first_name="Already",
            last_name="Done",
            role=User.Role.FAN,
        )
        approval = RoleApproval.objects.create(
            target_user=target,
            requested_role="UNION_ADMIN",
            requested_by=super_admin_1,
            status=RoleApproval.Status.APPROVED,
        )

        api_client.force_authenticate(user=super_admin_2)
        response = api_client.post(
            f"/api/accounts/role-approvals/{approval.id}/review/",
            {"action": "approve"},
            format="json",
        )
        assert response.status_code == 400
        assert "already" in response.data["detail"].lower()

    def test_approve_logs_role_change_audit(
        self, api_client, super_admin_1, super_admin_2
    ):
        """Approving should log a role change audit entry."""
        api_client.force_authenticate(user=super_admin_1)

        target = User.objects.create_user(
            email="auditapprove@example.com",
            password="testpass123",
            first_name="Audit",
            last_name="Approve",
            role=User.Role.FAN,
        )
        approval = RoleApproval.objects.create(
            target_user=target,
            requested_role="UNION_ADMIN",
            requested_by=super_admin_1,
        )

        api_client.force_authenticate(user=super_admin_2)
        api_client.post(
            f"/api/accounts/role-approvals/{approval.id}/review/",
            {"action": "approve"},
            format="json",
        )

        # Check audit logs
        assert AuditLog.objects.filter(
            category=AuditLog.Category.ROLE_CHANGE,
            target_user=target,
        ).exists()
        assert AuditLog.objects.filter(
            category=AuditLog.Category.GOVERNANCE,
            action="role_approval_approved",
            actor=super_admin_2,
        ).exists()

    def test_reject_logs_audit(self, api_client, super_admin_1, super_admin_2):
        """Rejecting should log a governance audit entry."""
        api_client.force_authenticate(user=super_admin_1)

        target = User.objects.create_user(
            email="auditreject@example.com",
            password="testpass123",
            first_name="Audit",
            last_name="Reject",
            role=User.Role.FAN,
        )
        approval = RoleApproval.objects.create(
            target_user=target,
            requested_role="UNION_ADMIN",
            requested_by=super_admin_1,
        )

        api_client.force_authenticate(user=super_admin_2)
        api_client.post(
            f"/api/accounts/role-approvals/{approval.id}/review/",
            {"action": "reject", "rejection_reason": "Not qualified."},
            format="json",
        )

        assert AuditLog.objects.filter(
            category=AuditLog.Category.GOVERNANCE,
            action="role_approval_rejected",
            actor=super_admin_2,
        ).exists()

    def test_review_nonexistent_request(self, api_client, super_admin_1):
        """Reviewing a non-existent request should return 404."""
        api_client.force_authenticate(user=super_admin_1)
        response = api_client.post(
            "/api/accounts/role-approvals/99999/review/",
            {"action": "approve"},
            format="json",
        )
        assert response.status_code == 404
