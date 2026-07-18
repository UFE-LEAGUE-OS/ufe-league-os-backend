"""Integration contract for dashboard access in authenticated API responses."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.dashboard_entitlements import resolve_dashboard_access
from accounts.models import Club, ClubAdminScope, RoleApproval
from accounts.serializers import UserSerializer, UserSummarySerializer
from dashboards.models import (
    League,
    LeagueAdminScope,
    Union,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
from dashboards.serializers import UnionWorkspaceUserSerializer
from sponsorships.models import SponsorAccount, SponsorAccountMember

User = get_user_model()


class DashboardAccessApiTests(TestCase):
    password = "ValidTestPass123!"

    def setUp(self):
        self.client = APIClient()
        self.sequence = 0

    def unique(self, prefix):
        self.sequence += 1
        return f"{prefix}-{self.sequence}"

    def create_user(self, prefix, role=User.Role.FAN, **fields):
        value = self.unique(prefix)
        return User.objects.create_user(
            email=f"{value}@example.com",
            password=self.password,
            first_name="Access",
            last_name="Tester",
            role=role,
            is_email_verified=True,
            **fields,
        )

    def create_union_membership(
        self,
        user,
        role=UnionWorkspaceMembership.Role.UNION_ADMIN,
        *,
        active=True,
        workspace_active=True,
    ):
        value = self.unique("union")
        union = Union.objects.create(name=f"{value} Union", slug=f"{value}-union")
        workspace = UnionWorkspace.objects.create(
            related_union=union,
            name=f"{value} Workspace",
            slug=f"{value}-workspace",
            acronym=value[:8].upper(),
            sport="Football",
            status=(
                UnionWorkspace.Status.ACTIVE
                if workspace_active
                else UnionWorkspace.Status.INACTIVE
            ),
        )
        return UnionWorkspaceMembership.objects.create(
            user=user,
            workspace=workspace,
            role=role,
            is_active=active,
        )

    def create_league_scope(
        self,
        user,
        role=LeagueAdminScope.Role.LEAGUE_ADMIN,
    ):
        value = self.unique("league")
        union = Union.objects.create(name=f"{value} Union", slug=f"{value}-union")
        league = League.objects.create(
            union=union,
            name=f"{value} League",
            slug=f"{value}-league",
        )
        return LeagueAdminScope.objects.create(
            user=user,
            league=league,
            role=role,
        )

    def create_club_scope(
        self,
        user,
        role=ClubAdminScope.Role.CLUB_ADMIN,
    ):
        value = self.unique("club")
        club = Club.objects.create(name=f"{value} Club", slug=f"{value}-club")
        return ClubAdminScope.objects.create(user=user, club=club, role=role)

    def create_individual_sponsor(self, user):
        account = SponsorAccount.objects.create(
            owner=user,
            sponsor_type=SponsorAccount.SponsorType.INDIVIDUAL,
            name=user.full_name,
            status=SponsorAccount.Status.APPROVED,
        )
        SponsorAccountMember.objects.create(
            sponsor_account=account,
            user=user,
            member_role=SponsorAccountMember.MemberRole.OWNER,
        )
        return account

    def create_corporate_sponsor(
        self,
        user,
        role=SponsorAccountMember.MemberRole.OWNER,
    ):
        value = self.unique("corporate")
        account = SponsorAccount.objects.create(
            owner=user,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name=f"{value} Ltd",
            tin=f"{self.sequence:010d}",
            status=SponsorAccount.Status.APPROVED,
        )
        SponsorAccountMember.objects.create(
            sponsor_account=account,
            user=user,
            member_role=role,
        )
        return account

    def assert_access_contract(self, access, user):
        self.assertEqual(access, resolve_dashboard_access(user))
        self.assertEqual(
            set(access),
            {"version", "default_entitlement_id", "entitlements"},
        )
        self.assertEqual(access["version"], 1)
        ids = [item["id"] for item in access["entitlements"]]
        if access["default_entitlement_id"] is None:
            self.assertEqual(access["entitlements"], [])
        else:
            self.assertIn(access["default_entitlement_id"], ids)
        for entitlement in access["entitlements"]:
            self.assertEqual(
                entitlement["permissions"],
                sorted(set(entitlement["permissions"])),
            )

    def assert_user_response_access(self, response, user):
        self.assertIn("user", response.data)
        self.assertIn("dashboard_access", response.data["user"])
        self.assert_access_contract(response.data["user"]["dashboard_access"], user)

    def login(self, user):
        return self.client.post(
            "/api/accounts/login/",
            {"identifier": user.email, "password": self.password},
            format="json",
        )

    def test_password_login_account_matrix(self):
        cases = []

        fan = self.create_user("fan")
        cases.append(("fan", fan, "/dashboard/fan", "/api/dashboards/fan/"))

        individual = self.create_user(
            "individual",
            role=User.Role.SPONSOR,
            sponsor_type=User.SponsorType.INDIVIDUAL,
        )
        self.create_individual_sponsor(individual)
        cases.append(
            (
                "individual",
                individual,
                "/dashboard/sponsor",
                "/api/dashboards/sponsor/",
            )
        )

        for member_role in (
            SponsorAccountMember.MemberRole.OWNER,
            SponsorAccountMember.MemberRole.FINANCE,
        ):
            user = self.create_user(
                f"corporate-{member_role.lower()}",
                sponsor_type=User.SponsorType.CORPORATE,
            )
            self.create_corporate_sponsor(user, member_role)
            cases.append(
                (
                    f"corporate-{member_role}",
                    user,
                    "/dashboard/sponsor",
                    "/api/dashboards/sponsor/",
                )
            )

        super_admin = self.create_user("super", role=User.Role.SUPER_ADMIN)
        cases.append(
            (
                "super",
                super_admin,
                "/dashboard/super-admin",
                "/api/dashboards/super-admin/",
            )
        )

        union_admin = self.create_user("union-admin", role=User.Role.UNION_ADMIN)
        self.create_union_membership(union_admin)
        cases.append(
            (
                "union-admin",
                union_admin,
                "/dashboard/union-admin",
                "/api/dashboards/union-admin/",
            )
        )

        official = self.create_user("official", role=User.Role.REFEREE)
        self.create_union_membership(
            official,
            UnionWorkspaceMembership.Role.MATCH_OFFICIAL,
        )
        cases.append(
            (
                "official",
                official,
                "/dashboard/union-admin",
                "/api/dashboards/union-admin/",
            )
        )

        union_ticketing = self.create_user(
            "union-ticketing",
            role=User.Role.TICKETING_OFFICER,
        )
        self.create_union_membership(
            union_ticketing,
            UnionWorkspaceMembership.Role.TICKETING_OFFICER,
        )
        cases.append(
            (
                "union-ticketing",
                union_ticketing,
                "/dashboard/union-admin",
                "/api/dashboards/union-admin/",
            )
        )

        league_admin = self.create_user(
            "league-admin",
            role=User.Role.LEAGUE_ADMIN,
        )
        self.create_league_scope(league_admin)
        cases.append(
            (
                "league-admin",
                league_admin,
                "/dashboard/league-admin",
                "/api/dashboards/league-admin/",
            )
        )

        league_viewer = self.create_user("league-viewer")
        self.create_league_scope(league_viewer, LeagueAdminScope.Role.VIEWER)
        cases.append(
            (
                "league-viewer",
                league_viewer,
                "/dashboard/league-admin",
                "/api/dashboards/league-admin/",
            )
        )

        club_admin = self.create_user("club-admin", role=User.Role.CLUB_ADMIN)
        self.create_club_scope(club_admin)
        cases.append(
            (
                "club-admin",
                club_admin,
                "/dashboard/club-admin",
                "/api/dashboards/club-admin/",
            )
        )

        club_ticketing = self.create_user(
            "club-ticketing",
            role=User.Role.TICKETING_OFFICER,
        )
        self.create_club_scope(
            club_ticketing,
            ClubAdminScope.Role.TICKETING_OFFICER,
        )
        cases.append(
            (
                "club-ticketing",
                club_ticketing,
                "/dashboard/ticketing-officer",
                "/api/dashboards/ticketing-officer/",
            )
        )

        conflicted = self.create_user("conflicted")
        self.create_union_membership(conflicted)
        self.create_league_scope(conflicted)
        cases.append(("conflicted", conflicted, None, None))

        for label, user, frontend_route, backend_route in cases:
            with self.subTest(label=label):
                response = self.login(user)
                self.assertEqual(response.status_code, 200)
                self.assert_user_response_access(response, user)
                self.assertEqual(
                    response.data["frontend_dashboard_route"],
                    frontend_route,
                )
                self.assertEqual(
                    response.data["backend_dashboard_route"],
                    backend_route,
                )

    def test_me_refreshes_access_and_generic_member_data_does_not_expose_it(self):
        user = self.create_user("me")
        other = self.create_user("other")
        self.client.force_authenticate(user)

        response = self.client.get("/api/accounts/me/")
        self.assertEqual(response.status_code, 200)
        self.assert_access_contract(response.data["dashboard_access"], user)

        account = self.create_corporate_sponsor(
            user,
            SponsorAccountMember.MemberRole.OWNER,
        )
        refreshed = self.client.get("/api/accounts/me/")
        self.assert_access_contract(refreshed.data["dashboard_access"], user)
        self.assertEqual(
            refreshed.data["dashboard_access"]["default_entitlement_id"],
            f"corporate-sponsor-{account.id}",
        )
        SponsorAccountMember.objects.create(
            sponsor_account=account,
            user=other,
            member_role=SponsorAccountMember.MemberRole.VIEWER,
        )
        members = self.client.get(f"/api/sponsorships/accounts/{account.id}/members/")
        self.assertEqual(members.status_code, 200)
        for member in members.data["results"]:
            self.assertNotIn("dashboard_access", member["user"])
        SponsorAccountMember.objects.filter(
            sponsor_account=account,
            user=user,
        ).update(is_active=False)
        deactivated = self.client.get("/api/accounts/me/")
        self.assertEqual(
            deactivated.data["dashboard_access"]["default_entitlement_id"],
            "fan",
        )

    @patch("accounts.serializers.verify_google_id_token")
    def test_google_auth_returns_same_contract_shapes(self, verify_token):
        fan = self.create_user("google-fan")

        sponsor = self.create_user(
            "google-sponsor",
            role=User.Role.SPONSOR,
            sponsor_type=User.SponsorType.INDIVIDUAL,
        )
        sponsor_account = self.create_individual_sponsor(sponsor)

        operational = self.create_user(
            "google-union",
            role=User.Role.UNION_ADMIN,
        )
        operational_membership = self.create_union_membership(operational)

        match_official = self.create_user(
            "google-official",
            role=User.Role.REFEREE,
        )
        official_membership = self.create_union_membership(
            match_official,
            UnionWorkspaceMembership.Role.MATCH_OFFICIAL,
        )

        no_access = self.create_user(
            "google-empty",
            role=User.Role.LEAGUE_ADMIN,
        )

        cases = (
            (
                fan,
                "fan",
                "/dashboard/fan",
                "/api/dashboards/fan/",
            ),
            (
                sponsor,
                f"individual-sponsor-{sponsor_account.id}",
                "/dashboard/sponsor",
                "/api/dashboards/sponsor/",
            ),
            (
                operational,
                f"union-workspace-{operational_membership.workspace_id}",
                "/dashboard/union-admin",
                "/api/dashboards/union-admin/",
            ),
            (
                match_official,
                f"union-workspace-{official_membership.workspace_id}",
                "/dashboard/union-admin",
                "/api/dashboards/union-admin/",
            ),
            (no_access, None, None, None),
        )
        for user, default_id, frontend_route, backend_route in cases:
            with self.subTest(user=user.email):
                verify_token.return_value = {
                    "email": user.email,
                    "given_name": user.first_name,
                    "family_name": user.last_name,
                }
                response = self.client.post(
                    "/api/accounts/google/",
                    {"id_token": "test-google-token"},
                    format="json",
                )
                self.assertEqual(response.status_code, 200)
                self.assert_user_response_access(response, user)
                access = response.data["user"]["dashboard_access"]
                self.assertEqual(access, resolve_dashboard_access(user))
                self.assertEqual(access["default_entitlement_id"], default_id)
                self.assertEqual(
                    response.data["frontend_dashboard_route"],
                    frontend_route,
                )
                self.assertEqual(
                    response.data["backend_dashboard_route"],
                    backend_route,
                )

    def test_sponsor_creation_responses_use_fresh_resolver_contract(self):
        user = self.create_user(
            "sponsor-create",
            sponsor_type=User.SponsorType.INDIVIDUAL,
        )
        self.client.force_authenticate(user)
        response = self.client.post(
            "/api/sponsorships/accounts/",
            {"sponsor_type": "INDIVIDUAL", "name": "Personal Sponsor"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("user", response.data)
        self.assert_access_contract(response.data["dashboard_access"], user)

        account = SponsorAccount.objects.get(pk=response.data["sponsor_account"]["id"])
        account.status = SponsorAccount.Status.APPROVED
        account.save(update_fields=["status"])
        me_response = self.client.get("/api/accounts/me/")
        access = me_response.data["dashboard_access"]
        self.assertEqual(
            access["entitlements"][0]["scope_id"],
            account.id,
        )
        self.assertEqual(access["entitlements"][-1]["scope_id"], user.id)

    def test_role_review_does_not_expose_affected_users_access(self):
        requester = self.create_user("requester", role=User.Role.SUPER_ADMIN)
        reviewer = self.create_user("reviewer", role=User.Role.SUPER_ADMIN)
        target = self.create_user("approval-target")
        membership = self.create_union_membership(target)
        approval = RoleApproval.objects.create(
            target_user=target,
            requested_role=User.Role.UNION_ADMIN,
            requested_by=requester,
        )
        self.client.force_authenticate(reviewer)
        response = self.client.post(
            f"/api/accounts/role-approvals/{approval.id}/review/",
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        target.refresh_from_db()
        self.assertEqual(target.role, User.Role.UNION_ADMIN)
        self.assertNotIn("dashboard_access", response.data)
        response_text = str(response.data)
        self.assertNotIn(f"union-workspace-{membership.workspace_id}", response_text)
        self.assertNotIn("workspace", response_text)
        self.assertNotIn("permissions", response_text)
        direct_access = resolve_dashboard_access(target)
        self.assertEqual(
            direct_access["default_entitlement_id"],
            f"union-workspace-{membership.workspace_id}",
        )
        self.client.force_authenticate(target)
        me_response = self.client.get("/api/accounts/me/")
        self.assert_access_contract(me_response.data["dashboard_access"], target)

        self.client.force_authenticate(reviewer)
        unscoped = self.create_user("unscoped-target")
        unscoped_approval = RoleApproval.objects.create(
            target_user=unscoped,
            requested_role=User.Role.UNION_ADMIN,
            requested_by=requester,
        )
        response = self.client.post(
            f"/api/accounts/role-approvals/{unscoped_approval.id}/review/",
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        unscoped.refresh_from_db()
        self.assertNotIn("dashboard_access", response.data)
        self.assertIsNone(resolve_dashboard_access(unscoped)["default_entitlement_id"])

        existing = self.create_user("rejected-existing")
        rejected = RoleApproval.objects.create(
            target_user=existing,
            requested_role=User.Role.SUPER_ADMIN,
            requested_by=requester,
        )
        response = self.client.post(
            f"/api/accounts/role-approvals/{rejected.id}/review/",
            {"action": "reject", "rejection_reason": "Not approved."},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        existing.refresh_from_db()
        self.assertEqual(existing.role, User.Role.FAN)
        self.assertNotIn("dashboard_access", response.data)
        self.assertEqual(
            resolve_dashboard_access(existing)["default_entitlement_id"],
            "fan",
        )

    def test_general_and_union_workspace_switches_validate_real_entitlements(self):
        user = self.create_user("switch", role=User.Role.UNION_ADMIN)
        membership = self.create_union_membership(user)
        self.client.force_authenticate(user)

        response = self.client.post(
            "/api/accounts/switch-workspace/",
            {"role": User.Role.UNION_ADMIN},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assert_user_response_access(response, user)
        self.assertEqual(
            response.data["selected_entitlement_id"],
            f"union-workspace-{membership.workspace_id}",
        )

        union_response = self.client.post(
            "/api/dashboards/union-admin/switch-workspace/",
            {"workspace": membership.workspace.slug},
            format="json",
        )
        self.assertEqual(union_response.status_code, 200)
        self.assert_access_contract(union_response.data["dashboard_access"], user)
        self.assertEqual(
            union_response.data["selected_entitlement_id"],
            f"union-workspace-{membership.workspace_id}",
        )

        invalid = self.client.post(
            "/api/dashboards/union-admin/switch-workspace/",
            {"workspace": "not-mine"},
            format="json",
        )
        self.assertEqual(invalid.status_code, 403)
        self.assertNotIn("dashboard_access", invalid.data)
        self.assertNotIn("frontend_dashboard_route", invalid.data)

        membership.workspace.status = UnionWorkspace.Status.INACTIVE
        membership.workspace.save(update_fields=["status"])
        inactive = self.client.post(
            "/api/dashboards/union-admin/switch-workspace/",
            {"workspace": membership.workspace.slug},
            format="json",
        )
        self.assertEqual(inactive.status_code, 403)

        ambiguous_user = self.create_user("ambiguous-union")
        first = self.create_union_membership(
            ambiguous_user,
            UnionWorkspaceMembership.Role.REGISTRAR,
        )
        second = self.create_union_membership(
            ambiguous_user,
            UnionWorkspaceMembership.Role.FINANCE_OFFICER,
        )
        self.client.force_authenticate(ambiguous_user)
        ambiguous = self.client.post(
            "/api/accounts/switch-workspace/",
            {"role": User.Role.UNION_ADMIN},
            format="json",
        )
        self.assertEqual(ambiguous.status_code, 200)
        self.assertIsNone(ambiguous.data["selected_entitlement_id"])
        self.assertIsNone(ambiguous.data["frontend_dashboard_route"])
        self.assertIsNone(ambiguous.data["backend_dashboard_route"])
        self.assertIsNone(ambiguous.data["role_display"])
        self.assertNotIn("Switched to", ambiguous.data["message"])
        self.assertEqual(
            ambiguous.data["message"],
            "Multiple workspaces are available. Select a specific workspace.",
        )
        self.assertEqual(
            {item["entitlement_id"] for item in ambiguous.data["available_dashboards"]},
            {
                f"union-workspace-{first.workspace_id}",
                f"union-workspace-{second.workspace_id}",
            },
        )

    def test_general_switch_rejects_incompatible_union_selectors(self):
        cases = (
            (
                UnionWorkspaceMembership.Role.MATCH_OFFICIAL,
                User.Role.REFEREE,
                (User.Role.UNION_ADMIN,),
            ),
            (
                UnionWorkspaceMembership.Role.TICKETING_OFFICER,
                User.Role.TICKETING_OFFICER,
                (User.Role.UNION_ADMIN,),
            ),
            (
                UnionWorkspaceMembership.Role.REGISTRAR,
                User.Role.FAN,
                (User.Role.REFEREE, User.Role.TICKETING_OFFICER),
            ),
        )
        for workspace_role, primary_role, rejected_roles in cases:
            with self.subTest(workspace_role=workspace_role):
                user = self.create_user(
                    f"reject-selector-{workspace_role}",
                    role=primary_role,
                )
                self.create_union_membership(user, workspace_role)
                self.client.force_authenticate(user)
                original_role = user.role
                for rejected_role in rejected_roles:
                    response = self.client.post(
                        "/api/accounts/switch-workspace/",
                        {"role": rejected_role},
                        format="json",
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertNotIn("selected_entitlement_id", response.data)
                    self.assertNotIn("frontend_dashboard_route", response.data)
                    self.assertNotIn("backend_dashboard_route", response.data)
                user.refresh_from_db()
                self.assertEqual(user.role, original_role)

    def test_union_workspace_switch_fails_closed_without_matching_entitlement(self):
        cases = (
            "inactive-membership",
            "invalid-role",
            "cross-family",
            "incompatible-primary",
        )
        for case in cases:
            with self.subTest(case=case):
                role = (
                    User.Role.LEAGUE_ADMIN
                    if case == "incompatible-primary"
                    else User.Role.FAN
                )
                user = self.create_user(f"union-switch-{case}", role=role)
                membership = self.create_union_membership(
                    user,
                    active=case != "inactive-membership",
                )
                if case == "invalid-role":
                    UnionWorkspaceMembership.objects.filter(pk=membership.pk).update(
                        role="INVALID"
                    )
                if case == "cross-family":
                    self.create_league_scope(user)
                self.client.force_authenticate(user)
                response = self.client.post(
                    "/api/dashboards/union-admin/switch-workspace/",
                    {"workspace": membership.workspace.slug},
                    format="json",
                )
                self.assertEqual(response.status_code, 403)
                self.assertNotIn("dashboard_access", response.data)
                self.assertNotIn("selected_entitlement_id", response.data)
                self.assertNotIn("frontend_dashboard_route", response.data)
                self.assertNotIn("backend_dashboard_route", response.data)
                self.assertNotIn("workspace", response.data)
                if case != "inactive-membership":
                    self.assertEqual(
                        response.data["detail"],
                        "You do not have active dashboard access to this workspace.",
                    )

    def test_dashboard_me_contains_current_user_contract_once(self):
        user = self.create_user("dashboard-me")
        self.client.force_authenticate(user)
        response = self.client.get("/api/dashboards/me/")
        self.assertEqual(response.status_code, 200)
        self.assert_user_response_access(response, user)
        self.assertNotIn("dashboard_access", response.data)

    def test_dashboard_me_uses_default_entitlement_and_neutral_empty_state(self):
        legacy_union = self.create_user("legacy-union")
        self.create_union_membership(
            legacy_union,
            UnionWorkspaceMembership.Role.REGISTRAR,
        )

        sponsor = self.create_user(
            "dashboard-sponsor",
            role=User.Role.SPONSOR,
            sponsor_type=User.SponsorType.INDIVIDUAL,
        )
        self.create_individual_sponsor(sponsor)

        match_official = self.create_user(
            "dashboard-official",
            role=User.Role.REFEREE,
        )
        self.create_union_membership(
            match_official,
            UnionWorkspaceMembership.Role.MATCH_OFFICIAL,
        )
        union_ticketing = self.create_user(
            "dashboard-union-ticketing",
            role=User.Role.TICKETING_OFFICER,
        )
        self.create_union_membership(
            union_ticketing,
            UnionWorkspaceMembership.Role.TICKETING_OFFICER,
        )

        empty_users = [
            self.create_user("empty-union", role=User.Role.UNION_ADMIN),
            self.create_user("empty-league", role=User.Role.LEAGUE_ADMIN),
            self.create_user("empty-club", role=User.Role.CLUB_ADMIN),
        ]
        conflicted = self.create_user("empty-conflict")
        self.create_union_membership(conflicted)
        self.create_league_scope(conflicted)
        empty_users.append(conflicted)

        cases = (
            (
                legacy_union,
                User.Role.UNION_ADMIN,
                "Union Admin Dashboard",
                "/api/dashboards/union-admin/",
            ),
            (
                sponsor,
                User.Role.SPONSOR,
                "Sponsor Dashboard",
                "/api/dashboards/sponsor/",
            ),
            (
                match_official,
                User.Role.REFEREE,
                "Match Official Dashboard",
                "/api/dashboards/union-admin/",
            ),
            (
                union_ticketing,
                User.Role.TICKETING_OFFICER,
                "Ticketing Officer Dashboard",
                "/api/dashboards/union-admin/",
            ),
        )
        for user, dashboard_role, title, backend_route in cases:
            with self.subTest(user=user.email):
                self.client.force_authenticate(user)
                response = self.client.get("/api/dashboards/me/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["dashboard_role"], dashboard_role)
                self.assertEqual(response.data["dashboard"]["title"], title)
                self.assertEqual(
                    response.data["backend_dashboard_route"],
                    backend_route,
                )

        for user in empty_users:
            with self.subTest(empty_user=user.email):
                self.client.force_authenticate(user)
                response = self.client.get("/api/dashboards/me/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.data["message"],
                    "Dashboard access is unavailable.",
                )
                self.assertIsNone(response.data["dashboard_role"])
                self.assertIsNone(response.data["frontend_dashboard_route"])
                self.assertIsNone(response.data["backend_dashboard_route"])
                self.assertEqual(response.data["available_dashboards"], [])
                self.assertIsNone(response.data["dashboard"])
                self.assert_access_contract(
                    response.data["user"]["dashboard_access"],
                    user,
                )

    def test_union_compatibility_entries_are_valid_legacy_switch_selectors(self):
        selector_by_workspace_role = {
            UnionWorkspaceMembership.Role.MATCH_OFFICIAL: User.Role.REFEREE,
            UnionWorkspaceMembership.Role.TICKETING_OFFICER: (
                User.Role.TICKETING_OFFICER
            ),
        }
        display_by_workspace_role = dict(UnionWorkspaceMembership.Role.choices)
        expected_keys = {
            "role",
            "role_display",
            "route",
            "backend_route",
            "entitlement_id",
        }
        for workspace_role, expected_display in display_by_workspace_role.items():
            with self.subTest(workspace_role=workspace_role):
                legacy_role = selector_by_workspace_role.get(
                    workspace_role,
                    User.Role.UNION_ADMIN,
                )
                user = self.create_user(
                    f"compat-{workspace_role}",
                    role=legacy_role,
                )
                self.create_union_membership(user, workspace_role)
                self.client.force_authenticate(user)
                dashboard_response = self.client.get("/api/dashboards/me/")
                entry = dashboard_response.data["available_dashboards"][0]
                self.assertEqual(set(entry), expected_keys)
                self.assertEqual(entry["role"], legacy_role)
                self.assertEqual(entry["role_display"], expected_display)
                if workspace_role == UnionWorkspaceMembership.Role.MATCH_OFFICIAL:
                    self.assertNotEqual(entry["role_display"], "Referee")
                self.assertEqual(
                    entry["backend_route"],
                    "/api/dashboards/union-admin/",
                )
                shared_route_response = self.client.get(entry["backend_route"])
                self.assertEqual(shared_route_response.status_code, 200)
                self.assertEqual(
                    shared_route_response.data["dashboard_role"],
                    legacy_role,
                )
                if workspace_role == UnionWorkspaceMembership.Role.MATCH_OFFICIAL:
                    self.assertEqual(
                        shared_route_response.data["dashboard"]["title"],
                        "Match Official Dashboard",
                    )
                if workspace_role == UnionWorkspaceMembership.Role.TICKETING_OFFICER:
                    self.assertEqual(
                        shared_route_response.data["dashboard"]["title"],
                        "Ticketing Officer Dashboard",
                    )
                switch_response = self.client.post(
                    "/api/accounts/switch-workspace/",
                    {"role": entry["role"]},
                    format="json",
                )
                self.assertEqual(switch_response.status_code, 200)
                self.assertEqual(
                    switch_response.data["selected_entitlement_id"],
                    entry["entitlement_id"],
                )
                self.assertEqual(
                    switch_response.data["frontend_dashboard_route"],
                    entry["route"],
                )
                self.assertEqual(
                    switch_response.data["backend_dashboard_route"],
                    entry["backend_route"],
                )
                self.assertEqual(
                    switch_response.data["role_display"],
                    expected_display,
                )
                if workspace_role == UnionWorkspaceMembership.Role.MATCH_OFFICIAL:
                    self.assertEqual(switch_response.data["role"], User.Role.REFEREE)
                    self.assertNotEqual(
                        switch_response.data["role_display"],
                        "Referee",
                    )

    def test_role_specific_dashboards_use_shared_routes_for_multiple_scopes(self):
        corporate = self.create_user(
            "multi-corporate",
            role=User.Role.SPONSOR,
            sponsor_type=User.SponsorType.CORPORATE,
        )
        self.create_corporate_sponsor(corporate)
        self.create_corporate_sponsor(corporate)

        union_admin = self.create_user(
            "multi-union-admin",
            role=User.Role.UNION_ADMIN,
        )
        self.create_union_membership(union_admin)
        self.create_union_membership(union_admin)

        league_admin = self.create_user(
            "multi-league-admin",
            role=User.Role.LEAGUE_ADMIN,
        )
        self.create_league_scope(league_admin)
        self.create_league_scope(league_admin)

        match_official = self.create_user(
            "multi-match-official",
            role=User.Role.REFEREE,
        )
        self.create_union_membership(
            match_official,
            UnionWorkspaceMembership.Role.MATCH_OFFICIAL,
        )
        self.create_union_membership(
            match_official,
            UnionWorkspaceMembership.Role.MATCH_OFFICIAL,
        )

        cases = (
            (
                corporate,
                "/api/dashboards/sponsor/",
                "/dashboard/sponsor",
                "/api/dashboards/sponsor/",
                3,
                User.Role.SPONSOR,
            ),
            (
                union_admin,
                "/api/dashboards/union-admin/",
                "/dashboard/union-admin",
                "/api/dashboards/union-admin/",
                2,
                User.Role.UNION_ADMIN,
            ),
            (
                league_admin,
                "/api/dashboards/league-admin/",
                "/dashboard/league-admin",
                "/api/dashboards/league-admin/",
                2,
                User.Role.LEAGUE_ADMIN,
            ),
            (
                match_official,
                "/api/dashboards/union-admin/",
                "/dashboard/union-admin",
                "/api/dashboards/union-admin/",
                2,
                User.Role.REFEREE,
            ),
        )
        for (
            user,
            endpoint,
            frontend_route,
            backend_route,
            available_count,
            dashboard_role,
        ) in cases:
            with self.subTest(endpoint=endpoint):
                self.client.force_authenticate(user)
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["dashboard_role"], dashboard_role)
                self.assertEqual(
                    response.data["frontend_dashboard_route"],
                    frontend_route,
                )
                self.assertEqual(
                    response.data["backend_dashboard_route"],
                    backend_route,
                )
                self.assertEqual(
                    len(response.data["available_dashboards"]),
                    available_count,
                )

    def test_club_admin_dashboard_routes_require_club_entitlement(self):
        one_scope = self.create_user("club-one", role=User.Role.CLUB_ADMIN)
        self.create_club_scope(one_scope)

        multiple_scopes = self.create_user(
            "club-multiple",
            role=User.Role.CLUB_ADMIN,
        )
        self.create_club_scope(multiple_scopes)
        self.create_club_scope(multiple_scopes)

        unscoped = self.create_user("club-unscoped", role=User.Role.CLUB_ADMIN)

        conflicted = self.create_user("club-conflicted", role=User.Role.CLUB_ADMIN)
        self.create_club_scope(conflicted)
        self.create_union_membership(conflicted)

        cases = (
            (
                one_scope,
                200,
                1,
                "/dashboard/club-admin",
                "/api/dashboards/club-admin/",
            ),
            (
                multiple_scopes,
                200,
                2,
                "/dashboard/club-admin",
                "/api/dashboards/club-admin/",
            ),
            (unscoped, 403, None, None, None),
            (conflicted, 403, None, None, None),
        )
        for (
            user,
            expected_status,
            available_count,
            frontend_route,
            backend_route,
        ) in cases:
            with self.subTest(user=user.email):
                self.client.force_authenticate(user)
                response = self.client.get("/api/dashboards/club-admin/")
                self.assertEqual(response.status_code, expected_status)
                if expected_status == 403:
                    self.assertEqual(
                        response.data["detail"],
                        "You do not have active access to this dashboard.",
                    )
                    continue
                self.assertEqual(
                    response.data["frontend_dashboard_route"],
                    frontend_route,
                )
                self.assertEqual(
                    response.data["backend_dashboard_route"],
                    backend_route,
                )
                self.assertEqual(
                    len(response.data["available_dashboards"]),
                    available_count,
                )

    def test_role_specific_endpoints_are_entitlement_authoritative(self):
        unscoped_cases = (
            (User.Role.CLUB_ADMIN, "/api/dashboards/club-admin/"),
            (User.Role.LEAGUE_ADMIN, "/api/dashboards/league-admin/"),
            (User.Role.UNION_ADMIN, "/api/dashboards/union-admin/"),
            (User.Role.REFEREE, "/api/dashboards/referee/"),
            (User.Role.TICKETING_OFFICER, "/api/dashboards/ticketing-officer/"),
            (User.Role.SPONSOR, "/api/dashboards/sponsor/"),
        )
        for role, endpoint in unscoped_cases:
            with self.subTest(role=role):
                user = self.create_user(f"unscoped-{role.lower()}", role=role)
                self.client.force_authenticate(user)
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 403)

        league_admin = self.create_user("legacy-scoped-league")
        self.create_league_scope(league_admin)
        self.client.force_authenticate(league_admin)
        league_response = self.client.get("/api/dashboards/league-admin/")
        self.assertEqual(league_response.status_code, 200)
        self.assertEqual(
            league_response.data["dashboard_role"],
            User.Role.LEAGUE_ADMIN,
        )

        club_ticketing = self.create_user("legacy-scoped-ticketing")
        self.create_club_scope(
            club_ticketing,
            ClubAdminScope.Role.TICKETING_OFFICER,
        )
        self.client.force_authenticate(club_ticketing)
        ticketing_response = self.client.get("/api/dashboards/ticketing-officer/")
        self.assertEqual(ticketing_response.status_code, 200)
        self.assertEqual(
            ticketing_response.data["dashboard_role"],
            User.Role.TICKETING_OFFICER,
        )

        django_superuser = self.create_user("django-superuser")
        django_superuser.is_superuser = True
        django_superuser.save(update_fields=["is_superuser"])
        self.client.force_authenticate(django_superuser)
        super_response = self.client.get("/api/dashboards/super-admin/")
        self.assertEqual(super_response.status_code, 200)
        fan_response = self.client.get("/api/dashboards/fan/")
        self.assertEqual(fan_response.status_code, 403)

    def test_sponsor_role_specific_dashboards_select_requested_entitlement(self):
        user = self.create_user(
            "mixed-sponsor",
            role=User.Role.FAN,
            is_sponsor=True,
            sponsor_type=User.SponsorType.INDIVIDUAL,
        )
        account = self.create_individual_sponsor(user)
        self.client.force_authenticate(user)

        expected = {
            "/api/dashboards/me/": (
                User.Role.SPONSOR,
                "/dashboard/sponsor",
                "/api/dashboards/sponsor/",
            ),
            "/api/dashboards/sponsor/": (
                User.Role.SPONSOR,
                "/dashboard/sponsor",
                "/api/dashboards/sponsor/",
            ),
            "/api/dashboards/fan/": (
                User.Role.FAN,
                "/dashboard/fan",
                "/api/dashboards/fan/",
            ),
        }
        contracts = []
        for endpoint, (
            dashboard_role,
            frontend_route,
            backend_route,
        ) in expected.items():
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["dashboard_role"], dashboard_role)
                self.assertEqual(
                    response.data["frontend_dashboard_route"],
                    frontend_route,
                )
                self.assertEqual(
                    response.data["backend_dashboard_route"],
                    backend_route,
                )
                contracts.append(response.data["user"]["dashboard_access"])
                roles = {item["role"] for item in response.data["available_dashboards"]}
                self.assertEqual(roles, {User.Role.SPONSOR, User.Role.FAN})
        self.assertEqual(contracts[0], contracts[1])
        self.assertEqual(contracts[1], contracts[2])
        fan = next(item for item in contracts[0]["entitlements"] if item["id"] == "fan")
        sponsor = next(
            item
            for item in contracts[0]["entitlements"]
            if item["dashboard"] == "SPONSOR"
        )
        self.assertEqual(fan["scope_id"], user.id)
        self.assertEqual(sponsor["scope_id"], account.id)

    @patch("sponsorships.serializers.create_email_verification_otp")
    def test_public_sponsor_registration_does_not_expose_dashboard_access(
        self, create_otp
    ):
        response = self.client.post(
            "/api/sponsorships/register/",
            {
                "sponsor_type": SponsorAccount.SponsorType.INDIVIDUAL,
                "email": "public-sponsor@example.com",
                "phone_number": "0772000000",
                "first_name": "Public",
                "last_name": "Sponsor",
                "password": self.password,
                "confirm_password": self.password,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("dashboard_access", response.data)
        self.assertNotIn("dashboard_access", response.data["user"])
        create_otp.assert_called_once()

    def test_generic_and_union_user_serializers_remain_private(self):
        user = self.create_user("serializer-private")
        membership = self.create_union_membership(user)
        for serializer in (
            UserSerializer(user),
            UserSummarySerializer(user),
            UnionWorkspaceUserSerializer(membership),
        ):
            with self.subTest(serializer=serializer.__class__.__name__):
                self.assertNotIn("dashboard_access", serializer.data)
