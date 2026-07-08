from .models import AuditLog, RoleApproval, User

ROLE_PERMISSIONS = {
    User.Role.FAN: {
        "dashboard.fan",
        "dashboard.me",
    },
    User.Role.CLUB_ADMIN: {
        "dashboard.club_admin",
        "dashboard.me",
    },
    User.Role.LEAGUE_ADMIN: {
        "dashboard.league_admin",
        "dashboard.me",
    },
    User.Role.UNION_ADMIN: {
        "dashboard.union_admin",
        "dashboard.me",
    },
    User.Role.SUPER_ADMIN: {
        "dashboard.super_admin",
        "dashboard.me",
    },
    User.Role.REFEREE: {
        "dashboard.referee",
        "dashboard.me",
    },
    User.Role.TICKETING_OFFICER: {
        "dashboard.ticketing_officer",
        "dashboard.me",
    },
    User.Role.SPONSOR: {
        "dashboard.sponsor",
        "dashboard.me",
    },
}

FRONTEND_DASHBOARD_ROUTES = {
    User.Role.FAN: "/dashboard/fan",
    User.Role.CLUB_ADMIN: "/dashboard/club-admin",
    User.Role.LEAGUE_ADMIN: "/dashboard/league-admin",
    User.Role.UNION_ADMIN: "/dashboard/union-admin",
    User.Role.SUPER_ADMIN: "/dashboard/super-admin",
    User.Role.REFEREE: "/dashboard/referee",
    User.Role.TICKETING_OFFICER: "/dashboard/ticketing-officer",
    User.Role.SPONSOR: "/dashboard/sponsor",
}

BACKEND_DASHBOARD_ROUTES = {
    User.Role.FAN: "/api/dashboards/fan/",
    User.Role.CLUB_ADMIN: "/api/dashboards/club-admin/",
    User.Role.LEAGUE_ADMIN: "/api/dashboards/league-admin/",
    User.Role.UNION_ADMIN: "/api/dashboards/union-admin/",
    User.Role.SUPER_ADMIN: "/api/dashboards/super-admin/",
    User.Role.REFEREE: "/api/dashboards/referee/",
    User.Role.TICKETING_OFFICER: "/api/dashboards/ticketing-officer/",
    User.Role.SPONSOR: "/api/dashboards/sponsor/",
}

# ---------------------------------------------------------------------------
# Sensitive roles requiring dual-admin approval
# When a SUPER_ADMIN assigns these roles, a RoleApproval record is created
# and another SUPER_ADMIN must approve it before the role change takes effect.
# ---------------------------------------------------------------------------
SENSITIVE_ROLES = {
    User.Role.UNION_ADMIN,
    User.Role.SUPER_ADMIN,
}


def is_sensitive_role(role):
    """Return True if the given role requires dual-admin approval."""
    return role in SENSITIVE_ROLES


def create_role_approval(*, target_user, requested_role, requested_by, reason=""):
    """
    Create a pending RoleApproval request for a sensitive role assignment.

    The role change is NOT applied immediately. Another SUPER_ADMIN must
    approve via the approval endpoint.
    """
    approval = RoleApproval.objects.create(
        target_user=target_user,
        requested_role=requested_role,
        requested_by=requested_by,
        status=RoleApproval.Status.PENDING,
        reason=reason,
    )
    log_governance_action(
        actor=requested_by,
        action="role_approval_requested",
        details={
            "target_user_email": target_user.email,
            "requested_role": requested_role,
            "approval_id": approval.id,
            "reason": reason,
        },
    )
    return approval


