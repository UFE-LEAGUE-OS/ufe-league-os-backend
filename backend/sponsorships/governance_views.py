"""
Sponsorship Governance Views
"""

from django.utils import timezone
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .governance_models import (
    SponsorFramework,
    CampaignVisibilitySettings,
    SystemPlacement,
    BenefitSharingPolicy,
    SponsorshipInventory,
    CampaignPerformance,
    SponsorshipApprovalWorkflow,
    ComplianceAudit,
)
from .governance_serializers import (
    SponsorFrameworkSerializer,
    CampaignVisibilitySettingsSerializer,
    SystemPlacementSerializer,
    BenefitSharingPolicySerializer,
    SponsorshipInventorySerializer,
    CampaignPerformanceSerializer,
    SponsorshipApprovalWorkflowSerializer,
    ComplianceAuditSerializer,
)


class SponsorFrameworkViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing sponsor frameworks.
    """

    queryset = SponsorFramework.objects.all()
    serializer_class = SponsorFrameworkSerializer
    permission_classes = [permissions.IsAdminUser]


class CampaignVisibilitySettingsViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing campaign visibility settings.
    """

    queryset = CampaignVisibilitySettings.objects.all()
    serializer_class = CampaignVisibilitySettingsSerializer
    permission_classes = [permissions.IsAdminUser]


class SystemPlacementViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing system placements.
    """

    queryset = SystemPlacement.objects.all()
    serializer_class = SystemPlacementSerializer
    permission_classes = [permissions.IsAdminUser]


class BenefitSharingPolicyViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing benefit sharing policies.
    """

    queryset = BenefitSharingPolicy.objects.all()
    serializer_class = BenefitSharingPolicySerializer
    permission_classes = [permissions.IsAdminUser]


class SponsorshipInventoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing sponsorship inventory.
    """

    queryset = SponsorshipInventory.objects.all()
    serializer_class = SponsorshipInventorySerializer
    permission_classes = [permissions.IsAdminUser]


class CampaignPerformanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing campaign performance metrics.
    """

    queryset = CampaignPerformance.objects.all()
    serializer_class = CampaignPerformanceSerializer
    permission_classes = [permissions.IsAdminUser]


class SponsorshipApprovalWorkflowViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing sponsorship approval workflows.
    """

    queryset = SponsorshipApprovalWorkflow.objects.all()
    serializer_class = SponsorshipApprovalWorkflowSerializer
    permission_classes = [permissions.IsAdminUser]


class ComplianceAuditViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing compliance audits.
    """

    queryset = ComplianceAudit.objects.all()
    serializer_class = ComplianceAuditSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        audit = self.get_object()
        audit.status = ComplianceAudit.Status.COMPLETED
        audit.completed_at = timezone.now()
        audit.save()
        return Response({"status": "completed"})

    @action(detail=True, methods=["post"])
    def fail(self, request, pk=None):
        audit = self.get_object()
        audit.status = ComplianceAudit.Status.FAILED
        audit.completed_at = timezone.now()
        audit.save()
        return Response({"status": "failed"})
