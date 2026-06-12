from .models import AuditLog, User


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


def get_user_permissions(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return set()

    permissions = set(get_role_permissions(user.role))

    if getattr(user, "is_sponsor", False):
        permissions |= get_role_permissions(User.Role.SPONSOR)

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

    if getattr(user, "is_sponsor", False) and user.role != User.Role.SPONSOR:
        routes.append(
            {
                "role": User.Role.SPONSOR,
                "role_display": User.Role.SPONSOR.label,
                "route": FRONTEND_DASHBOARD_ROUTES[User.Role.SPONSOR],
                "backend_route": BACKEND_DASHBOARD_ROUTES[User.Role.SPONSOR],
            }
        )

    return routes


def get_dashboard_route(user):
    if (
        getattr(user, "is_sponsor", False)
        and getattr(user, "role", None) == User.Role.FAN
    ):
        return FRONTEND_DASHBOARD_ROUTES.get(User.Role.FAN, "/dashboard/fan")

    return FRONTEND_DASHBOARD_ROUTES.get(getattr(user, "role", None), "/dashboard/fan")


def get_backend_dashboard_route(user):
    if (
        getattr(user, "is_sponsor", False)
        and getattr(user, "role", None) == User.Role.FAN
    ):
        return BACKEND_DASHBOARD_ROUTES.get(User.Role.FAN, "/api/dashboards/me/")

    return BACKEND_DASHBOARD_ROUTES.get(
        getattr(user, "role", None), "/api/dashboards/me/"
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
