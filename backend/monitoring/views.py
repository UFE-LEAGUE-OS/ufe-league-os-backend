from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsSuperAdmin
from .models import (
    Anomaly,
    ApprovalLog,
    ChargebackRefund,
    ComplianceTrail,
    DataAccessAudit,
    PaymentAudit,
    SecurityEvent,
    SystemLog,
    TransactionReconciliation,
)
from .serializers import (
    AnomalySerializer,
    ApprovalLogSerializer,
    ChargebackRefundSerializer,
    ComplianceTrailSerializer,
    DataAccessAuditSerializer,
    PaymentAuditSerializer,
    SecurityEventSerializer,
    SystemLogSerializer,
    TransactionReconciliationSerializer,
)


class ApprovalLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for monitoring all approval actions across the platform.
    Provides a centralized, read-only audit trail for super administrators.
    """

    queryset = (
        ApprovalLog.objects.all()
        .select_related("actor")
        .prefetch_related("content_object")
    )
    serializer_class = ApprovalLogSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ["action", "category", "actor__email"]


class ChargebackRefundViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing payment chargebacks and refund requests.
    Allows super administrators to track and resolve payment disputes.
    """

    queryset = ChargebackRefund.objects.all().select_related("opened_by", "handled_by")
    serializer_class = ChargebackRefundSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ["dispute_type", "status", "currency", "handled_by__email"]

    def perform_create(self, serializer):
        serializer.save(opened_by=self.request.user)


class AnomalyViewSet(viewsets.ModelViewSet):
    queryset = Anomaly.objects.all().order_by("-created_at")
    serializer_class = AnomalySerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ["anomaly_type", "severity", "status", "assigned_to__email"]

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        anomaly = self.get_object()
        resolution_notes = request.data.get("resolution_notes", "")
        anomaly.status = Anomaly.Status.RESOLVED
        anomaly.resolved_by = request.user
        anomaly.resolution_notes = resolution_notes
        anomaly.resolved_at = timezone.now()
        anomaly.save()
        return Response(self.get_serializer(anomaly).data)


class PaymentAuditViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PaymentAudit.objects.all().order_by("-created_at")
    serializer_class = PaymentAuditSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ["user__email", "payment_source", "event_type", "status"]


class TransactionReconciliationViewSet(viewsets.ModelViewSet):
    queryset = TransactionReconciliation.objects.all().order_by("-transaction_date")
    serializer_class = TransactionReconciliationSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ["status", "source_system", "is_verified"]

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        reconciliation = self.get_object()
        reconciliation.is_verified = True
        reconciliation.verified_by = request.user
        reconciliation.save()
        return Response(self.get_serializer(reconciliation).data)


class SystemLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SystemLog.objects.all().order_by("-created_at")
    serializer_class = SystemLogSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ["level", "logger_name", "user_email"]


class ComplianceTrailViewSet(viewsets.ModelViewSet):
    queryset = ComplianceTrail.objects.all().order_by("-created_at")
    serializer_class = ComplianceTrailSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ["category", "is_compliant", "assessed_by__email"]


class DataAccessAuditViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DataAccessAudit.objects.all().order_by("-created_at")
    serializer_class = DataAccessAuditSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ["user__email", "access_type", "resource_type", "is_authorized"]


class SecurityEventViewSet(viewsets.ModelViewSet):
    queryset = SecurityEvent.objects.all().order_by("-created_at")
    serializer_class = SecurityEventSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ["event_type", "severity", "is_resolved", "user__email"]

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        event = self.get_object()
        resolution_notes = request.data.get("resolution_notes", "")
        event.is_resolved = True
        event.resolved_by = request.user
        event.resolution_notes = resolution_notes
        event.resolved_at = timezone.now()
        event.save()
        return Response(self.get_serializer(event).data)
