from django.urls import path

from . import views

urlpatterns = [
    path(
        "announcements/",
        views.announcement_list_create_view,
        name="announcement-list-create",
    ),
    path(
        "feature-flags/",
        views.feature_flag_list_create_view,
        name="feature-flag-list-create",
    ),
    path("banners/", views.banner_list_create_view, name="banner-list-create"),
    path(
        "system-messages/",
        views.system_message_list_create_view,
        name="system-message-list-create",
    ),
]
