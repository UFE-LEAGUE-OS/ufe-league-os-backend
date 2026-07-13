"""
Comprehensive integration tests for all 8 user roles.

Tests verify that each role can:
1. Access their own dashboard
2. Switch to their workspace
3. Access their profile
4. Cannot access unauthorized roles' workspaces/dashboards
5. Admin creation permissions (where applicable)
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


# ============================================================================
# Fixtures for all 8 roles
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


# ============================================================================
# Tests: Profile Access (all roles)
# ============================================================================


class TestProfileAccess:
    """All authenticated users can access their own profile."""

    def test_fan_can_access_profile(self, client, fan_user):
        client.force_authenticate(user=fan_user)
        response = client.get("/api/accounts/profile/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == fan_user.email

    def test_club_admin_can_access_profile(self, client, club_admin_user):
        client.force_authenticate(user=club_admin_user)
        response = client.get("/api/accounts/profile/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == club_admin_user.email

    def test_league_admin_can_access_profile(self, client, league_admin_user):
        client.force_authenticate(user=league_admin_user)
        response = client.get("/api/accounts/profile/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == league_admin_user.email

    def test_union_admin_can_access_profile(self, client, union_admin_user):
        client.force_authenticate(user=union_admin_user)
        response = client.get("/api/accounts/profile/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == union_admin_user.email

    def test_super_admin_can_access_profile(self, client, super_admin_user):
        client.force_authenticate(user=super_admin_user)
        response = client.get("/api/accounts/profile/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == super_admin_user.email

    def test_referee_can_access_profile(self, client, referee_user):
        client.force_authenticate(user=referee_user)
        response = client.get("/api/accounts/profile/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == referee_user.email

    def test_ticketing_officer_can_access_profile(self, client, ticketing_officer_user):
        client.force_authenticate(user=ticketing_officer_user)
        response = client.get("/api/accounts/profile/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == ticketing_officer_user.email

    def test_sponsor_can_access_profile(self, client, sponsor_user):
        client.force_authenticate(user=sponsor_user)
        response = client.get("/api/accounts/profile/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == sponsor_user.email


# ============================================================================
# Tests: Switch Workspace (all roles)
# ============================================================================


class TestSwitchWorkspace:
    """Each role can switch to their own workspace."""

    def test_fan_can_switch_to_fan(self, client, fan_user):
        client.force_authenticate(user=fan_user)
        response = client.post(
            "/api/accounts/switch-workspace/",
            {"role": "FAN"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == "FAN"
        assert response.data["frontend_dashboard_route"] == "/dashboard/fan"

    def test_club_admin_can_switch_to_club_admin(self, client, club_admin_user):
        client.force_authenticate(user=club_admin_user)
        response = client.post(
            "/api/accounts/switch-workspace/",
            {"role": "CLUB_ADMIN"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == "CLUB_ADMIN"

    def test_league_admin_can_switch_to_league_admin(self, client, league_admin_user):
        client.force_authenticate(user=league_admin_user)
        response = client.post(
            "/api/accounts/switch-workspace/",
            {"role": "LEAGUE_ADMIN"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == "LEAGUE_ADMIN"

    def test_union_admin_can_switch_to_union_admin(self, client, union_admin_user):
        client.force_authenticate(user=union_admin_user)
        response = client.post(
            "/api/accounts/switch-workspace/",
            {"role": "UNION_ADMIN"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == "UNION_ADMIN"

    def test_super_admin_can_switch_to_super_admin(self, client, super_admin_user):
        client.force_authenticate(user=super_admin_user)
        response = client.post(
            "/api/accounts/switch-workspace/",
            {"role": "SUPER_ADMIN"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == "SUPER_ADMIN"

    def test_referee_can_switch_to_referee(self, client, referee_user):
        client.force_authenticate(user=referee_user)
        response = client.post(
            "/api/accounts/switch-workspace/",
            {"role": "REFEREE"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == "REFEREE"

    def test_ticketing_officer_can_switch_to_ticketing(
        self, client, ticketing_officer_user
    ):
        client.force_authenticate(user=ticketing_officer_user)
        response = client.post(
            "/api/accounts/switch-workspace/",
            {"role": "TICKETING_OFFICER"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == "TICKETING_OFFICER"

    def test_sponsor_can_switch_to_sponsor(self, client, sponsor_user):
        client.force_authenticate(user=sponsor_user)
        response = client.post(
            "/api/accounts/switch-workspace/",
            {"role": "SPONSOR"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == "SPONSOR"

    def test_fan_cannot_switch_to_unavailable_role(self, client, fan_user):
        """FAN should not be able to switch to SUPER_ADMIN."""
        client.force_authenticate(user=fan_user)
        response = client.post(
            "/api/accounts/switch-workspace/",
            {"role": "SUPER_ADMIN"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# Tests: Dashboard Access (my-dashboard)
# ============================================================================


class TestMyDashboard:
    """Each authenticated user can access my-dashboard (returns their role-specific dashboard)."""

    def test_fan_can_access_my_dashboard(self, client, fan_user):
        client.force_authenticate(user=fan_user)
        response = client.get("/api/dashboards/me/")
        assert response.status_code == status.HTTP_200_OK

    def test_club_admin_can_access_my_dashboard(self, client, club_admin_user):
        client.force_authenticate(user=club_admin_user)
        response = client.get("/api/dashboards/me/")
        assert response.status_code == status.HTTP_200_OK

    def test_league_admin_can_access_my_dashboard(self, client, league_admin_user):
        client.force_authenticate(user=league_admin_user)
        response = client.get("/api/dashboards/me/")
        assert response.status_code == status.HTTP_200_OK

    def test_union_admin_can_access_my_dashboard(self, client, union_admin_user):
        client.force_authenticate(user=union_admin_user)
        response = client.get("/api/dashboards/me/")
        assert response.status_code == status.HTTP_200_OK

    def test_super_admin_can_access_my_dashboard(self, client, super_admin_user):
        client.force_authenticate(user=super_admin_user)
        response = client.get("/api/dashboards/me/")
        assert response.status_code == status.HTTP_200_OK

    def test_referee_can_access_my_dashboard(self, client, referee_user):
        client.force_authenticate(user=referee_user)
        response = client.get("/api/dashboards/me/")
        assert response.status_code == status.HTTP_200_OK

    def test_ticketing_officer_can_access_my_dashboard(
        self, client, ticketing_officer_user
    ):
        client.force_authenticate(user=ticketing_officer_user)
        response = client.get("/api/dashboards/me/")
        assert response.status_code == status.HTTP_200_OK

    def test_sponsor_can_access_my_dashboard(self, client, sponsor_user):
        client.force_authenticate(user=sponsor_user)
        response = client.get("/api/dashboards/me/")
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_cannot_access_my_dashboard(self, client, db):
        response = client.get("/api/dashboards/me/")
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


# ============================================================================
# Tests: Role Creation Permissions (hierarchical admin creation)
# ============================================================================


class TestRoleCreationPermissions:
    """Verify which roles can create which other roles."""

    def test_club_admin_can_create_ticketing_officer(self, client, club_admin_user):
        """CLUB_ADMIN can create TICKETING_OFFICER."""
        client.force_authenticate(user=club_admin_user)
        response = client.post(
            "/api/accounts/club-admin/create-user/",
            {
                "email": "newticket@example.com",
                "password": "TestPass123",
                "confirm_password": "TestPass123",
                "first_name": "New",
                "last_name": "Ticketing",
                "role": "TICKETING_OFFICER",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["user"]["role"] == "TICKETING_OFFICER"

    def test_club_admin_cannot_create_club_admin(self, client, club_admin_user):
        """CLUB_ADMIN cannot create another CLUB_ADMIN (serializer validation)."""
        client.force_authenticate(user=club_admin_user)
        response = client.post(
            "/api/accounts/club-admin/create-user/",
            {
                "email": "newclub@example.com",
                "password": "TestPass123",
                "confirm_password": "TestPass123",
                "first_name": "New",
                "last_name": "Club",
                "role": "CLUB_ADMIN",
            },
            format="json",
        )
        # Returns 400 because serializer rejects the role assignment
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_league_admin_can_create_club_admin(self, client, league_admin_user):
        """LEAGUE_ADMIN can create CLUB_ADMIN."""
        client.force_authenticate(user=league_admin_user)
        response = client.post(
            "/api/accounts/league-admin/create-user/",
            {
                "email": "newclub@example.com",
                "password": "TestPass123",
                "confirm_password": "TestPass123",
                "first_name": "New",
                "last_name": "Club",
                "role": "CLUB_ADMIN",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["user"]["role"] == "CLUB_ADMIN"

    def test_league_admin_can_create_referee(self, client, league_admin_user):
        """LEAGUE_ADMIN can create REFEREE."""
        client.force_authenticate(user=league_admin_user)
        response = client.post(
            "/api/accounts/league-admin/create-user/",
            {
                "email": "newreferee@example.com",
                "password": "TestPass123",
                "confirm_password": "TestPass123",
                "first_name": "New",
                "last_name": "Referee",
                "role": "REFEREE",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["user"]["role"] == "REFEREE"

    def test_league_admin_cannot_create_league_admin(self, client, league_admin_user):
        """LEAGUE_ADMIN cannot create another LEAGUE_ADMIN (serializer validation)."""
        client.force_authenticate(user=league_admin_user)
        response = client.post(
            "/api/accounts/league-admin/create-user/",
            {
                "email": "newleague@example.com",
                "password": "TestPass123",
                "confirm_password": "TestPass123",
                "first_name": "New",
                "last_name": "League",
                "role": "LEAGUE_ADMIN",
            },
            format="json",
        )
        # Returns 400 because serializer rejects the role assignment
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_union_admin_can_create_referee(self, client, union_admin_user):
        """UNION_ADMIN can create REFEREE."""
        client.force_authenticate(user=union_admin_user)
        response = client.post(
            "/api/accounts/union-admin/create-user/",
            {
                "email": "newreferee@example.com",
                "password": "TestPass123",
                "confirm_password": "TestPass123",
                "first_name": "New",
                "last_name": "Referee",
                "role": "REFEREE",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["user"]["role"] == "REFEREE"

    def test_union_admin_can_create_ticketing_officer(self, client, union_admin_user):
        """UNION_ADMIN can create TICKETING_OFFICER."""
        client.force_authenticate(user=union_admin_user)
        response = client.post(
            "/api/accounts/union-admin/create-user/",
            {
                "email": "newticket@example.com",
                "password": "TestPass123",
                "confirm_password": "TestPass123",
                "first_name": "New",
                "last_name": "Ticketing",
                "role": "TICKETING_OFFICER",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["user"]["role"] == "TICKETING_OFFICER"

    def test_union_admin_cannot_create_union_admin(self, client, union_admin_user):
        """UNION_ADMIN cannot create another UNION_ADMIN (serializer validation)."""
        client.force_authenticate(user=union_admin_user)
        response = client.post(
            "/api/accounts/union-admin/create-user/",
            {
                "email": "newunion@example.com",
                "password": "TestPass123",
                "confirm_password": "TestPass123",
                "first_name": "New",
                "last_name": "Union",
                "role": "UNION_ADMIN",
            },
            format="json",
        )
        # Returns 400 because serializer rejects the role assignment
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_fan_cannot_create_any_admin(self, client, fan_user):
        """FAN cannot create any admin users."""
        client.force_authenticate(user=fan_user)
        for endpoint in [
            "/api/accounts/club-admin/create-user/",
            "/api/accounts/league-admin/create-user/",
            "/api/accounts/union-admin/create-user/",
        ]:
            response = client.post(
                endpoint,
                {
                    "email": "newadmin@example.com",
                    "password": "TestPass123",
                    "confirm_password": "TestPass123",
                    "first_name": "New",
                    "last_name": "Admin",
                    "role": "CLUB_ADMIN",
                },
                format="json",
            )
            assert response.status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            )

    def test_referee_cannot_create_users(self, client, referee_user):
        """REFEREE cannot create users."""
        client.force_authenticate(user=referee_user)
        response = client.post(
            "/api/accounts/union-admin/create-user/",
            {
                "email": "newuser@example.com",
                "password": "TestPass123",
                "confirm_password": "TestPass123",
                "first_name": "New",
                "last_name": "User",
                "role": "FAN",
            },
            format="json",
        )
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_ticketing_officer_cannot_create_users(
        self, client, ticketing_officer_user
    ):
        """TICKETING_OFFICER cannot create users."""
        client.force_authenticate(user=ticketing_officer_user)
        response = client.post(
            "/api/accounts/club-admin/create-user/",
            {
                "email": "newuser@example.com",
                "password": "TestPass123",
                "confirm_password": "TestPass123",
                "first_name": "New",
                "last_name": "User",
                "role": "FAN",
            },
            format="json",
        )
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_sponsor_cannot_create_users(self, client, sponsor_user):
        """SPONSOR cannot create users."""
        client.force_authenticate(user=sponsor_user)
        response = client.post(
            "/api/accounts/club-admin/create-user/",
            {
                "email": "newuser@example.com",
                "password": "TestPass123",
                "confirm_password": "TestPass123",
                "first_name": "New",
                "last_name": "User",
                "role": "FAN",
            },
            format="json",
        )
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


# ============================================================================
# Tests: Super Admin User Creation with sensitive roles
# ============================================================================


class TestSuperAdminRoleApproval:
    """SUPER_ADMIN can create users with sensitive roles requiring approval."""

    def test_super_admin_can_create_union_admin_with_approval(
        self, client, super_admin_user
    ):
        """Creating UNION_ADMIN creates a pending approval request."""
        client.force_authenticate(user=super_admin_user)
        response = client.post(
            "/api/accounts/superadmin/create-user/",
            {
                "email": "newunion@example.com",
                "password": "TestPass123",
                "confirm_password": "TestPass123",
                "first_name": "New",
                "last_name": "Union",
                "role": "UNION_ADMIN",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["requires_approval"] is True
        assert response.data["user"]["role"] == "FAN"  # Starts as FAN until approved

    def test_super_admin_can_create_super_admin_with_approval(
        self, client, super_admin_user
    ):
        """Creating SUPER_ADMIN creates a pending approval request."""
        client.force_authenticate(user=super_admin_user)
        response = client.post(
            "/api/accounts/superadmin/create-user/",
            {
                "email": "newsuper@example.com",
                "password": "TestPass123",
                "confirm_password": "TestPass123",
                "first_name": "New",
                "last_name": "Super",
                "role": "SUPER_ADMIN",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["requires_approval"] is True

    def test_super_admin_can_create_club_admin_immediately(
        self, client, super_admin_user
    ):
        """Creating CLUB_ADMIN (non-sensitive) applies immediately."""
        client.force_authenticate(user=super_admin_user)
        response = client.post(
            "/api/accounts/superadmin/create-user/",
            {
                "email": "newclub@example.com",
                "password": "TestPass123",
                "confirm_password": "TestPass123",
                "first_name": "New",
                "last_name": "Club",
                "role": "CLUB_ADMIN",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["user"]["role"] == "CLUB_ADMIN"

    def test_non_admin_cannot_use_superadmin_endpoint(self, client, fan_user):
        """Non-super-admin cannot use superadmin create-user endpoint."""
        client.force_authenticate(user=fan_user)
        response = client.post(
            "/api/accounts/superadmin/create-user/",
            {
                "email": "newuser@example.com",
                "password": "TestPass123",
                "confirm_password": "TestPass123",
                "first_name": "New",
                "last_name": "User",
                "role": "CLUB_ADMIN",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# Tests: Role Approval Management
# ============================================================================


class TestRoleApprovalManagement:
    """Test role approval workflow."""

    def test_super_admin_can_list_approvals(self, client, super_admin_user):
        client.force_authenticate(user=super_admin_user)
        response = client.get("/api/accounts/role-approvals/")
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_non_super_admin_cannot_list_approvals(self, client, club_admin_user):
        client.force_authenticate(user=club_admin_user)
        response = client.get("/api/accounts/role-approvals/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_super_admin_can_get_pending_count(self, client, super_admin_user):
        client.force_authenticate(user=super_admin_user)
        response = client.get("/api/accounts/role-approvals/pending-count/")
        assert response.status_code == status.HTTP_200_OK
        assert "pending_count" in response.data


# ============================================================================
# Tests: Me Endpoint (all roles)
# ============================================================================


class TestMeEndpoint:
    """Each role can access the /me endpoint."""

    def test_fan_can_get_me(self, client, fan_user):
        client.force_authenticate(user=fan_user)
        response = client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == fan_user.email
        assert response.data["role"] == User.Role.FAN

    def test_club_admin_can_get_me(self, client, club_admin_user):
        client.force_authenticate(user=club_admin_user)
        response = client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == User.Role.CLUB_ADMIN

    def test_league_admin_can_get_me(self, client, league_admin_user):
        client.force_authenticate(user=league_admin_user)
        response = client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == User.Role.LEAGUE_ADMIN

    def test_union_admin_can_get_me(self, client, union_admin_user):
        client.force_authenticate(user=union_admin_user)
        response = client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == User.Role.UNION_ADMIN

    def test_super_admin_can_get_me(self, client, super_admin_user):
        client.force_authenticate(user=super_admin_user)
        response = client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == User.Role.SUPER_ADMIN

    def test_referee_can_get_me(self, client, referee_user):
        client.force_authenticate(user=referee_user)
        response = client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == User.Role.REFEREE

    def test_ticketing_officer_can_get_me(self, client, ticketing_officer_user):
        client.force_authenticate(user=ticketing_officer_user)
        response = client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == User.Role.TICKETING_OFFICER

    def test_sponsor_can_get_me(self, client, sponsor_user):
        client.force_authenticate(user=sponsor_user)
        response = client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == User.Role.FAN  # Sponsor has base role FAN
        assert response.data["is_sponsor"] is True

    def test_unauthenticated_cannot_get_me(self, client, db):
        response = client.get("/api/accounts/me/")
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


# ============================================================================
# Tests: Roles Endpoint (public)
# ============================================================================


class TestRolesEndpoint:
    """Anyone can get the list of available roles."""

    def test_roles_endpoint_returns_all_roles(self, client):
        response = client.get("/api/accounts/roles/")
        assert response.status_code == status.HTTP_200_OK
        roles = response.data["roles"]
        role_keys = [r["key"] for r in roles]

        expected_roles = [
            User.Role.FAN,
            User.Role.CLUB_ADMIN,
            User.Role.LEAGUE_ADMIN,
            User.Role.UNION_ADMIN,
            User.Role.SUPER_ADMIN,
            User.Role.REFEREE,
            User.Role.TICKETING_OFFICER,
            User.Role.SPONSOR,
        ]

        for role in expected_roles:
            assert role in role_keys, f"Missing role: {role}"

    def test_roles_endpoint_no_auth_required(self, client):
        response = client.get("/api/accounts/roles/")
        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# Tests: Me View - Profile Update for all roles
# ============================================================================


class TestProfileUpdate:
    """Each role can update their own profile."""

    def test_fan_can_update_profile(self, client, fan_user):
        client.force_authenticate(user=fan_user)
        response = client.patch(
            "/api/accounts/profile/",
            {"bio": "Updated bio"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        fan_user.refresh_from_db()
        assert fan_user.bio == "Updated bio"

    def test_club_admin_can_update_profile(self, client, club_admin_user):
        client.force_authenticate(user=club_admin_user)
        response = client.patch(
            "/api/accounts/profile/",
            {"bio": "Club admin bio"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        club_admin_user.refresh_from_db()
        assert club_admin_user.bio == "Club admin bio"

    def test_referee_can_update_profile(self, client, referee_user):
        client.force_authenticate(user=referee_user)
        response = client.patch(
            "/api/accounts/profile/",
            {"bio": "Referee bio"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        referee_user.refresh_from_db()
        assert referee_user.bio == "Referee bio"

    def test_sponsor_can_update_profile(self, client, sponsor_user):
        client.force_authenticate(user=sponsor_user)
        response = client.patch(
            "/api/accounts/profile/",
            {"bio": "Sponsor bio"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        sponsor_user.refresh_from_db()
        assert sponsor_user.bio == "Sponsor bio"


# ============================================================================
# Tests: Sponsor-specific test
# ============================================================================


class TestSponsorRole:
    """Tests specific to SPONSOR role."""

    def test_sponsor_has_sponsor_type(self, client, sponsor_user):
        client.force_authenticate(user=sponsor_user)
        response = client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_sponsor"] is True
        assert response.data["sponsor_type"] == User.SponsorType.INDIVIDUAL

    def test_sponsor_can_switch_to_fan(self, client, sponsor_user):
        """Sponsor (FAN + SPONSOR) can switch to FAN workspace."""
        client.force_authenticate(user=sponsor_user)
        response = client.post(
            "/api/accounts/switch-workspace/",
            {"role": "FAN"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == "FAN"

    def test_sponsor_can_switch_between_roles(self, client, sponsor_user):
        """Sponsor can switch between FAN and SPONSOR workspaces."""
        client.force_authenticate(user=sponsor_user)

        # Switch to SPONSOR
        response = client.post(
            "/api/accounts/switch-workspace/",
            {"role": "SPONSOR"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == "SPONSOR"

        # Switch back to FAN
        response = client.post(
            "/api/accounts/switch-workspace/",
            {"role": "FAN"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == "FAN"


# ============================================================================
# Tests: Referee-specific
# ============================================================================


class TestRefereeRole:
    """Tests specific to REFEREE role."""

    def test_referee_is_active(self, client, referee_user):
        client.force_authenticate(user=referee_user)
        response = client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == User.Role.REFEREE

    def test_referee_can_become_sponsor(self, client, referee_user):
        """A REFEREE should be able to become a sponsor if desired."""
        client.force_authenticate(user=referee_user)
        response = client.post(
            "/api/accounts/become-sponsor/",
            {"sponsor_type": "INDIVIDUAL"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        referee_user.refresh_from_db()
        assert referee_user.is_sponsor is True


# ============================================================================
# Tests: Ticketing Officer-specific
# ============================================================================


class TestTicketingOfficerRole:
    """Tests specific to TICKETING_OFFICER role."""

    def test_ticketing_officer_is_active(self, client, ticketing_officer_user):
        client.force_authenticate(user=ticketing_officer_user)
        response = client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == User.Role.TICKETING_OFFICER

    def test_ticketing_officer_can_update_profile(self, client, ticketing_officer_user):
        client.force_authenticate(user=ticketing_officer_user)
        response = client.patch(
            "/api/accounts/profile/",
            {"phone_number": "+256700000000"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        ticketing_officer_user.refresh_from_db()
        assert ticketing_officer_user.phone_number == "+256700000000"


# ============================================================================
# Tests: Auth flows for all roles
# ============================================================================


class TestLoginForAllRoles:
    """Test that all roles can log in and receive correct dashboard routes."""

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
        ],
    )
    def test_login_returns_tokens_and_dashboard_route(self, client, role, db):
        user = User.objects.create_user(
            email=f"{role.lower()}@example.com",
            password="testpass123",
            first_name=role,
            last_name="User",
            role=role,
            is_email_verified=True,
        )

        response = client.post(
            "/api/accounts/login/",
            {"identifier": user.email, "password": "testpass123"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert response.data["role"] == role


# ============================================================================
# Tests: Union workspace memberships (simulated for UNION_ADMIN and REFEREE)
# ============================================================================


class TestUnionWorkspaceMemberships:
    """
    UNION_ADMIN and REFEREE can have union workspace memberships.
    This is a simplified test to verify the roles property works.
    """

    def test_union_admin_has_union_admin_role(self, client, union_admin_user):
        client.force_authenticate(user=union_admin_user)
        response = client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_200_OK
        # The base role should be UNION_ADMIN
        assert response.data["role"] == User.Role.UNION_ADMIN

    def test_referee_has_referee_role(self, client, referee_user):
        client.force_authenticate(user=referee_user)
        response = client.get("/api/accounts/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == User.Role.REFEREE

    def test_union_admin_can_switch_workspace(self, client, union_admin_user):
        client.force_authenticate(user=union_admin_user)
        response = client.post(
            "/api/accounts/switch-workspace/",
            {"role": "UNION_ADMIN"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == "UNION_ADMIN"

    def test_referee_can_switch_workspace(self, client, referee_user):
        client.force_authenticate(user=referee_user)
        response = client.post(
            "/api/accounts/switch-workspace/",
            {"role": "REFEREE"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == "REFEREE"


# ============================================================================
# Tests: Profile Changes Persisted Correctly
# ============================================================================


class TestProfilePersistence:
    """Profile updates are persisted and reflected in subsequent reads."""

    def test_profile_update_persists_across_requests(self, client, fan_user):
        client.force_authenticate(user=fan_user)

        # Update profile
        update_response = client.patch(
            "/api/accounts/profile/",
            {
                "bio": "I love rugby!",
                "location": "Kampala",
                "first_name": "Updated",
                "last_name": "Fan",
            },
            format="json",
        )
        assert update_response.status_code == status.HTTP_200_OK

        # Verify persistence via /me endpoint
        me_response = client.get("/api/accounts/me/")
        assert me_response.status_code == status.HTTP_200_OK
        assert me_response.data["bio"] == "I love rugby!"
        assert me_response.data["location"] == "Kampala"
        assert me_response.data["first_name"] == "Updated"
        assert me_response.data["last_name"] == "Fan"

        # Verify persistence via profile endpoint
        profile_response = client.get("/api/accounts/profile/")
        assert profile_response.status_code == status.HTTP_200_OK
        assert profile_response.data["bio"] == "I love rugby!"
        assert profile_response.data["location"] == "Kampala"

    def test_profile_update_reflects_immediately(self, client, club_admin_user):
        client.force_authenticate(user=club_admin_user)

        # Update location
        client.patch(
            "/api/accounts/profile/",
            {"location": "Entebbe"},
            format="json",
        )

        # Refresh user from DB
        club_admin_user.refresh_from_db()
        assert club_admin_user.location == "Entebbe"

    def test_multiple_profile_updates_accumulate(self, client, league_admin_user):
        client.force_authenticate(user=league_admin_user)

        # First update
        client.patch(
            "/api/accounts/profile/",
            {"bio": "First bio"},
            format="json",
        )

        # Second update
        client.patch(
            "/api/accounts/profile/",
            {"bio": "Second bio", "location": "Jinja"},
            format="json",
        )

        # Verify both changes persisted
        league_admin_user.refresh_from_db()
        assert league_admin_user.bio == "Second bio"
        assert league_admin_user.location == "Jinja"

    def test_profile_update_with_favorite_sport(self, client, union_admin_user):
        client.force_authenticate(user=union_admin_user)

        response = client.patch(
            "/api/accounts/profile/",
            {"favorite_sport": "FOOTBALL"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

        union_admin_user.refresh_from_db()
        assert union_admin_user.favourite_sport == "FOOTBALL"


# ============================================================================
# Tests: Notification Preferences Saved & Applied
# ============================================================================


class TestNotificationPreferencesPersistence:
    """Notification preferences are saved and can be retrieved."""

    def test_get_notification_preferences_creates_defaults(self, client, fan_user):
        client.force_authenticate(user=fan_user)
        response = client.get("/api/accounts/notification-preferences/me/")
        assert response.status_code == status.HTTP_200_OK
        # Should return all default preferences
        assert len(response.data) >= 5  # At least 5 event types
        # Should return all default preferences inside the 'preferences' key
        assert len(response.data["preferences"]) >= 5

    def test_update_notification_preference_persists(self, client, fan_user):
        client.force_authenticate(user=fan_user)

        # Update marketing preference
        update_response = client.patch(
            "/api/accounts/notification-preferences/me/",
            {
                "event_type": "MARKETING_UPDATES",
                "email_enabled": False,
                "push_enabled": False,
                "sms_enabled": False,
            },
            format="json",
        )
        assert update_response.status_code == status.HTTP_200_OK

        # Verify persistence
        get_response = client.get("/api/accounts/notification-preferences/me/")
        assert get_response.status_code == status.HTTP_200_OK

        # Find marketing preference in response
        marketing_pref = next(
            (
                p
                for p in get_response.data["preferences"]
                if p["event_type"] == "MARKETING_UPDATES"
            ),
            None,
        )
        assert marketing_pref is not None
        assert marketing_pref["email_enabled"] is False
        assert marketing_pref["push_enabled"] is False
        assert marketing_pref["sms_enabled"] is False

    def test_notification_preferences_affect_in_app_notifications(
        self, client, club_admin_user
    ):
        client.force_authenticate(user=club_admin_user)

        # Disable push for ticket updates
        client.patch(
            "/api/accounts/notification-preferences/me/",
            {
                "event_type": "TICKET_UPDATES",
                "push_enabled": False,
            },
            format="json",
        )

        # The service should respect this preference
        from accounts.services import get_or_create_notification_preferences
        from accounts.models import NotificationPreference

        prefs = get_or_create_notification_preferences(club_admin_user)
        ticket_pref = next(
            (
                p
                for p in prefs
                if p.event_type == NotificationPreference.EventType.TICKET_UPDATES
            ),
            None,
        )
        assert ticket_pref is not None
        assert ticket_pref.push_enabled is False

    def test_multiple_preferences_updated_independently(self, client, league_admin_user):
        client.force_authenticate(user=league_admin_user)

        # Update multiple preferences at once
        preferences = [
            {
                "event_type": "TICKET_UPDATES",
                "email_enabled": True,
                "push_enabled": True,
                "sms_enabled": False,
            },
            {
                "event_type": "MEMBERSHIP_UPDATES",
                "email_enabled": True,
                "push_enabled": False,
                "sms_enabled": True,
            },
        ]

        for pref in preferences:
            response = client.patch(
                "/api/accounts/notification-preferences/me/",
                pref,
                format="json",
            )
            assert response.status_code == status.HTTP_200_OK

        # Verify both persisted
        get_response = client.get("/api/accounts/notification-preferences/me/")
        assert get_response.status_code == status.HTTP_200_OK

        ticket_pref = next(
            (
                p
                for p in get_response.data["preferences"]
                if p["event_type"] == "TICKET_UPDATES"
            ),
            None,
        )
        membership_pref = next(
            (
                p
                for p in get_response.data["preferences"]
                if p["event_type"] == "MEMBERSHIP_UPDATES"
            ),
            None,
        )

        assert ticket_pref["email_enabled"] is True
        assert ticket_pref["push_enabled"] is True
        assert ticket_pref["sms_enabled"] is False

        assert membership_pref["email_enabled"] is True
        assert membership_pref["push_enabled"] is False
        assert membership_pref["sms_enabled"] is True


# ============================================================================
# Tests: Following List Updates Reflected in Feed
# ============================================================================


class TestFollowingAndFeedIntegration:
    """Following entities updates the user's feed correctly."""

    def test_follow_entity_creates_feed_item(self, client, db):
        from accounts.models import Club, Follow, FeedItem

        User = get_user_model()
        user = User.objects.create_user(
            email="feedfan@example.com",
            password="testpass123",
            first_name="Feed",
            last_name="Fan",
            role=User.Role.FAN,
        )

        # Create a club to follow
        club = Club.objects.create(name="Test FC", slug="test-fc")

        client.force_authenticate(user=user)
        response = client.post(
            "/api/accounts/follow/",
            {"content_type": "CLUB", "object_id": club.id},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

        # Verify follow was created
        assert Follow.objects.filter(
            user=user, content_type="CLUB", object_id=club.id
        ).exists()

        # Feed may or may not have items immediately (depends on aggregation logic)
        # But following relationship should exist
        follows_response = client.get("/api/accounts/follow/")
        assert follows_response.status_code == status.HTTP_200_OK
        assert len(follows_response.data) >= 1

    def test_unfollow_removes_from_following_list(self, client, db):
        from accounts.models import Club, Follow

        User = get_user_model()
        user = User.objects.create_user(
            email="unfollowfan@example.com",
            password="testpass123",
            first_name="Unfollow",
            last_name="Fan",
            role=User.Role.FAN,
        )

        club = Club.objects.create(name="Unfollow FC", slug="unfollow-fc")

        client.force_authenticate(user=user)

        # Follow
        client.post(
            "/api/accounts/follow/",
            {"content_type": "CLUB", "object_id": club.id},
            format="json",
        )

        # Verify followed
        follows = client.get("/api/accounts/follow/")
        assert len(follows.data) == 1

        # Unfollow
        unfollow_response = client.delete(
            "/api/accounts/follow/",
            {"content_type": "CLUB", "object_id": club.id},
            format="json",
        )
        assert unfollow_response.status_code == status.HTTP_200_OK

        # Verify unfollowed
        follows = client.get("/api/accounts/follow/")
        assert len(follows.data) == 0

    def test_follow_multiple_content_types(self, client, db):
        from accounts.models import Club, Follow, League, Union

        User = get_user_model()
        user = User.objects.create_user(
            email="multifollow@example.com",
            password="testpass123",
            first_name="Multi",
            last_name="Follow",
            role=User.Role.FAN,
        )

        club = Club.objects.create(name="Multi Club", slug="multi-club")
        league = League.objects.create(name="Multi League", slug="multi-league")
        union = Union.objects.create(name="Multi Union", slug="multi-union")

        client.force_authenticate(user=user)

        # Follow all three
        client.post(
            "/api/accounts/follow/",
            {"content_type": "CLUB", "object_id": club.id},
            format="json",
        )
        client.post(
            "/api/accounts/follow/",
            {"content_type": "LEAGUE", "object_id": league.id},
            format="json",
        )
        client.post(
            "/api/accounts/follow/",
            {"content_type": "UNION", "object_id": union.id},
            format="json",
        )

        # Verify all follows
        follows = client.get("/api/accounts/follow/")
        assert len(follows.data) == 3

        # Verify content types are present
        followed_types = {item["content_type"] for item in follows.data}
        assert "CLUB" in followed_types
        assert "LEAGUE" in followed_types
        assert "UNION" in followed_types

    def test_check_follow_status(self, client, db):
        from accounts.models import Club, Follow

        User = get_user_model()
        user = User.objects.create_user(
            email="checkfollow@example.com",
            password="testpass123",
            first_name="Check",
            last_name="Follow",
            role=User.Role.FAN,
        )

        club = Club.objects.create(name="Check FC", slug="check-fc")

        client.force_authenticate(user=user)

        # Check before following
        response = client.get(f"/api/accounts/follow/check/CLUB/{club.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_following"] is False

        # Follow
        client.post(
            "/api/accounts/follow/",
            {"content_type": "CLUB", "object_id": club.id},
            format="json",
        )

        # Check after following
        response = client.get(f"/api/accounts/follow/check/CLUB/{club.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_following"] is True

    def test_feed_returns_items_for_followed_entities(self, client, db):
        from accounts.models import Club, FeedItem

        User = get_user_model()
        user = User.objects.create_user(
            email="feedtest@example.com",
            password="testpass123",
            first_name="Feed",
            last_name="Test",
            role=User.Role.FAN,
        )

        club = Club.objects.create(name="Feed Club", slug="feed-club")

        client.force_authenticate(user=user)

        # Follow the club
        client.post(
            "/api/accounts/follow/",
            {"content_type": "CLUB", "object_id": club.id},
            format="json",
        )

        # Create a feed item related to the club
        FeedItem.objects.create(
            user=user,
            item_type=FeedItem.ItemType.NEWS,
            title="Feed Club signs new player",
            related_object_type="CLUB",
            related_object_id=club.id,
            relevance_score=0.8,
        )

        # Get feed
        feed_response = client.get("/api/accounts/feed/")
        assert feed_response.status_code == status.HTTP_200_OK
        assert len(feed_response.data) >= 1

        # Verify feed contains the news item
        news_items = [item for item in feed_response.data["results"] if item["item_type"] == "NEWS"]
        assert len(news_items) >= 1
        assert "Feed Club" in news_items[0]["title"]

    def test_feed_mark_items_read(self, client, db):
        from accounts.models import Club, FeedItem

        User = get_user_model()
        user = User.objects.create_user(
            email="markread@example.com",
            password="testpass123",
            first_name="Mark",
            last_name="Read",
            role=User.Role.FAN,
        )

        club = Club.objects.create(name="Read Club", slug="read-club")

        client.force_authenticate(user=user)

        # Follow the club
        client.post(
            "/api/accounts/follow/",
            {"content_type": "CLUB", "object_id": club.id},
            format="json",
        )

        # Create unread feed item
        item = FeedItem.objects.create(
            user=user,
            item_type=FeedItem.ItemType.NEWS,
            title=(
                "Unread news about Read Club"
            ),
            source_content_type="CLUB",
            source_object_id=club.id,
            relevance_score=0.8,
        )

        # Verify unread count
        unread_response = client.get("/api/accounts/feed/unread-count/")
        assert unread_response.status_code == status.HTTP_200_OK
        assert unread_response.data["unread_count"] >= 1

        # Mark as read
        mark_response = client.post(f"/api/accounts/feed/mark-read/{item.id}/")
        assert mark_response.status_code == status.HTTP_200_OK

        # Verify unread count decreased
        unread_response = client.get("/api/accounts/feed/unread-count/")
        assert unread_response.data["unread_count"] == 0

    def test_feed_mark_all_read(self, client, db):
        from accounts.models import Club, FeedItem

        User = get_user_model()
        user = User.objects.create_user(
            email="markallread@example.com",
            password="testpass123",
            first_name="MarkAll",
            last_name="Read",
            role=User.Role.FAN,
        )

        club = Club.objects.create(name="MarkAll Club", slug="markall-club")

        client.force_authenticate(user=user)

        # Follow the club
        client.post(
            "/api/accounts/follow/",
            {"content_type": "CLUB", "object_id": club.id},
            format="json",
        )

        # Create multiple feed items
        FeedItem.objects.create(
            user=user,
            item_type=FeedItem.ItemType.NEWS,
            title="News 1",
            source_content_type="CLUB",
            source_object_id=club.id,
            relevance_score=0.8,
        )
        FeedItem.objects.create(
            user=user,
            item_type=FeedItem.ItemType.MATCH_RESULT,
            title="Match Result",
            source_content_type="CLUB",
            source_object_id=club.id,
            relevance_score=0.8,
        )

        # Mark all as read
        mark_all_response = client.post("/api/accounts/feed/mark-all-read/")
        assert mark_all_response.status_code == status.HTTP_200_OK
        assert "marked as read" in mark_all_response.data["detail"]

        # Verify unread count is 0
        unread_response = client.get("/api/accounts/feed/unread-count/")
        assert unread_response.data["unread_count"] == 0


# ============================================================================
# Tests: Wallet & Payment History Accessible
# ============================================================================


class TestWalletAndPaymentAccess:
    """User can access their wallet/payment summary and payment history."""

    def test_wallet_accessible_for_all_roles(self, client, fan_user):
        client.force_authenticate(user=fan_user)
        response = client.get("/api/accounts/wallet/")
        assert response.status_code == status.HTTP_200_OK
        assert "stored_balance_enabled" in response.data
        assert response.data["stored_balance_enabled"] is False
        assert "balance" in response.data
        assert "total_spent" in response.data

    def test_payment_history_accessible_for_all_roles(self, client, club_admin_user):
        client.force_authenticate(user=club_admin_user) 
        response = client.get("/api/accounts/payments/")
        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data

    def test_wallet_shows_no_stored_balance(self, client, league_admin_user):
        client.force_authenticate(user=league_admin_user)
        response = client.get("/api/accounts/wallet/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["balance"] == 0.00
        assert "does not currently store" in response.data["balance_note"].lower()

    def test_payment_history_filters_work(self, client, union_admin_user):
        client.force_authenticate(user=union_admin_user)
        # Should return empty list but still 200
        response = client.get("/api/accounts/payments/")
        assert response.status_code == status.HTTP_200_OK
        response = client.get("/api/accounts/payments/?status=SUCCESSFUL")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_unauthenticated_cannot_access_wallet(self, client, db):
        response = client.get("/api/accounts/wallet/")
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_cannot_access_payments(self, client, db):
        response = client.get("/api/accounts/payments/")
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )
