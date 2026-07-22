from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounts.models import Club

from .models import (
    CampaignAssignment,
    MatchdayOperationTask,
    MatchdayReport,
    SponsorCampaign,
    TicketingOfficerAssignment,
)
from .permissions import (
    CanAccessClubOperations,
)
from .serializers import (
    CampaignAssignmentSerializer,
    MatchdayOperationTaskSerializer,
    MatchdayReportSerializer,
    SponsorCampaignSerializer,
    TicketingOfficerAssignmentSerializer,
)
from .services import (
    archive_campaign,
    log_club_operation_action,
)


class ClubDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = None  # Add serializer when needed
    permission_classes = [IsAuthenticated, CanAccessClubOperations]


class ComplianceChecklistViewSet(viewsets.ModelViewSet):
    serializer_class = None
    permission_classes = [IsAuthenticated, CanAccessClubOperations]


class AnnouncementViewSet(viewsets.ModelViewSet):
    serializer_class = None
    permission_classes = [IsAuthenticated, CanAccessClubOperations]


class CommunicationLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = None
    permission_classes = [IsAuthenticated, CanAccessClubOperations]


class SponsorCampaignViewSet(viewsets.ModelViewSet):
    serializer_class = SponsorCampaignSerializer
    permission_classes = [IsAuthenticated, CanAccessClubOperations]
    filterset_fields = ["status", "campaign_type", "club", "sponsor"]
    search_fields = ["name", "sponsor__name", "description", "notes"]
    ordering_fields = ["start_date", "end_date", "created_at", "name", "budget"]
    ordering = ["-start_date", "-created_at"]

    def get_queryset(self):
        user = self.request.user
        club_id = self.request.query_params.get("club")
        queryset = SponsorCampaign.objects.filter(is_deleted=False).select_related(
            "club", "sponsor", "sponsor_package", "created_by"
        )
        if club_id:
            return queryset.filter(club_id=club_id)
        club = Club.objects.filter(admin=user).first()
        if user.role != "SUPER_ADMIN" and not club:
            return SponsorCampaign.objects.none()
        if club:
            queryset = queryset.filter(club=club)
        return queryset

    def perform_create(self, serializer):
        club = Club.objects.filter(admin=self.request.user).first()
        if not club:
            raise ValueError("User is not a club admin.")
        campaign = serializer.save(club=club, created_by=self.request.user)
        log_club_operation_action(
            club=club,
            actor=self.request.user,
            action="CAMPAIGN_CREATED",
            target_object=campaign,
            description=f"Campaign {campaign.name} created.",
        )
        return campaign

    def perform_update(self, serializer):
        campaign = serializer.save()
        log_club_operation_action(
            club=campaign.club,
            actor=self.request.user,
            action="CAMPAIGN_UPDATED",
            target_object=campaign,
            description=f"Campaign {campaign.name} updated.",
        )
        return campaign

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["is_deleted", "deleted_at"])
        log_club_operation_action(
            club=instance.club,
            actor=self.request.user,
            action="CAMPAIGN_DELETED",
            target_object=instance,
            description=f"Campaign {instance.name} deleted.",
        )

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        campaign = self.get_object()
        archive_campaign(campaign)
        log_club_operation_action(
            club=campaign.club,
            actor=request.user,
            action="CAMPAIGN_ARCHIVED",
            target_object=campaign,
            description=f"Campaign {campaign.name} archived.",
        )
        return Response({"status": "archived"}, status=status.HTTP_200_OK)


class CampaignAssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = CampaignAssignmentSerializer
    permission_classes = [IsAuthenticated, CanAccessClubOperations]
    filterset_fields = ["campaign", "match", "sponsor_package", "activation_status"]
    search_fields = ["campaign__name", "activation_notes", "branding_locations"]
    ordering_fields = ["created_at", "activation_status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        club_id = self.request.query_params.get("club")
        queryset = CampaignAssignment.objects.select_related(
            "campaign", "match", "sponsor_package", "created_by"
        )
        if club_id:
            return queryset.filter(campaign__club_id=club_id)
        club = Club.objects.filter(admin=user).first()
        if user.role != "SUPER_ADMIN" and not club:
            return CampaignAssignment.objects.none()
        if club:
            return queryset.filter(campaign__club=club)
        return queryset

    def perform_create(self, serializer):
        campaign = serializer.validated_data["campaign"]
        assignment = serializer.save(created_by=self.request.user)
        log_club_operation_action(
            club=campaign.club,
            actor=self.request.user,
            action="CAMPAIGN_TAGGED",
            target_object=assignment,
            description=f"Campaign {campaign.name} tagged to event.",
        )
        return assignment

    def perform_update(self, serializer):
        assignment = serializer.save()
        log_club_operation_action(
            club=assignment.campaign.club,
            actor=self.request.user,
            action="CAMPAIGN_ASSIGNMENT_UPDATED",
            target_object=assignment,
            description="Campaign assignment updated.",
        )
        return assignment

    def perform_destroy(self, instance):
        campaign = instance.campaign
        instance.delete()
        log_club_operation_action(
            club=campaign.club,
            actor=self.request.user,
            action="CAMPAIGN_REMOVED",
            target_object=instance,
            description="Campaign assignment removed.",
        )


class MatchdayOperationTaskViewSet(viewsets.ModelViewSet):
    serializer_class = MatchdayOperationTaskSerializer
    permission_classes = [IsAuthenticated, CanAccessClubOperations]
    filterset_fields = [
        "status",
        "priority",
        "category",
        "assigned_to",
        "match",
        "due_date",
    ]
    search_fields = ["title", "description", "completion_notes"]
    ordering_fields = ["due_date", "priority", "created_at", "status"]
    ordering = ["due_date", "priority", "-created_at"]

    def get_queryset(self):
        user = self.request.user
        club_id = self.request.query_params.get("club")
        queryset = MatchdayOperationTask.objects.filter(
            is_deleted=False
        ).select_related("club", "match", "assigned_to", "completed_by", "created_by")
        if club_id:
            return queryset.filter(club_id=club_id)
        club = Club.objects.filter(admin=user).first()
        if user.role != "SUPER_ADMIN" and not club:
            return MatchdayOperationTask.objects.none()
        if club:
            queryset = queryset.filter(club=club)
        return queryset

    def perform_create(self, serializer):
        club = Club.objects.filter(admin=self.request.user).first()
        if not club:
            raise ValueError("User is not a club admin.")
        task = serializer.save(club=club, created_by=self.request.user)
        log_club_operation_action(
            club=club,
            actor=self.request.user,
            action="TASK_CREATED",
            target_object=task,
            description=f"Matchday task {task.title} created.",
        )
        return task

    def perform_update(self, serializer):
        task = serializer.save()
        log_club_operation_action(
            club=task.club,
            actor=self.request.user,
            action="TASK_UPDATED",
            target_object=task,
            description=f"Matchday task {task.title} updated.",
        )
        return task

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        task = self.get_object()
        task.completed_by = request.user
        task.status = MatchdayOperationTask.TaskStatus.COMPLETED
        task.completed_at = timezone.now()
        task.save(update_fields=["completed_by", "status", "completed_at"])
        log_club_operation_action(
            club=task.club,
            actor=request.user,
            action="TASK_COMPLETED",
            target_object=task,
            description=f"Matchday task {task.title} completed.",
        )
        serializer = self.get_serializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TicketingOfficerAssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = TicketingOfficerAssignmentSerializer
    permission_classes = [IsAuthenticated, CanAccessClubOperations]
    filterset_fields = [
        "match",
        "officer",
        "status",
        "assignment_role",
        "gate_allocation",
    ]
    search_fields = [
        "officer__email",
        "officer__first_name",
        "officer__last_name",
        "gate_allocation",
        "notes",
    ]
    ordering_fields = ["shift_start", "shift_end", "created_at", "status"]
    ordering = ["match__match_date", "shift_start"]

    def get_queryset(self):
        user = self.request.user
        club_id = self.request.query_params.get("club")
        queryset = TicketingOfficerAssignment.objects.select_related(
            "club", "match", "officer", "assigned_by"
        )
        if club_id:
            return queryset.filter(club_id=club_id)
        club = Club.objects.filter(admin=user).first()
        if user.role != "SUPER_ADMIN" and not club:
            return TicketingOfficerAssignment.objects.none()
        if club:
            queryset = queryset.filter(club=club)
        return queryset

    def perform_create(self, serializer):
        club = Club.objects.filter(admin=self.request.user).first()
        if not club:
            raise ValueError("User is not a club admin.")
        assignment = serializer.save(club=club, assigned_by=self.request.user)
        log_club_operation_action(
            club=club,
            actor=self.request.user,
            action="OFFICER_ASSIGNED",
            target_object=assignment,
            description="Ticketing officer assigned.",
        )
        return assignment

    def perform_update(self, serializer):
        assignment = serializer.save()
        log_club_operation_action(
            club=assignment.club,
            actor=self.request.user,
            action="OFFICER_ASSIGNMENT_UPDATED",
            target_object=assignment,
            description="Ticketing officer assignment updated.",
        )
        return assignment

    def perform_destroy(self, instance):
        club = instance.club
        instance.delete()
        log_club_operation_action(
            club=club,
            actor=self.request.user,
            action="OFFICER_REMOVED",
            target_object=instance,
            description="Ticketing officer assignment removed.",
        )


class MatchdayReportViewSet(viewsets.ModelViewSet):
    serializer_class = MatchdayReportSerializer
    permission_classes = [IsAuthenticated, CanAccessClubOperations]
    filterset_fields = ["status", "match", "club", "submitted_by"]
    search_fields = [
        "successes",
        "challenges",
        "recommendations",
        "incidents",
        "stadium_issues",
    ]
    ordering_fields = ["created_at", "submitted_at", "reviewed_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        club_id = self.request.query_params.get("club")
        queryset = MatchdayReport.objects.filter(is_deleted=False).select_related(
            "match", "club", "submitted_by", "reviewed_by"
        )
        if club_id:
            return queryset.filter(club_id=club_id)
        club = Club.objects.filter(admin=user).first()
        if user.role != "SUPER_ADMIN" and not club:
            return MatchdayReport.objects.none()
        if club:
            queryset = queryset.filter(club=club)
        return queryset

    def perform_create(self, serializer):
        club = Club.objects.filter(admin=self.request.user).first()
        if not club:
            raise ValueError("User is not a club admin.")
        report = serializer.save(club=club, submitted_by=self.request.user)
        log_club_operation_action(
            club=club,
            actor=self.request.user,
            action="REPORT_SUBMITTED",
            target_object=report,
            description="Matchday report submitted.",
        )
        return report

    def perform_update(self, serializer):
        report = serializer.save()
        log_club_operation_action(
            club=report.club,
            actor=self.request.user,
            action="REPORT_UPDATED",
            target_object=report,
            description="Matchday report updated.",
        )
        return report

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        report = self.get_object()
        report.status = MatchdayReport.ReportStatus.SUBMITTED
        report.submitted_at = timezone.now()
        report.save(update_fields=["status", "submitted_at"])
        log_club_operation_action(
            club=report.club,
            actor=request.user,
            action="REPORT_SUBMITTED",
            target_object=report,
            description="Matchday report submitted.",
        )
        serializer = self.get_serializer(report)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        report = self.get_object()
        report.status = MatchdayReport.ReportStatus.APPROVED
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        log_club_operation_action(
            club=report.club,
            actor=request.user,
            action="REPORT_APPROVED",
            target_object=report,
            description="Matchday report approved.",
        )
        serializer = self.get_serializer(report)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        report = self.get_object()
        report.status = MatchdayReport.ReportStatus.REJECTED
        report.reviewed_by = request.user
        report.review_notes = request.data.get("review_notes", "")
        report.reviewed_at = timezone.now()
        report.save(
            update_fields=["status", "reviewed_by", "review_notes", "reviewed_at"]
        )
        log_club_operation_action(
            club=report.club,
            actor=request.user,
            action="REPORT_REJECTED",
            target_object=report,
            description="Matchday report rejected.",
        )
        serializer = self.get_serializer(report)
        return Response(serializer.data, status=status.HTTP_200_OK)
