from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ClubDocumentViewSet,
    ComplianceChecklistViewSet,
    AnnouncementViewSet,
    CommunicationLogViewSet,
    SponsorCampaignViewSet,
    CampaignAssignmentViewSet,
    MatchdayOperationTaskViewSet,
    TicketingOfficerAssignmentViewSet,
    MatchdayReportViewSet,
)

router = DefaultRouter()
router.register(r"documents", ClubDocumentViewSet, basename="club-document")
router.register(r"compliance", ComplianceChecklistViewSet, basename="compliance")
router.register(r"announcements", AnnouncementViewSet, basename="announcement")
router.register(r"communications", CommunicationLogViewSet, basename="communication")
router.register(
    r"sponsor-campaigns", SponsorCampaignViewSet, basename="sponsor-campaign"
)
router.register(
    r"campaign-assignments", CampaignAssignmentViewSet, basename="campaign-assignment"
)
router.register(
    r"matchday-tasks", MatchdayOperationTaskViewSet, basename="matchday-task"
)
router.register(
    r"ticketing-officers",
    TicketingOfficerAssignmentViewSet,
    basename="ticketing-officer",
)
router.register(r"matchday-reports", MatchdayReportViewSet, basename="matchday-report")

urlpatterns = [
    path("", include(router.urls)),
]
