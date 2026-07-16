"""Final Django TestCase contract for dashboard entitlement account families."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from accounts.dashboard_entitlements import resolve_dashboard_access
from accounts.models import Club, ClubAdminScope, RoleApproval
from accounts.rbac import CLUB_ADMIN_SUB_ROLE_PERMISSIONS, get_role_permissions
from dashboards.models import (
    Competition,
    League,
    LeagueAdminScope,
    Union,
    UnionWorkspace,
    UnionWorkspaceMembership,
)
from sponsorships.models import SponsorAccount, SponsorAccountMember

User = get_user_model()

INDIVIDUAL_PERMISSIONS = sorted(
    {
        "sponsor.dashboard.view",
        "sponsor.profile.view",
        "sponsor.profile.manage",
        "sponsor.opportunities.view",
        "sponsor.agreements.view",
        "sponsor.agreements.manage",
        "sponsor.campaigns.view",
        "sponsor.campaigns.manage",
        "sponsor.payments.view",
        "sponsor.payments.manage",
        "sponsor.analytics.view",
        "sponsor.settings.manage",
    }
)

CORPORATE_PERMISSIONS = {
    "OWNER": sorted(
        {
            *INDIVIDUAL_PERMISSIONS,
            "sponsor.team.view",
            "sponsor.team.manage",
            "sponsor.ownership.transfer",
        }
    ),
    "ADMIN": sorted(
        {
            "sponsor.dashboard.view",
            "sponsor.profile.view",
            "sponsor.profile.manage",
            "sponsor.team.view",
            "sponsor.team.manage",
            "sponsor.opportunities.view",
            "sponsor.agreements.view",
            "sponsor.agreements.manage",
            "sponsor.campaigns.view",
            "sponsor.campaigns.manage",
            "sponsor.payments.view",
            "sponsor.analytics.view",
        }
    ),
    "FINANCE": sorted(
        {
            "sponsor.dashboard.view",
            "sponsor.profile.view",
            "sponsor.agreements.view",
            "sponsor.payments.view",
            "sponsor.payments.manage",
            "sponsor.analytics.view",
        }
    ),
    "VIEWER": sorted(
        {
            "sponsor.dashboard.view",
            "sponsor.profile.view",
            "sponsor.opportunities.view",
            "sponsor.agreements.view",
            "sponsor.campaigns.view",
            "sponsor.analytics.view",
        }
    ),
}

LEAGUE_PERMISSIONS = {
    "LEAGUE_ADMIN": sorted(
        {
            "dashboard.league_admin",
            "dashboard.me",
            "union.competitions.manage",
            "union.finance.view",
            "union.official.appointments.view",
            "union.reports.view",
            "union.users.manage",
        }
    ),
    "COMPETITION_ADMIN": sorted(
        {
            "dashboard.league_admin",
            "dashboard.me",
            "union.competitions.manage",
            "union.reports.view",
        }
    ),
    "OFFICIALS_COORDINATOR": sorted(
        {
            "dashboard.league_admin",
            "dashboard.me",
            "union.official.appointments.view",
            "union.official.reports.manage",
        }
    ),
    "VIEWER": sorted(
        {
            "dashboard.league_admin",
            "dashboard.me",
            "union.reports.view",
        }
    ),
}


class DashboardEntitlementContractTests(TestCase):
    def setUp(self):
        self.sequence = 0

    def unique(self, prefix):
        self.sequence += 1
        return f"{prefix}-{self.sequence}"

    def create_user(self, prefix, role=User.Role.FAN, **fields):
        value = self.unique(prefix)
        return User.objects.create_user(
            email=f"{value}@example.com",
            password="testpass123",
            first_name="Dashboard",
            last_name="Tester",
            role=role,
            is_email_verified=True,
            **fields,
        )

    def create_union_workspace(self, prefix="union", active=True):
        value = self.unique(prefix)
        union = Union.objects.create(name=f"{value} Union", slug=f"{value}-union")
        return UnionWorkspace.objects.create(
            related_union=union,
            name=f"{value} Workspace",
            slug=f"{value}-workspace",
            acronym=value[:8].upper(),
            sport="Football",
            status=(
                UnionWorkspace.Status.ACTIVE
                if active
                else UnionWorkspace.Status.INACTIVE
            ),
        )

    def create_league(self, prefix="league", active=True):
        value = self.unique(prefix)
        union = Union.objects.create(name=f"{value} Union", slug=f"{value}-union")
        return League.objects.create(
            union=union,
            name=f"{value} League",
            slug=f"{value}-league",
            is_active=active,
        )

    def create_club(self, prefix="club", admin=None):
        value = self.unique(prefix)
        return Club.objects.create(
            name=f"{value} Club", slug=f"{value}-club", admin=admin
        )

    def create_sponsor_account(
        self,
        owner,
        *,
        sponsor_type=SponsorAccount.SponsorType.INDIVIDUAL,
        status=SponsorAccount.Status.APPROVED,
    ):
        value = self.unique("sponsor")
        fields = {}
        if sponsor_type == SponsorAccount.SponsorType.CORPORATE:
            fields["tin"] = f"TIN-{value}"
        return SponsorAccount.objects.create(
            owner=owner,
            sponsor_type=sponsor_type,
            name=f"{value} Account",
            status=status,
            **fields,
        )

    def add_corporate_membership(
        self,
        user,
        *,
        account=None,
        role=SponsorAccountMember.MemberRole.OWNER,
        active=True,
        status=SponsorAccount.Status.APPROVED,
    ):
        account = account or self.create_sponsor_account(
            user,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            status=status,
        )
        membership = SponsorAccountMember.objects.create(
            sponsor_account=account,
            user=user,
            member_role=role,
            is_active=active,
        )
        return account, membership

    def add_union_scope(
        self,
        user,
        *,
        role=UnionWorkspaceMembership.Role.UNION_ADMIN,
        active=True,
        workspace=None,
    ):
        workspace = workspace or self.create_union_workspace("union-scope")
        return UnionWorkspaceMembership.objects.create(
            user=user,
            workspace=workspace,
            role=role,
            is_active=active,
        )

    def add_league_scope(
        self,
        user,
        *,
        league=None,
        role=LeagueAdminScope.Role.LEAGUE_ADMIN,
        active=True,
        competition=None,
    ):
        league = league or self.create_league("league-scope")
        return LeagueAdminScope.objects.create(
            user=user,
            league=league,
            role=role,
            is_active=active,
            competition=competition,
        )

    def add_club_scope(
        self, user, *, club=None, role=ClubAdminScope.Role.CLUB_ADMIN, active=True
    ):
        return ClubAdminScope.objects.create(
            user=user,
            club=club or self.create_club("club-scope"),
            role=role,
            is_active=active,
        )

    def assert_contract(self, access, *, default_id, entitlements):
        self.assertEqual(
            set(access),
            {"version", "default_entitlement_id", "entitlements"},
        )
        self.assertEqual(access["version"], 1)
        self.assertEqual(access["default_entitlement_id"], default_id)
        self.assertEqual(access["entitlements"], entitlements)
        ids = [item["id"] for item in entitlements]
        self.assertEqual(len(ids), len(set(ids)))
        if default_id is None:
            self.assertEqual(entitlements, [])
        else:
            self.assertIn(default_id, ids)
        for item in entitlements:
            self.assertEqual(
                set(item),
                {
                    "id",
                    "dashboard",
                    "route",
                    "scope_type",
                    "scope_id",
                    "workspace_role",
                    "permissions",
                },
            )
            self.assertEqual(item["permissions"], sorted(set(item["permissions"])))

    def assert_empty(self, user):
        self.assert_contract(
            resolve_dashboard_access(user),
            default_id=None,
            entitlements=[],
        )

    def fan(self, user):
        return {
            "id": "fan",
            "dashboard": "FAN",
            "route": "/dashboard/fan",
            "scope_type": "ACCOUNT",
            "scope_id": user.id,
            "workspace_role": None,
            "permissions": [],
        }

    def individual(self, account, legacy_user=None):
        return {
            "id": (
                "individual-sponsor-legacy"
                if legacy_user
                else f"individual-sponsor-{account.id}"
            ),
            "dashboard": "SPONSOR",
            "route": "/dashboard/sponsor",
            "scope_type": "INDIVIDUAL_SPONSOR_ACCOUNT",
            "scope_id": legacy_user.id if legacy_user else account.id,
            "workspace_role": "OWNER",
            "permissions": INDIVIDUAL_PERMISSIONS,
        }

    def corporate(self, account, role):
        return {
            "id": f"corporate-sponsor-{account.id}",
            "dashboard": "SPONSOR",
            "route": "/dashboard/sponsor",
            "scope_type": "CORPORATE_SPONSOR_WORKSPACE",
            "scope_id": account.id,
            "workspace_role": role,
            "permissions": CORPORATE_PERMISSIONS[role],
        }

    def union(self, membership):
        return {
            "id": f"union-workspace-{membership.workspace_id}",
            "dashboard": "UNION_WORKSPACE",
            "route": "/dashboard/union-admin",
            "scope_type": "UNION_WORKSPACE",
            "scope_id": membership.workspace_id,
            "workspace_role": membership.role,
            "permissions": membership.effective_permissions,
        }

    def league(self, scope):
        return {
            "id": f"league-scope-{scope.id}",
            "dashboard": "LEAGUE_ADMIN",
            "route": "/dashboard/league-admin",
            "scope_type": "COMPETITION" if scope.competition_id else "LEAGUE",
            "scope_id": scope.competition_id or scope.league_id,
            "workspace_role": scope.role,
            "permissions": LEAGUE_PERMISSIONS[scope.role],
        }

    def club(self, scope):
        ticketing = scope.role == ClubAdminScope.Role.TICKETING_OFFICER
        permissions = set(CLUB_ADMIN_SUB_ROLE_PERMISSIONS[scope.role])
        if ticketing:
            permissions.discard("dashboard.club_admin")
            permissions.add("dashboard.ticketing_officer")
        return {
            "id": f"club-scope-{scope.id}",
            "dashboard": "TICKETING_OFFICER" if ticketing else "CLUB_ADMIN",
            "route": (
                "/dashboard/ticketing-officer" if ticketing else "/dashboard/club-admin"
            ),
            "scope_type": "CLUB",
            "scope_id": scope.club_id,
            "workspace_role": scope.role,
            "permissions": sorted(permissions),
        }

    def test_fan_and_invalid_identity_contracts(self):
        fan_user = self.create_user("fan")
        self.assert_contract(
            resolve_dashboard_access(fan_user),
            default_id="fan",
            entitlements=[self.fan(fan_user)],
        )
        inactive = self.create_user("inactive", is_active=False)
        self.assert_empty(inactive)
        self.assert_empty(None)
        self.assert_empty(AnonymousUser())
        for invalid_role in ("", "UNKNOWN"):
            with self.subTest(role=invalid_role):
                user = self.create_user(f"invalid-{invalid_role or 'blank'}")
                User.objects.filter(pk=user.pk).update(role=invalid_role)
                user.refresh_from_db()
                self.assert_empty(user)

    def test_approved_individual_owner_receives_sponsor_and_personal_fan(self):
        user = self.create_user("individual")
        account = self.create_sponsor_account(user)
        self.assert_contract(
            resolve_dashboard_access(user),
            default_id=f"individual-sponsor-{account.id}",
            entitlements=[self.individual(account), self.fan(user)],
        )
        permissions = self.individual(account)["permissions"]
        self.assertNotIn("sponsor.team.view", permissions)
        self.assertNotIn("sponsor.team.manage", permissions)
        self.assertNotIn("sponsor.workspace.manage", permissions)
        self.assertNotIn("sponsor.ownership.transfer", permissions)

    def test_individual_member_does_not_gain_owner_profile(self):
        owner = self.create_user("individual-owner")
        member = self.create_user("individual-member")
        account = self.create_sponsor_account(owner)
        SponsorAccountMember.objects.create(
            sponsor_account=account,
            user=member,
            member_role=SponsorAccountMember.MemberRole.ADMIN,
        )
        self.assert_contract(
            resolve_dashboard_access(member),
            default_id="fan",
            entitlements=[self.fan(member)],
        )

    def test_unapproved_individual_accounts_do_not_grant_sponsor(self):
        for status in (SponsorAccount.Status.PENDING, SponsorAccount.Status.REJECTED):
            with self.subTest(status=status):
                user = self.create_user(f"individual-{status.lower()}")
                self.create_sponsor_account(user, status=status)
                self.assert_contract(
                    resolve_dashboard_access(user),
                    default_id="fan",
                    entitlements=[self.fan(user)],
                )

    def test_legacy_individual_compatibility_and_corporate_flag_rejection(self):
        for source in ("role", "flag"):
            with self.subTest(source=source):
                fields = {"sponsor_type": User.SponsorType.INDIVIDUAL}
                if source == "role":
                    fields["role"] = User.Role.SPONSOR
                else:
                    fields["is_sponsor"] = True
                user = self.create_user(f"legacy-{source}", **fields)
                self.assert_contract(
                    resolve_dashboard_access(user),
                    default_id="individual-sponsor-legacy",
                    entitlements=[self.individual(None, user), self.fan(user)],
                )
        corporate_flag = self.create_user(
            "legacy-corporate",
            is_sponsor=True,
            sponsor_type=User.SponsorType.CORPORATE,
        )
        self.assert_contract(
            resolve_dashboard_access(corporate_flag),
            default_id="fan",
            entitlements=[self.fan(corporate_flag)],
        )

    def test_corporate_permission_matrix_and_complete_entitlements(self):
        for role, _label in SponsorAccountMember.MemberRole.choices:
            with self.subTest(role=role):
                user = self.create_user(f"corporate-{role.lower()}")
                account, _membership = self.add_corporate_membership(user, role=role)
                self.assert_contract(
                    resolve_dashboard_access(user),
                    default_id=f"corporate-sponsor-{account.id}",
                    entitlements=[self.corporate(account, role), self.fan(user)],
                )

    def test_invalid_or_inactive_corporate_membership_preserves_personal_fan(self):
        for case in ("invalid-role", "inactive", "pending", "rejected"):
            with self.subTest(case=case):
                user = self.create_user(f"corporate-{case}")
                status = {
                    "pending": SponsorAccount.Status.PENDING,
                    "rejected": SponsorAccount.Status.REJECTED,
                }.get(case, SponsorAccount.Status.APPROVED)
                account, membership = self.add_corporate_membership(
                    user,
                    active=case != "inactive",
                    status=status,
                )
                if case == "invalid-role":
                    SponsorAccountMember.objects.filter(pk=membership.pk).update(
                        member_role="INVALID"
                    )
                self.assert_contract(
                    resolve_dashboard_access(user),
                    default_id="fan",
                    entitlements=[self.fan(user)],
                )
                self.assertIsNotNone(account.id)

    def test_corporate_members_share_workspace_but_not_fan_identity(self):
        owner = self.create_user("corp-owner")
        member = self.create_user("corp-member")
        account = self.create_sponsor_account(
            owner,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
        )
        self.add_corporate_membership(owner, account=account)
        self.add_corporate_membership(
            member,
            account=account,
            role=SponsorAccountMember.MemberRole.FINANCE,
        )
        owner_access = resolve_dashboard_access(owner)
        member_access = resolve_dashboard_access(member)
        self.assertEqual(owner_access["entitlements"][0]["scope_id"], account.id)
        self.assertEqual(member_access["entitlements"][0]["scope_id"], account.id)
        self.assertNotEqual(
            owner_access["entitlements"][1]["scope_id"],
            member_access["entitlements"][1]["scope_id"],
        )

    def test_multiple_corporate_workspaces_are_deterministic_with_one_fan(self):
        user = self.create_user("multi-corporate")
        first, _ = self.add_corporate_membership(user)
        second, _ = self.add_corporate_membership(
            user,
            role=SponsorAccountMember.MemberRole.ADMIN,
        )
        self.assert_contract(
            resolve_dashboard_access(user),
            default_id=f"corporate-sponsor-{first.id}",
            entitlements=[
                self.corporate(first, SponsorAccountMember.MemberRole.OWNER),
                self.corporate(second, SponsorAccountMember.MemberRole.ADMIN),
                self.fan(user),
            ],
        )

    def test_individual_and_corporate_sponsor_conflict_fails_closed(self):
        user = self.create_user("mixed-sponsor")
        self.create_sponsor_account(user)
        self.add_corporate_membership(user)
        self.assert_empty(user)

    def test_multiple_approved_individual_accounts_fail_closed(self):
        user = self.create_user(
            "ambiguous-individual",
            role=User.Role.SPONSOR,
            sponsor_type=User.SponsorType.INDIVIDUAL,
        )
        self.create_sponsor_account(user)
        self.create_sponsor_account(user)
        self.assert_empty(user)

    def test_sponsor_humans_keep_fan_when_workspace_is_unavailable(self):
        for primary_role in (User.Role.SPONSOR, User.Role.FAN):
            for status in (
                SponsorAccount.Status.PENDING,
                SponsorAccount.Status.REJECTED,
            ):
                with self.subTest(
                    sponsor_type="individual",
                    primary_role=primary_role,
                    status=status,
                ):
                    user = self.create_user(
                        f"individual-fallback-{primary_role}-{status}",
                        role=primary_role,
                        sponsor_type=User.SponsorType.INDIVIDUAL,
                    )
                    self.create_sponsor_account(user, status=status)
                    self.assert_contract(
                        resolve_dashboard_access(user),
                        default_id="fan",
                        entitlements=[self.fan(user)],
                    )

            for case in ("inactive", "pending", "rejected"):
                with self.subTest(
                    sponsor_type="corporate",
                    primary_role=primary_role,
                    case=case,
                ):
                    user = self.create_user(
                        f"corporate-fallback-{primary_role}-{case}",
                        role=primary_role,
                        sponsor_type=User.SponsorType.CORPORATE,
                    )
                    status = {
                        "pending": SponsorAccount.Status.PENDING,
                        "rejected": SponsorAccount.Status.REJECTED,
                    }.get(case, SponsorAccount.Status.APPROVED)
                    self.add_corporate_membership(
                        user,
                        active=case != "inactive",
                        status=status,
                    )
                    self.assert_contract(
                        resolve_dashboard_access(user),
                        default_id="fan",
                        entitlements=[self.fan(user)],
                    )

        malformed = self.create_user("malformed-sponsor", role=User.Role.SPONSOR)
        self.assert_empty(malformed)

    def test_super_admin_contract_and_family_conflicts(self):
        user = self.create_user("super", role=User.Role.SUPER_ADMIN)
        expected = {
            "id": "super-admin",
            "dashboard": "SUPER_ADMIN",
            "route": "/dashboard/super-admin",
            "scope_type": "ACCOUNT",
            "scope_id": user.id,
            "workspace_role": User.Role.SUPER_ADMIN,
            "permissions": sorted(get_role_permissions(User.Role.SUPER_ADMIN)),
        }
        self.assert_contract(
            resolve_dashboard_access(user),
            default_id="super-admin",
            entitlements=[expected],
        )
        for family in ("sponsor", "union", "league", "club"):
            with self.subTest(family=family):
                conflict = self.create_user(
                    f"super-{family}", role=User.Role.SUPER_ADMIN
                )
                self.add_family(conflict, family)
                self.assert_empty(conflict)

    def test_django_superuser_and_staff_classification(self):
        for stored_role in (User.Role.SUPER_ADMIN, User.Role.FAN):
            with self.subTest(stored_role=stored_role):
                user = self.create_user(
                    f"django-super-{stored_role}",
                    role=stored_role,
                    is_superuser=True,
                    is_staff=True,
                )
                access = resolve_dashboard_access(user)
                self.assertEqual(access["default_entitlement_id"], "super-admin")
                self.assertEqual(
                    [item["dashboard"] for item in access["entitlements"]],
                    ["SUPER_ADMIN"],
                )
        staff = self.create_user("ordinary-staff", is_staff=True)
        self.assert_contract(
            resolve_dashboard_access(staff),
            default_id="fan",
            entitlements=[self.fan(staff)],
        )

    def test_every_union_role_and_multiple_workspaces(self):
        for role, _label in UnionWorkspaceMembership.Role.choices:
            with self.subTest(role=role):
                user = self.create_user(f"union-{role.lower()}")
                membership = self.add_union_scope(user, role=role)
                self.assert_contract(
                    resolve_dashboard_access(user),
                    default_id=f"union-workspace-{membership.workspace_id}",
                    entitlements=[self.union(membership)],
                )
        user = self.create_user("multi-union")
        first = self.add_union_scope(user)
        second = self.add_union_scope(
            user,
            role=UnionWorkspaceMembership.Role.MATCH_OFFICIAL,
        )
        expected = sorted([first, second], key=lambda item: item.workspace_id)
        self.assert_contract(
            resolve_dashboard_access(user),
            default_id=f"union-workspace-{expected[0].workspace_id}",
            entitlements=[self.union(item) for item in expected],
        )

    def test_invalid_or_inactive_union_scope_and_unscoped_roles_fail_closed(self):
        for case in ("inactive-membership", "inactive-workspace", "invalid-role"):
            with self.subTest(case=case):
                user = self.create_user(f"union-{case}")
                workspace = self.create_union_workspace(
                    case,
                    active=case != "inactive-workspace",
                )
                membership = self.add_union_scope(
                    user,
                    workspace=workspace,
                    active=case != "inactive-membership",
                )
                if case == "invalid-role":
                    UnionWorkspaceMembership.objects.filter(pk=membership.pk).update(
                        role="INVALID"
                    )
                self.assert_contract(
                    resolve_dashboard_access(user),
                    default_id=None,
                    entitlements=[],
                )
        for role in (
            User.Role.UNION_ADMIN,
            User.Role.REFEREE,
            User.Role.TICKETING_OFFICER,
        ):
            with self.subTest(unscoped_role=role):
                self.assert_empty(
                    self.create_user(f"unscoped-{role.lower()}", role=role)
                )

    def test_legacy_and_primary_union_scoped_roles(self):
        cases = (
            (User.Role.FAN, UnionWorkspaceMembership.Role.REGISTRAR),
            (User.Role.REFEREE, UnionWorkspaceMembership.Role.MATCH_OFFICIAL),
            (
                User.Role.TICKETING_OFFICER,
                UnionWorkspaceMembership.Role.TICKETING_OFFICER,
            ),
        )
        for primary_role, workspace_role in cases:
            with self.subTest(primary_role=primary_role, workspace_role=workspace_role):
                user = self.create_user(
                    f"scoped-{primary_role.lower()}", role=primary_role
                )
                membership = self.add_union_scope(user, role=workspace_role)
                self.assert_contract(
                    resolve_dashboard_access(user),
                    default_id=f"union-workspace-{membership.workspace_id}",
                    entitlements=[self.union(membership)],
                )

    def test_league_scope_matrix_and_ordering(self):
        for role, _label in LeagueAdminScope.Role.choices:
            with self.subTest(role=role):
                user = self.create_user(f"league-{role.lower()}")
                league = self.create_league(role.lower())
                competition = None
                if role == LeagueAdminScope.Role.COMPETITION_ADMIN:
                    competition = Competition.objects.create(
                        league=league,
                        name=self.unique("Competition"),
                        slug=self.unique("competition"),
                        season="2026/27",
                    )
                scope = self.add_league_scope(
                    user,
                    league=league,
                    role=role,
                    competition=competition,
                )
                self.assert_contract(
                    resolve_dashboard_access(user),
                    default_id=f"league-scope-{scope.id}",
                    entitlements=[self.league(scope)],
                )
                permissions = self.league(scope)["permissions"]
                if role == LeagueAdminScope.Role.VIEWER:
                    self.assertNotIn("union.competitions.manage", permissions)
                    self.assertNotIn("union.users.manage", permissions)
                    self.assertNotIn("union.finance.view", permissions)
                    self.assertNotIn("union.official.reports.manage", permissions)
                if role == LeagueAdminScope.Role.OFFICIALS_COORDINATOR:
                    self.assertNotIn("union.competitions.manage", permissions)
                    self.assertNotIn("union.users.manage", permissions)
                    self.assertNotIn("union.finance.view", permissions)
        user = self.create_user("multi-league")
        first = self.add_league_scope(user)
        second = self.add_league_scope(user)
        self.assert_contract(
            resolve_dashboard_access(user),
            default_id=f"league-scope-{first.id}",
            entitlements=[self.league(first), self.league(second)],
        )

    def test_invalid_league_scopes_and_unscoped_admin_fail_closed(self):
        for case in (
            "inactive-scope",
            "inactive-league",
            "inactive-competition",
            "mismatched-competition",
            "invalid-role",
        ):
            with self.subTest(case=case):
                user = self.create_user(f"league-{case}")
                league = self.create_league(case, active=case != "inactive-league")
                competition = None
                if case in ("inactive-competition", "mismatched-competition"):
                    competition_league = (
                        self.create_league("other")
                        if case == "mismatched-competition"
                        else league
                    )
                    competition = Competition.objects.create(
                        league=competition_league,
                        name=self.unique("Competition"),
                        slug=self.unique("competition"),
                        season="2026/27",
                        is_active=case != "inactive-competition",
                    )
                scope = self.add_league_scope(
                    user,
                    league=league,
                    active=case != "inactive-scope",
                    competition=competition,
                )
                if case == "invalid-role":
                    LeagueAdminScope.objects.filter(pk=scope.pk).update(role="INVALID")
                self.assert_contract(
                    resolve_dashboard_access(user),
                    default_id=None,
                    entitlements=[],
                )
        self.assert_empty(
            self.create_user("unscoped-league", role=User.Role.LEAGUE_ADMIN)
        )

    def test_legacy_fan_plus_league_scope_returns_league_only(self):
        user = self.create_user("legacy-league")
        scope = self.add_league_scope(user)
        self.assert_contract(
            resolve_dashboard_access(user),
            default_id=f"league-scope-{scope.id}",
            entitlements=[self.league(scope)],
        )

    def test_club_scope_roles_direct_links_and_ordering(self):
        for role, _label in ClubAdminScope.Role.choices:
            with self.subTest(role=role):
                user = self.create_user(f"club-{role.lower()}")
                scope = self.add_club_scope(user, role=role)
                self.assert_contract(
                    resolve_dashboard_access(user),
                    default_id=f"club-scope-{scope.id}",
                    entitlements=[self.club(scope)],
                )
        for association in ("user-club", "club-admin"):
            with self.subTest(association=association):
                user = self.create_user(
                    f"direct-{association}", role=User.Role.CLUB_ADMIN
                )
                club = self.create_club(association)
                if association == "user-club":
                    user.club = club
                    user.save(update_fields=["club"])
                else:
                    club.admin = user
                    club.save(update_fields=["admin"])
                access = resolve_dashboard_access(user)
                self.assertEqual(access["default_entitlement_id"], f"club-{club.id}")
                self.assertEqual(access["entitlements"][0]["scope_id"], club.id)
                self.assert_contract(
                    access,
                    default_id=f"club-{club.id}",
                    entitlements=access["entitlements"],
                )
        user = self.create_user("multi-club")
        first = self.add_club_scope(user)
        second = self.add_club_scope(user, role=ClubAdminScope.Role.TREASURER)
        self.assert_contract(
            resolve_dashboard_access(user),
            default_id=f"club-scope-{first.id}",
            entitlements=[self.club(first), self.club(second)],
        )

    def test_invalid_inactive_duplicate_and_unscoped_club_cases(self):
        inactive_user = self.create_user("inactive-club")
        self.add_club_scope(inactive_user, active=False)
        self.assert_contract(
            resolve_dashboard_access(inactive_user),
            default_id=None,
            entitlements=[],
        )
        invalid_user = self.create_user("invalid-club")
        invalid_scope = self.add_club_scope(invalid_user)
        ClubAdminScope.objects.filter(pk=invalid_scope.pk).update(role="INVALID")
        self.assert_contract(
            resolve_dashboard_access(invalid_user),
            default_id=None,
            entitlements=[],
        )
        duplicate_user = self.create_user("duplicate-club", role=User.Role.CLUB_ADMIN)
        club = self.create_club("duplicate", admin=duplicate_user)
        duplicate_user.club = club
        duplicate_user.save(update_fields=["club"])
        scope = self.add_club_scope(duplicate_user, club=club)
        self.assert_contract(
            resolve_dashboard_access(duplicate_user),
            default_id=f"club-scope-{scope.id}",
            entitlements=[self.club(scope)],
        )
        for role in (User.Role.CLUB_ADMIN, User.Role.TICKETING_OFFICER):
            with self.subTest(role=role):
                self.assert_empty(
                    self.create_user(f"unscoped-{role.lower()}", role=role)
                )

    def test_club_ticketing_permission_replacement_and_legacy_scope(self):
        for primary_role in (User.Role.TICKETING_OFFICER, User.Role.FAN):
            with self.subTest(primary_role=primary_role):
                user = self.create_user(
                    f"ticket-{primary_role.lower()}", role=primary_role
                )
                scope = self.add_club_scope(
                    user,
                    role=ClubAdminScope.Role.TICKETING_OFFICER,
                )
                expected = self.club(scope)
                self.assertIn("dashboard.ticketing_officer", expected["permissions"])
                self.assertNotIn("dashboard.club_admin", expected["permissions"])
                self.assert_contract(
                    resolve_dashboard_access(user),
                    default_id=f"club-scope-{scope.id}",
                    entitlements=[expected],
                )

    def add_family(self, user, family):
        if family == "sponsor":
            self.create_sponsor_account(user)
        elif family == "union":
            self.add_union_scope(user)
        elif family == "league":
            self.add_league_scope(user)
        elif family == "club":
            self.add_club_scope(user)
        else:
            raise AssertionError(f"Unknown family {family}")

    def test_cross_family_conflicts_fail_closed(self):
        pairs = (
            ("sponsor", "union"),
            ("sponsor", "league"),
            ("sponsor", "club"),
            ("union", "league"),
            ("union", "club"),
            ("league", "club"),
        )
        for first, second in pairs:
            with self.subTest(first=first, second=second):
                user = self.create_user(f"conflict-{first}-{second}")
                self.add_family(user, first)
                self.add_family(user, second)
                self.assert_empty(user)
        user = self.create_user("three-families")
        for family in ("union", "league", "club"):
            self.add_family(user, family)
        self.assert_empty(user)
        ticket_user = self.create_user(
            "ticket-conflict", role=User.Role.TICKETING_OFFICER
        )
        self.add_union_scope(
            ticket_user,
            role=UnionWorkspaceMembership.Role.TICKETING_OFFICER,
        )
        self.add_club_scope(
            ticket_user,
            role=ClubAdminScope.Role.TICKETING_OFFICER,
        )
        self.assert_empty(ticket_user)

    def test_declared_roles_only_resolve_compatible_families(self):
        mismatches = (
            (User.Role.UNION_ADMIN, "league"),
            (User.Role.UNION_ADMIN, "club"),
            (User.Role.LEAGUE_ADMIN, "union"),
            (User.Role.LEAGUE_ADMIN, "club"),
            (User.Role.CLUB_ADMIN, "union"),
            (User.Role.CLUB_ADMIN, "league"),
            (User.Role.SPONSOR, "union"),
            (User.Role.SPONSOR, "league"),
            (User.Role.SPONSOR, "club"),
        )
        for role, family in mismatches:
            with self.subTest(role=role, family=family):
                user = self.create_user(f"mismatch-{role}-{family}", role=role)
                self.add_family(user, family)
                self.assert_empty(user)

        scoped_roles = (
            (
                User.Role.REFEREE,
                UnionWorkspaceMembership.Role.VIEWER,
                False,
            ),
            (
                User.Role.REFEREE,
                UnionWorkspaceMembership.Role.MATCH_OFFICIAL,
                True,
            ),
            (
                User.Role.TICKETING_OFFICER,
                UnionWorkspaceMembership.Role.VIEWER,
                False,
            ),
            (
                User.Role.TICKETING_OFFICER,
                UnionWorkspaceMembership.Role.TICKETING_OFFICER,
                True,
            ),
        )
        for primary_role, workspace_role, allowed in scoped_roles:
            with self.subTest(
                primary_role=primary_role,
                workspace_role=workspace_role,
            ):
                user = self.create_user(
                    f"union-compat-{primary_role}-{workspace_role}",
                    role=primary_role,
                )
                membership = self.add_union_scope(user, role=workspace_role)
                if allowed:
                    self.assert_contract(
                        resolve_dashboard_access(user),
                        default_id=f"union-workspace-{membership.workspace_id}",
                        entitlements=[self.union(membership)],
                    )
                else:
                    self.assert_empty(user)

        normal_club = self.create_user(
            "ticket-normal-club", role=User.Role.TICKETING_OFFICER
        )
        self.add_club_scope(normal_club, role=ClubAdminScope.Role.CLUB_ADMIN)
        self.assert_empty(normal_club)

        for invalid_role in ("", "UNKNOWN"):
            with self.subTest(invalid_role=invalid_role):
                user = self.create_user(f"invalid-scoped-{invalid_role or 'blank'}")
                self.add_union_scope(user)
                User.objects.filter(pk=user.pk).update(role=invalid_role)
                user.refresh_from_db()
                self.assert_empty(user)

    def test_role_approvals_preserve_existing_active_family_access(self):
        requester = self.create_user("requester", role=User.Role.SUPER_ADMIN)
        reviewer = self.create_user("reviewer", role=User.Role.SUPER_ADMIN)
        cases = (
            ("fan-pending", RoleApproval.Status.PENDING, "fan"),
            ("fan-rejected", RoleApproval.Status.REJECTED, "fan"),
            ("sponsor-rejected", RoleApproval.Status.REJECTED, "sponsor"),
            ("union-pending", RoleApproval.Status.PENDING, "union"),
        )
        for label, status, family in cases:
            with self.subTest(label=label):
                user = self.create_user(label)
                family_object = None
                if family != "fan":
                    if family == "sponsor":
                        family_object = self.create_sponsor_account(user)
                    elif family == "union":
                        family_object = self.add_union_scope(user)
                RoleApproval.objects.create(
                    target_user=user,
                    requested_role=User.Role.SUPER_ADMIN,
                    requested_by=requester,
                    reviewed_by=(
                        reviewer if status == RoleApproval.Status.REJECTED else None
                    ),
                    status=status,
                    rejection_reason=(
                        "Rejected" if status == RoleApproval.Status.REJECTED else ""
                    ),
                )
                access = resolve_dashboard_access(user)
                if family == "fan":
                    self.assert_contract(
                        access,
                        default_id="fan",
                        entitlements=[self.fan(user)],
                    )
                elif family == "sponsor":
                    self.assert_contract(
                        access,
                        default_id=f"individual-sponsor-{family_object.id}",
                        entitlements=[self.individual(family_object), self.fan(user)],
                    )
                else:
                    self.assert_contract(
                        access,
                        default_id=f"union-workspace-{family_object.workspace_id}",
                        entitlements=[self.union(family_object)],
                    )

    def test_provisional_and_unapplied_approved_role_requests(self):
        requester = self.create_user("approval-requester", role=User.Role.SUPER_ADMIN)
        reviewer = self.create_user("approval-reviewer", role=User.Role.SUPER_ADMIN)
        provisional = self.create_user("provisional", is_active=False)
        RoleApproval.objects.create(
            target_user=provisional,
            requested_role=User.Role.UNION_ADMIN,
            requested_by=requester,
        )
        self.assert_empty(provisional)
        active_fan = self.create_user("approved-not-applied")
        RoleApproval.objects.create(
            target_user=active_fan,
            requested_role=User.Role.UNION_ADMIN,
            requested_by=requester,
            reviewed_by=reviewer,
            status=RoleApproval.Status.APPROVED,
        )
        self.assert_contract(
            resolve_dashboard_access(active_fan),
            default_id="fan",
            entitlements=[self.fan(active_fan)],
        )
