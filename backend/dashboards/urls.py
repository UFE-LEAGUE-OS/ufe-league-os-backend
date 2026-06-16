from django.urls import path
from . import views

urlpatterns = [
    # Authenticated role dashboards
    path("me/", views.my_dashboard_view, name="my-dashboard"),
    path("fan/", views.fan_dashboard_view, name="fan-dashboard"),
    path("club-admin/", views.club_admin_dashboard_view, name="club-admin-dashboard"),
    path(
        "league-admin/",
        views.league_admin_dashboard_view,
        name="league-admin-dashboard",
    ),
    path(
        "union-admin/", views.union_admin_dashboard_view, name="union-admin-dashboard"
    ),
    path(
        "super-admin/", views.super_admin_dashboard_view, name="super-admin-dashboard"
    ),
    path("referee/", views.referee_dashboard_view, name="referee-dashboard"),
    path(
        "ticketing-officer/",
        views.ticketing_officer_dashboard_view,
        name="ticketing-officer-dashboard",
    ),
    path("sponsor/", views.sponsor_dashboard_view, name="sponsor-dashboard"),
    # Public / No-auth endpoints (AllowAny)
    path(
        "public/fixtures/",
        views.public_fixtures_view,
        name="public-fixtures",
    ),
    path(
        "public/results/",
        views.public_results_view,
        name="public-results",
    ),
    path(
        "public/standings/",
        views.public_standings_view,
        name="public-standings",
    ),
    path(
        "public/clubs/",
        views.public_clubs_view,
        name="public-clubs",
    ),
    path(
        "public/unions/",
        views.public_unions_view,
        name="public-unions",
    ),
    path(
        "public/leagues/",
        views.public_leagues_view,
        name="public-leagues",
    ),
    path(
        "public/competitions/",
        views.public_competitions_view,
        name="public-competitions",
    ),
]
