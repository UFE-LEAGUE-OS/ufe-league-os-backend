from django.urls import path
from . import views

urlpatterns = [
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
]
