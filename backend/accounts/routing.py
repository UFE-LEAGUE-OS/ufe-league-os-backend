from .models import User

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


def get_dashboard_route(user):
    return FRONTEND_DASHBOARD_ROUTES.get(user.role, "/dashboard")


def get_backend_dashboard_route(user):
    return BACKEND_DASHBOARD_ROUTES.get(user.role, "/api/dashboards/me/")
