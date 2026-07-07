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

urlpatterns = [path("", include(router.urls))]