def approve_role_approval(approval, reviewer, rejection_reason=""):
    """
    Approve or reject a RoleApproval request.

    On APPROVED: the target user's role is updated and the change is logged.
    On REJECTED: the request is marked as rejected, no role change occurs.
    """
    if approval.status != RoleApproval.Status.PENDING:
        raise ValueError(
            f"Cannot review a request with status '{approval.status}'."
            " Only PENDING requests can be approved or rejected."
        )

    if rejection_reason:
        approval.status = RoleApproval.Status.REJECTED
        approval.rejection_reason = rejection_reason
        approval.reviewed_by = reviewer
        approval.save(
            update_fields=["status", "rejection_reason", "reviewed_by", "updated_at"]
        )
        log_governance_action(
            actor=reviewer,
            action="role_approval_rejected",
            details={
                "target_user_email": approval.target_user.email,
                "requested_role": approval.requested_role,
                "approval_id": approval.id,
                "rejection_reason": rejection_reason,
            },
        )
        return approval

    # APPROVED
    previous_role = approval.target_user.role
    approval.target_user.role = approval.requested_role
    approval.target_user.save(update_fields=["role"])

    approval.status = RoleApproval.Status.APPROVED
    approval.reviewed_by = reviewer
    approval.save(update_fields=["status", "reviewed_by", "updated_at"])

    log_role_change(
        target_user=approval.target_user,
        previous_role=previous_role,
        new_role=approval.requested_role,
        actor=reviewer,
        reason=f"role_approval_approved (request #{approval.id})",
    )
    log_governance_action(
        actor=reviewer,
        action="role_approval_approved",
        details={
            "target_user_email": approval.target_user.email,
            "previous_role": previous_role,
            "new_role": approval.requested_role,
            "approval_id": approval.id,
        },
    )
    return approval


# ---------------------------------------------------------------------------
# Role hierarchy for user creation
# Defines which roles each admin level is allowed to create.
# Each entry maps (admin_role -> set(creatable_roles)).
#
# Rules:
#   - FAN is a self-registration role only. No admin can create fans manually.
#   - SPONSOR is a self-upgrade from FAN via the become-sponsor endpoint.
#     No admin can create sponsors manually.
#   - Only SUPER_ADMIN can create CLUB_ADMIN, LEAGUE_ADMIN, and UNION_ADMIN.
#   - LEAGUE_ADMIN can create CLUB_ADMIN (for clubs under the league),
#     REFEREE (match officials), and TICKETING_OFFICER.
#   - UNION_ADMIN can create REFEREE and TICKETING_OFFICER.
#   - CLUB_ADMIN can create TICKETING_OFFICER.
#   - SUPER_ADMIN and UNION_ADMIN are sensitive roles requiring
#     dual-admin approval via the RoleApproval workflow.
# ---------------------------------------------------------------------------
CREATABLE_ROLES = {
    User.Role.SUPER_ADMIN: {
        User.Role.CLUB_ADMIN,
        User.Role.LEAGUE_ADMIN,
        User.Role.UNION_ADMIN,
        User.Role.REFEREE,
        User.Role.TICKETING_OFFICER,
    },
    User.Role.UNION_ADMIN: {
        User.Role.REFEREE,
        User.Role.TICKETING_OFFICER,
    },
    User.Role.LEAGUE_ADMIN: {
        User.Role.CLUB_ADMIN,
        User.Role.REFEREE,
        User.Role.TICKETING_OFFICER,
    },
    User.Role.CLUB_ADMIN: {
        User.Role.TICKETING_OFFICER,
    },
}


def get_creatable_roles(admin_role):
    """Return the set of roles that the given admin role is allowed to create."""
    return CREATABLE_ROLES.get(admin_role, set())


def can_admin_create_role(admin_user, target_role):
    """Check whether *admin_user* is allowed to create a user with *target_role*."""
    return target_role in get_creatable_roles(admin_user.role)


def get_role_permissions(role):
    return ROLE_PERMISSIONS.get(role, set())


def user_has_union_workspace_access(user):
    """Return True when a normal user account has an active union workspace."""

    if user is None or not getattr(user, "is_authenticated", False):
        return False

    union_memberships = getattr(user, "union_workspace_memberships", None)

    if union_memberships is None:
        return False

    return union_memberships.filter(is_active=True, workspace__status="ACTIVE").exists()


def get_union_workspace_permissions(user):
    """Return permissions granted through active union workspace memberships."""

    if user is None or not getattr(user, "is_authenticated", False):
        return set()

    union_memberships = getattr(user, "union_workspace_memberships", None)

    if union_memberships is None:
        return set()

    permissions = set()

    for membership in union_memberships.filter(
        is_active=True,
        workspace__status="ACTIVE",
    ):
        permissions.update(membership.effective_permissions)

    if permissions:
        permissions.add("dashboard.union_admin")
        permissions.add("dashboard.me")
        permissions.add("union.workspace.switch")

    return permissions


