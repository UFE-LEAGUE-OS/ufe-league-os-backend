"""Backend-owned dashboard entitlement resolution for League OS accounts."""

from .models import Club, ClubAdminScope, User
from .rbac import CLUB_ADMIN_SUB_ROLE_PERMISSIONS, get_role_permissions

ACCESS_VERSION = 1

INDIVIDUAL_SPONSOR_PERMISSIONS = {
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

CORPORATE_SPONSOR_PERMISSIONS = {
    "OWNER": {
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
        "sponsor.payments.manage",
        "sponsor.analytics.view",
        "sponsor.settings.manage",
        "sponsor.ownership.transfer",
    },
    "ADMIN": {
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
    },
    "FINANCE": {
        "sponsor.dashboard.view",
        "sponsor.profile.view",
        "sponsor.agreements.view",
        "sponsor.payments.view",
        "sponsor.payments.manage",
        "sponsor.analytics.view",
    },
    "VIEWER": {
        "sponsor.dashboard.view",
        "sponsor.profile.view",
        "sponsor.opportunities.view",
        "sponsor.agreements.view",
        "sponsor.campaigns.view",
        "sponsor.analytics.view",
    },
}

LEAGUE_SCOPE_ROLE_PERMISSIONS = {
    "LEAGUE_ADMIN": {
        "dashboard.league_admin",
        "dashboard.me",
        "union.competitions.manage",
        "union.finance.view",
        "union.official.appointments.view",
        "union.reports.view",
        "union.users.manage",
    },
    "COMPETITION_ADMIN": {
        "dashboard.league_admin",
        "dashboard.me",
        "union.competitions.manage",
        "union.reports.view",
    },
    "OFFICIALS_COORDINATOR": {
        "dashboard.league_admin",
        "dashboard.me",
        "union.official.appointments.view",
        "union.official.reports.manage",
    },
    "VIEWER": {
        "dashboard.league_admin",
        "dashboard.me",
        "union.reports.view",
    },
}


def _empty_access():
    return {
        "version": ACCESS_VERSION,
        "default_entitlement_id": None,
        "entitlements": [],
    }


def _entitlement(
    *,
    entitlement_id,
    dashboard,
    route,
    scope_type,
    scope_id,
    workspace_role,
    permissions,
):
    return {
        "id": entitlement_id,
        "dashboard": dashboard,
        "route": route,
        "scope_type": scope_type,
        "scope_id": scope_id,
        "workspace_role": workspace_role,
        "permissions": sorted(set(permissions)),
    }


def _fan_entitlement(user):
    return _entitlement(
        entitlement_id="fan",
        dashboard="FAN",
        route="/dashboard/fan",
        scope_type="ACCOUNT",
        scope_id=user.id,
        workspace_role=None,
        permissions=(),
    )


def _resolve_individual_sponsor_entitlements(user):
    from sponsorships.models import SponsorAccount

    accounts = list(
        SponsorAccount.objects.filter(
            owner=user,
            sponsor_type=SponsorAccount.SponsorType.INDIVIDUAL,
            status__in=(
                SponsorAccount.Status.PENDING,
                SponsorAccount.Status.APPROVED,
            ),
        ).order_by("id")
    )
    if len(accounts) > 1:
        return [], True
    if accounts:
        account = accounts[0]
        return [
            _entitlement(
                entitlement_id=f"individual-sponsor-{account.id}",
                dashboard="SPONSOR",
                route="/sponsor/dashboard",
                scope_type="INDIVIDUAL_SPONSOR_ACCOUNT",
                scope_id=account.id,
                workspace_role="OWNER",
                permissions=INDIVIDUAL_SPONSOR_PERMISSIONS,
            )
        ], False

    has_contradicting_account = SponsorAccount.objects.filter(
        owner=user,
        status=SponsorAccount.Status.REJECTED,
    ).exists()
    is_legacy_individual = (
        user.role == User.Role.SPONSOR or bool(user.is_sponsor)
    ) and user.sponsor_type == User.SponsorType.INDIVIDUAL
    if is_legacy_individual and not has_contradicting_account:
        return [
            _entitlement(
                entitlement_id="individual-sponsor-legacy",
                dashboard="SPONSOR",
                route="/sponsor/dashboard",
                scope_type="INDIVIDUAL_SPONSOR_ACCOUNT",
                scope_id=user.id,
                workspace_role="OWNER",
                permissions=INDIVIDUAL_SPONSOR_PERMISSIONS,
            )
        ], False

    return [], False


def _resolve_corporate_sponsor_entitlements(user):
    from sponsorships.models import SponsorAccount, SponsorAccountMember

    valid_roles = {value for value, _label in SponsorAccountMember.MemberRole.choices}
    memberships = (
        SponsorAccountMember.objects.filter(
            user=user,
            is_active=True,
            sponsor_account__sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            sponsor_account__status__in=(
                SponsorAccount.Status.PENDING,
                SponsorAccount.Status.APPROVED,
            ),
            member_role__in=valid_roles,
        )
        .select_related("sponsor_account")
        .order_by("sponsor_account_id", "id")
    )
    seen_accounts = set()
    entitlements = []
    for membership in memberships:
        if membership.sponsor_account_id in seen_accounts:
            continue
        seen_accounts.add(membership.sponsor_account_id)
        entitlements.append(
            _entitlement(
                entitlement_id=f"corporate-sponsor-{membership.sponsor_account_id}",
                dashboard="SPONSOR",
                route="/sponsor/dashboard",
                scope_type="CORPORATE_SPONSOR_WORKSPACE",
                scope_id=membership.sponsor_account_id,
                workspace_role=membership.member_role,
                permissions=CORPORATE_SPONSOR_PERMISSIONS[membership.member_role],
            )
        )
    return entitlements


def _resolve_super_admin_entitlements(user):
    if user.role != User.Role.SUPER_ADMIN and not user.is_superuser:
        return []
    return [
        _entitlement(
            entitlement_id="super-admin",
            dashboard="SUPER_ADMIN",
            route="/dashboard/super-admin",
            scope_type="ACCOUNT",
            scope_id=user.id,
            workspace_role=User.Role.SUPER_ADMIN,
            permissions=get_role_permissions(User.Role.SUPER_ADMIN),
        )
    ]


def _resolve_union_entitlements(user):
    from dashboards.models import UnionWorkspace, UnionWorkspaceMembership

    valid_roles = {value for value, _label in UnionWorkspaceMembership.Role.choices}
    memberships = (
        UnionWorkspaceMembership.objects.filter(
            user=user,
            is_active=True,
            workspace__status=UnionWorkspace.Status.ACTIVE,
            role__in=valid_roles,
        )
        .select_related("workspace")
        .order_by("workspace_id", "id")
    )
    seen_workspaces = set()
    entitlements = []
    for membership in memberships:
        if membership.workspace_id in seen_workspaces:
            continue
        seen_workspaces.add(membership.workspace_id)
        route = "/dashboard/union-admin"
        if membership.role == UnionWorkspaceMembership.Role.MATCH_OFFICIAL:
            route = "/dashboard/referee"
        elif membership.role == UnionWorkspaceMembership.Role.TICKETING_OFFICER:
            route = "/dashboard/ticketing-officer"
        entitlements.append(
            _entitlement(
                entitlement_id=f"union-workspace-{membership.workspace_id}",
                dashboard="UNION_WORKSPACE",
                route=route,
                scope_type="UNION_WORKSPACE",
                scope_id=membership.workspace_id,
                workspace_role=membership.role,
                permissions=membership.effective_permissions,
            )
        )
    return entitlements


def _filter_union_entitlements(entitlements, allowed_roles):
    return [item for item in entitlements if item["workspace_role"] in allowed_roles]


def _resolve_league_entitlements(user):
    from dashboards.models import LeagueAdminScope

    valid_roles = {value for value, _label in LeagueAdminScope.Role.choices}
    scopes = (
        LeagueAdminScope.objects.filter(
            user=user,
            is_active=True,
            league__is_active=True,
            role__in=valid_roles,
        )
        .select_related("league", "competition")
        .order_by("id")
    )
    seen_scopes = set()
    entitlements = []
    for scope in scopes:
        if scope.competition_id:
            if (
                not scope.competition.is_active
                or scope.competition.league_id != scope.league_id
            ):
                continue
            scope_type = "COMPETITION"
            scope_id = scope.competition_id
        else:
            scope_type = "LEAGUE"
            scope_id = scope.league_id

        scope_key = (scope_type, scope_id, scope.role)
        if scope_key in seen_scopes:
            continue
        seen_scopes.add(scope_key)
        entitlements.append(
            _entitlement(
                entitlement_id=f"league-scope-{scope.id}",
                dashboard="LEAGUE_ADMIN",
                route="/dashboard/league-admin",
                scope_type=scope_type,
                scope_id=scope_id,
                workspace_role=scope.role,
                permissions=LEAGUE_SCOPE_ROLE_PERMISSIONS[scope.role],
            )
        )
    return entitlements


def _club_scope_entitlement(scope):
    is_ticketing = scope.role == ClubAdminScope.Role.TICKETING_OFFICER
    permissions = set(CLUB_ADMIN_SUB_ROLE_PERMISSIONS.get(scope.role, set()))
    if is_ticketing:
        permissions.discard("dashboard.club_admin")
        permissions.add("dashboard.ticketing_officer")
    return _entitlement(
        entitlement_id=f"club-scope-{scope.id}",
        dashboard="TICKETING_OFFICER" if is_ticketing else "CLUB_ADMIN",
        route=(
            "/dashboard/ticketing-officer" if is_ticketing else "/dashboard/club-admin"
        ),
        scope_type="CLUB",
        scope_id=scope.club_id,
        workspace_role=scope.role,
        permissions=permissions,
    )


def _resolve_club_entitlements(user):
    valid_roles = {value for value, _label in ClubAdminScope.Role.choices}
    scopes = (
        ClubAdminScope.objects.filter(
            user=user,
            is_active=True,
            role__in=valid_roles,
        )
        .select_related("club")
        .order_by("id")
    )
    entitlements_by_club = {}
    for scope in scopes:
        entitlements_by_club.setdefault(scope.club_id, _club_scope_entitlement(scope))

    if user.role == User.Role.CLUB_ADMIN:
        direct_clubs = Club.objects.filter(admin=user)
        if user.club_id:
            direct_clubs = Club.objects.filter(id=user.club_id) | direct_clubs
        for club in direct_clubs.order_by("id").distinct():
            entitlements_by_club.setdefault(
                club.id,
                _entitlement(
                    entitlement_id=f"club-{club.id}",
                    dashboard="CLUB_ADMIN",
                    route="/dashboard/club-admin",
                    scope_type="CLUB",
                    scope_id=club.id,
                    workspace_role=ClubAdminScope.Role.CLUB_ADMIN,
                    permissions=CLUB_ADMIN_SUB_ROLE_PERMISSIONS[
                        ClubAdminScope.Role.CLUB_ADMIN
                    ],
                ),
            )

    return sorted(entitlements_by_club.values(), key=lambda item: item["scope_id"])


def _has_invalid_family_combination(families):
    active_families = [name for name, values in families.items() if values]
    return len(active_families) > 1


def _account_evidence(user):
    from dashboards.models import LeagueAdminScope, UnionWorkspaceMembership
    from sponsorships.models import SponsorAccount, SponsorAccountMember

    return {
        "SPONSOR": (
            SponsorAccount.objects.filter(owner=user).exists()
            or SponsorAccountMember.objects.filter(user=user).exists()
        ),
        "UNION_WORKSPACE": UnionWorkspaceMembership.objects.filter(user=user).exists(),
        "LEAGUE_WORKSPACE": LeagueAdminScope.objects.filter(user=user).exists(),
        "CLUB_WORKSPACE": (
            ClubAdminScope.objects.filter(user=user).exists()
            or Club.objects.filter(admin=user).exists()
            or bool(user.club_id)
        ),
    }


def _is_sponsor_human(user, evidence):
    from sponsorships.models import SponsorAccountMember

    valid_types = {value for value, _label in User.SponsorType.choices}
    return (
        user.sponsor_type in valid_types
        and (user.role == User.Role.SPONSOR or bool(user.is_sponsor))
    ) or (
        evidence["SPONSOR"] and SponsorAccountMember.objects.filter(user=user).exists()
    )


def _access(entitlements):
    if not entitlements:
        return _empty_access()
    return {
        "version": ACCESS_VERSION,
        "default_entitlement_id": entitlements[0]["id"],
        "entitlements": entitlements,
    }


def resolve_dashboard_access(user):
    """Return the deterministic dashboard contract for an authenticated user."""

    if (
        user is None
        or not getattr(user, "is_authenticated", False)
        or not getattr(user, "is_active", False)
        or not getattr(user, "pk", None)
    ):
        return _empty_access()

    valid_primary_roles = {value for value, _label in User.Role.choices}
    if user.role not in valid_primary_roles:
        return _empty_access()

    evidence = _account_evidence(user)
    individual_sponsor, invalid_individual = _resolve_individual_sponsor_entitlements(
        user
    )
    if invalid_individual:
        return _empty_access()
    corporate_sponsor = _resolve_corporate_sponsor_entitlements(user)
    if individual_sponsor and corporate_sponsor:
        return _empty_access()
    sponsor = individual_sponsor or corporate_sponsor

    all_union = _resolve_union_entitlements(user)
    all_league = _resolve_league_entitlements(user)
    all_club = _resolve_club_entitlements(user)
    families = {
        "SPONSOR": sponsor,
        "SUPER_ADMIN": _resolve_super_admin_entitlements(user),
        "UNION_WORKSPACE": all_union,
        "LEAGUE_WORKSPACE": all_league,
        "CLUB_WORKSPACE": all_club,
    }
    if _has_invalid_family_combination(families):
        return _empty_access()

    sponsor_human = _is_sponsor_human(user, evidence)
    operational_evidence = any(
        evidence[name]
        for name in ("UNION_WORKSPACE", "LEAGUE_WORKSPACE", "CLUB_WORKSPACE")
    )

    if user.is_superuser or user.role == User.Role.SUPER_ADMIN:
        if sponsor or all_union or all_league or all_club:
            return _empty_access()
        return _access(families["SUPER_ADMIN"])

    if user.role == User.Role.SPONSOR:
        if operational_evidence:
            return _empty_access()
        if sponsor:
            return _access([*sponsor, _fan_entitlement(user)])
        if sponsor_human:
            return _access([_fan_entitlement(user)])
        return _empty_access()

    if user.role == User.Role.UNION_ADMIN:
        if (
            evidence["SPONSOR"]
            or evidence["LEAGUE_WORKSPACE"]
            or evidence["CLUB_WORKSPACE"]
        ):
            return _empty_access()
        return _access(all_union)

    if user.role == User.Role.LEAGUE_ADMIN:
        if (
            evidence["SPONSOR"]
            or evidence["UNION_WORKSPACE"]
            or evidence["CLUB_WORKSPACE"]
        ):
            return _empty_access()
        return _access(all_league)

    if user.role == User.Role.CLUB_ADMIN:
        if (
            evidence["SPONSOR"]
            or evidence["UNION_WORKSPACE"]
            or evidence["LEAGUE_WORKSPACE"]
        ):
            return _empty_access()
        return _access(all_club)

    if user.role == User.Role.REFEREE:
        if (
            evidence["SPONSOR"]
            or evidence["LEAGUE_WORKSPACE"]
            or evidence["CLUB_WORKSPACE"]
        ):
            return _empty_access()
        return _access(_filter_union_entitlements(all_union, {"MATCH_OFFICIAL"}))

    if user.role == User.Role.TICKETING_OFFICER:
        if evidence["SPONSOR"] or evidence["LEAGUE_WORKSPACE"]:
            return _empty_access()
        union_ticketing = _filter_union_entitlements(all_union, {"TICKETING_OFFICER"})
        club_ticketing = [
            item for item in all_club if item["workspace_role"] == "TICKETING_OFFICER"
        ]
        if union_ticketing and club_ticketing:
            return _empty_access()
        return _access(union_ticketing or club_ticketing)

    if user.role == User.Role.FAN:
        if sponsor and operational_evidence:
            return _empty_access()
        valid_operational = [all_union, all_league, all_club]
        valid_operational = [items for items in valid_operational if items]
        if len(valid_operational) > 1:
            return _empty_access()
        if sponsor:
            return _access([*sponsor, _fan_entitlement(user)])
        if valid_operational:
            return _access(valid_operational[0])
        if operational_evidence:
            return _empty_access()
        if sponsor_human:
            return _access([_fan_entitlement(user)])
        return _access([_fan_entitlement(user)])

    return _empty_access()
