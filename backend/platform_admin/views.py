from rest_framework import viewsets
from accounts.permissions import IsSuperAdmin
from .models import ApprovalLog, ChargebackRefund
from .serializers import ApprovalLogSerializer, ChargebackRefundSerializer


class ApprovalLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for monitoring all approval actions across the platform.
    Provides a centralized, read-only audit trail for super administrators.
    """

    queryset = ApprovalLog.objects.all().select_related("actor").prefetch_related("content_object")
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