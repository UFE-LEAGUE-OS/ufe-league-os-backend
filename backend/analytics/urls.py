from django.urls import path

from . import views

urlpatterns = [
    path("summary/", views.platform_summary_view, name="platform-summary"),
    path("user-growth/", views.user_growth_view, name="user-growth"),
    path("engagement/", views.engagement_analytics_view, name="engagement-analytics"),
    path("membership/", views.membership_analytics_view, name="membership-analytics"),
    path("ticketing/", views.ticketing_analytics_view, name="ticketing-analytics"),
    path(
        "sponsorship/", views.sponsorship_analytics_view, name="sponsorship-analytics"
    ),
    path("system-health/", views.system_health_view, name="system-health"),
    path(
        "access-logs/",
        views.analytics_report_access_log_view,
        name="analytics-access-logs",
    ),
]
