from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ClubDocumentViewSet,
    ComplianceChecklistViewSet,
    AnnouncementViewSet,
    CommunicationLogViewSet,
)

router = DefaultRouter()
router.register(r"documents", ClubDocumentViewSet, basename="club-document")
router.register(r"compliance", ComplianceChecklistViewSet, basename="compliance")
router.register(r"announcements", AnnouncementViewSet, basename="announcement")
router.register(r"communications", CommunicationLogViewSet, basename="communication")

urlpatterns = [
    path("", include(router.urls)),
]
