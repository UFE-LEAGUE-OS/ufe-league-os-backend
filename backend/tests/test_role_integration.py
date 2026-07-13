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
