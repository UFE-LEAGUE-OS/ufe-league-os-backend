from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"announcements", views.AnnouncementViewSet, basename="announcement")
router.register(r"feature-flags", views.FeatureFlagViewSet, basename="feature-flag")
router.register(r"banners", views.BannerViewSet, basename="banner")
router.register(
    r"system-messages", views.SystemMessageViewSet, basename="system-message"
)
router.register(
    r"public-content", views.PublicContentViewSet, basename="public-content"
)
router.register(
    r"help-center-articles",
    views.HelpCenterArticleViewSet,
    basename="help-center-article",
)
router.register(r"broadcasts", views.BroadcastViewSet, basename="broadcast")
router.register(
    r"notification-templates",
    views.NotificationTemplateViewSet,
    basename="notification-template",
)

urlpatterns = [
    path("public/", views.public_platform_content_view, name="public-platform-content"),
    path("", include(router.urls)),
]