def user_has_sponsor_access(user):
    """
    Return True when the user can access sponsor features.

    Final League OS sponsor logic:
    - Legacy SPONSOR role is still supported.
    - Legacy User.is_sponsor flag is still supported.
    - SponsorAccountMember is the real source of truth for sponsor access.
    """

    if user is None or not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "role", None) == User.Role.SPONSOR:
        return True

    if getattr(user, "is_sponsor", False):
        return True

    sponsor_memberships = getattr(user, "sponsor_memberships", None)

    if sponsor_memberships is None:
        return False

    return sponsor_memberships.filter(is_active=True).exists()


def get_user_permissions(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return set()

    permissions = set(get_role_permissions(user.role))

    if user_has_sponsor_access(user):
        permissions |= get_role_permissions(User.Role.SPONSOR)

    permissions |= get_union_workspace_permissions(user)

    return permissions


def has_role_permission(user, permission):
    return permission in get_user_permissions(user)


def get_dashboard_routes(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return []

    routes = []

    default_role = getattr(user, "role", None)

    if default_role in FRONTEND_DASHBOARD_ROUTES:
        routes.append(
            {
                "role": default_role,
                "role_display": user.get_role_display(),
                "route": FRONTEND_DASHBOARD_ROUTES[default_role],
                "backend_route": BACKEND_DASHBOARD_ROUTES[default_role],
            }
        )

    if user_has_sponsor_access(user) and user.role != User.Role.SPONSOR:
        routes.append(
            {
                "role": User.Role.SPONSOR,
                "role_display": "Sponsor",
                "route": FRONTEND_DASHBOARD_ROUTES[User.Role.SPONSOR],
                "backend_route": BACKEND_DASHBOARD_ROUTES[User.Role.SPONSOR],
            }
        )

    if user_has_union_workspace_access(user) and user.role != User.Role.UNION_ADMIN:
        routes.append(
            {
                "role": User.Role.UNION_ADMIN,
                "role_display": "Union Admin Workspace",
                "route": FRONTEND_DASHBOARD_ROUTES[User.Role.UNION_ADMIN],
                "backend_route": BACKEND_DASHBOARD_ROUTES[User.Role.UNION_ADMIN],
            }
        )

    return routes


def get_dashboard_route(user):
    return FRONTEND_DASHBOARD_ROUTES.get(
        getattr(user, "role", None),
        "/dashboard/fan",
    )


def get_backend_dashboard_route(user):
    return BACKEND_DASHBOARD_ROUTES.get(
        getattr(user, "role", None),
        "/api/dashboards/me/",
    )


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR", "") or ""


def log_role_change(
    target_user,
    previous_role,
    new_role,
    actor=None,
    reason=None,
):
    return AuditLog.objects.create(
        category=AuditLog.Category.ROLE_CHANGE,
        actor=actor,
        target_user=target_user,
        action="role_change",
        details={
            "previous_role": previous_role,
            "new_role": new_role,
            "reason": reason,
        },
    )


def log_governance_action(
    actor,
    action,
    details,
    target_user=None,
):
    """Log administrative actions related to league governance."""
    return AuditLog.objects.create(
        category=AuditLog.Category.GOVERNANCE,
        actor=actor,
        target_user=target_user,
        action=action,
        details=details,
    )


def log_access_violation(request, status_code, detail=None):
    user = getattr(request, "user", None)
    actor = user if getattr(user, "is_authenticated", False) else None
    details = detail if isinstance(detail, dict) else {"message": detail}

    return AuditLog.objects.create(
        category=AuditLog.Category.ACCESS_VIOLATION,
        actor=actor,
        target_user=actor,
        action="access_denied",
        path=getattr(request, "path", ""),
        method=getattr(request, "method", ""),
        status_code=status_code,
        ip_address=get_client_ip(request),
        details=details,
    )
