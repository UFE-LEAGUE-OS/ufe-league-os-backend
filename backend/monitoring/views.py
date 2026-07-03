from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsSuperAdmin
from accounts.rbac import log_governance_action

from .models import (
    Anomaly,
    PaymentAudit,
    TransactionReconciliation,
    SystemLog,
    ComplianceTrail,
    DataAccessAudit,
    SecurityEvent,
)
from .serializers import (
    AnomalySerializer,
    PaymentAuditSerializer,
    TransactionReconciliationSerializer,
    SystemLogSerializer,
    ComplianceTrailSerializer,
    DataAccessAuditSerializer,
    SecurityEventSerializer,
)

# ---------------------------------------------------------------------------
# ANOMALY INVESTIGATION
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def anomaly_list_create_view(request):
    """List anomalies or create a new anomaly record."""
    if request.method == "GET":
        queryset = Anomaly.objects.all().order_by("-created_at")
        serializer = AnomalySerializer(queryset, many=True)
        return Response(serializer.data)

    serializer = AnomalySerializer(data=request.data)
    if serializer.is_valid():
        anomaly = serializer.save()
        log_governance_action(
            actor=request.user,
            action="create_anomaly",
            details={"anomaly_id": anomaly.id, "anomaly_type": anomaly.anomaly_type},
        )
        return Response(AnomalySerializer(anomaly).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsSuperAdmin])
def anomaly_detail_view(request, pk):
    """Retrieve, update, or delete an anomaly."""
    try:
        anomaly = Anomaly.objects.get(pk=pk)
    except Anomaly.DoesNotExist:
        return Response(
            {"detail": "Anomaly not found."}, status=status.HTTP_404_NOT_FOUND
        )

    if request.method == "GET":
        serializer = AnomalySerializer(anomaly)
        return Response(serializer.data)

    if request.method in ("PUT", "PATCH"):
        partial = request.method == "PATCH"
        serializer = AnomalySerializer(anomaly, data=request.data, partial=partial)
        if serializer.is_valid():
            updated = serializer.save()
            log_governance_action(
                actor=request.user,
                action="update_anomaly",
                details={"anomaly_id": anomaly.id, "status": updated.status},
            )
            return Response(AnomalySerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    anomaly.delete()
    log_governance_action(
        actor=request.user,
        action="delete_anomaly",
        details={"anomaly_id": anomaly.id},
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def anomaly_resolve_view(request, pk):
    """Mark an anomaly as resolved."""
    try:
        anomaly = Anomaly.objects.get(pk=pk)
    except Anomaly.DoesNotExist:
        return Response(
            {"detail": "Anomaly not found."}, status=status.HTTP_404_NOT_FOUND
        )

    resolution_notes = request.data.get("resolution_notes", "")
    anomaly.status = Anomaly.Status.RESOLVED
    anomaly.resolved_by = request.user
    anomaly.resolution_notes = resolution_notes
    anomaly.resolved_at = timezone.now()
    anomaly.save(
        update_fields=["status", "resolved_by", "resolution_notes", "resolved_at"]
    )

    log_governance_action(
        actor=request.user,
        action="resolve_anomaly",
        details={"anomaly_id": anomaly.id},
    )
    return Response(
        {
            "detail": "Anomaly resolved successfully.",
            "anomaly": AnomalySerializer(anomaly).data,
        }
    )


# ---------------------------------------------------------------------------
# PAYMENTS AUDIT
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def payment_audit_list_view(request):
    """List payment audit records with optional filters."""
    queryset = PaymentAudit.objects.all().order_by("-created_at")

    user_id = request.query_params.get("user_id")
    if user_id:
        queryset = queryset.filter(user_id=user_id)

    payment_source = request.query_params.get("payment_source")
    if payment_source:
        queryset = queryset.filter(payment_source=payment_source)

    event_type = request.query_params.get("event_type")
    if event_type:
        queryset = queryset.filter(event_type=event_type)

    serializer = PaymentAuditSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def payment_audit_detail_view(request, pk):
    """Retrieve a single payment audit record."""
    try:
        audit = PaymentAudit.objects.get(pk=pk)
    except PaymentAudit.DoesNotExist:
        return Response(
            {"detail": "Payment audit not found."}, status=status.HTTP_404_NOT_FOUND
        )
    serializer = PaymentAuditSerializer(audit)
    return Response(serializer.data)


# ---------------------------------------------------------------------------
# TRANSACTION RECONCILIATION
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def transaction_reconciliation_list_create_view(request):
    """List or create transaction reconciliation records."""
    if request.method == "GET":
        queryset = TransactionReconciliation.objects.all().order_by(
            "-transaction_date", "-created_at"
        )
        serializer = TransactionReconciliationSerializer(queryset, many=True)
        return Response(serializer.data)

    serializer = TransactionReconciliationSerializer(data=request.data)
    if serializer.is_valid():
        reconciliation = serializer.save()
        log_governance_action(
            actor=request.user,
            action="create_reconciliation",
            details={"reconciliation_id": reconciliation.id},
        )
        return Response(
            TransactionReconciliationSerializer(reconciliation).data,
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsSuperAdmin])
def transaction_reconciliation_detail_view(request, pk):
    """Retrieve or update a reconciliation record."""
    try:
        reconciliation = TransactionReconciliation.objects.get(pk=pk)
    except TransactionReconciliation.DoesNotExist:
        return Response(
            {"detail": "Reconciliation record not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        serializer = TransactionReconciliationSerializer(reconciliation)
        return Response(serializer.data)

    partial = request.method == "PATCH"
    serializer = TransactionReconciliationSerializer(
        reconciliation, data=request.data, partial=partial
    )
    if serializer.is_valid():
        updated = serializer.save()
        log_governance_action(
            actor=request.user,
            action="update_reconciliation",
            details={"reconciliation_id": reconciliation.id, "status": updated.status},
        )
        return Response(TransactionReconciliationSerializer(updated).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def transaction_reconciliation_verify_view(request, pk):
    """Mark a reconciliation record as verified."""
    try:
        reconciliation = TransactionReconciliation.objects.get(pk=pk)
    except TransactionReconciliation.DoesNotExist:
        return Response(
            {"detail": "Reconciliation record not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    reconciliation.is_verified = True
    reconciliation.verified_by = request.user
    reconciliation.save(update_fields=["is_verified", "verified_by"])

    log_governance_action(
        actor=request.user,
        action="verify_reconciliation",
        details={"reconciliation_id": reconciliation.id},
    )
    return Response(
        {
            "detail": "Reconciliation verified.",
            "reconciliation": TransactionReconciliationSerializer(reconciliation).data,
        }
    )


# ---------------------------------------------------------------------------
# SYSTEM LOGS
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def system_log_list_view(request):
    """List system logs with optional filters."""
    queryset = SystemLog.objects.all().order_by("-created_at")

    level = request.query_params.get("level")
    if level:
        queryset = queryset.filter(level=level)

    logger_name = request.query_params.get("logger_name")
    if logger_name:
        queryset = queryset.filter(logger_name=logger_name)

    serializer = SystemLogSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def system_log_detail_view(request, pk):
    """Retrieve a single system log."""
    try:
        log = SystemLog.objects.get(pk=pk)
    except SystemLog.DoesNotExist:
        return Response(
            {"detail": "System log not found."}, status=status.HTTP_404_NOT_FOUND
        )
    serializer = SystemLogSerializer(log)
    return Response(serializer.data)


# ---------------------------------------------------------------------------
# COMPLIANCE TRAILS
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def compliance_trail_list_create_view(request):
    """List or create compliance trail records."""
    if request.method == "GET":
        queryset = ComplianceTrail.objects.all().order_by("-created_at")
        serializer = ComplianceTrailSerializer(queryset, many=True)
        return Response(serializer.data)

    serializer = ComplianceTrailSerializer(data=request.data)
    if serializer.is_valid():
        trail = serializer.save()
        log_governance_action(
            actor=request.user,
            action="create_compliance_trail",
            details={"trail_id": trail.id, "category": trail.category},
        )
        return Response(
            ComplianceTrailSerializer(trail).data, status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsSuperAdmin])
def compliance_trail_detail_view(request, pk):
    """Retrieve or update a compliance trail."""
    try:
        trail = ComplianceTrail.objects.get(pk=pk)
    except ComplianceTrail.DoesNotExist:
        return Response(
            {"detail": "Compliance trail not found."}, status=status.HTTP_404_NOT_FOUND
        )

    if request.method == "GET":
        serializer = ComplianceTrailSerializer(trail)
        return Response(serializer.data)

    partial = request.method == "PATCH"
    serializer = ComplianceTrailSerializer(trail, data=request.data, partial=partial)
    if serializer.is_valid():
        updated = serializer.save()
        log_governance_action(
            actor=request.user,
            action="update_compliance_trail",
            details={"trail_id": trail.id},
        )
        return Response(ComplianceTrailSerializer(updated).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# DATA ACCESS AUDIT
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def data_access_audit_list_view(request):
    """List data access audit records."""
    queryset = DataAccessAudit.objects.all().order_by("-created_at")

    user_id = request.query_params.get("user_id")
    if user_id:
        queryset = queryset.filter(user_id=user_id)

    access_type = request.query_params.get("access_type")
    if access_type:
        queryset = queryset.filter(access_type=access_type)

    resource_type = request.query_params.get("resource_type")
    if resource_type:
        queryset = queryset.filter(resource_type=resource_type)

    serializer = DataAccessAuditSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def data_access_audit_detail_view(request, pk):
    """Retrieve a single data access audit record."""
    try:
        audit = DataAccessAudit.objects.get(pk=pk)
    except DataAccessAudit.DoesNotExist:
        return Response(
            {"detail": "Data access audit not found."}, status=status.HTTP_404_NOT_FOUND
        )
    serializer = DataAccessAuditSerializer(audit)
    return Response(serializer.data)


# ---------------------------------------------------------------------------
# SECURITY EVENTS & ALERTS
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def security_event_list_create_view(request):
    """List or create security events."""
    if request.method == "GET":
        queryset = SecurityEvent.objects.all().order_by("-created_at")

        event_type = request.query_params.get("event_type")
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        severity = request.query_params.get("severity")
        if severity:
            queryset = queryset.filter(severity=severity)

        is_resolved = request.query_params.get("is_resolved")
        if is_resolved is not None:
            queryset = queryset.filter(is_resolved=is_resolved.lower() == "true")

        serializer = SecurityEventSerializer(queryset, many=True)
        return Response(serializer.data)

    serializer = SecurityEventSerializer(data=request.data)
    if serializer.is_valid():
        event = serializer.save()
        log_governance_action(
            actor=request.user,
            action="create_security_event",
            details={"event_id": event.id, "event_type": event.event_type},
        )
        return Response(
            SecurityEventSerializer(event).data, status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def security_event_detail_view(request, pk):
    """Retrieve or update a security event."""
    try:
        event = SecurityEvent.objects.get(pk=pk)
    except SecurityEvent.DoesNotExist:
        return Response(
            {"detail": "Security event not found."}, status=status.HTTP_404_NOT_FOUND
        )

    if request.method == "GET":
        serializer = SecurityEventSerializer(event)
        return Response(serializer.data)

    partial = request.method == "POST"  # use partial update for POST as well
    serializer = SecurityEventSerializer(event, data=request.data, partial=partial)
    if serializer.is_valid():
        updated = serializer.save()
        log_governance_action(
            actor=request.user,
            action="update_security_event",
            details={"event_id": event.id, "is_resolved": updated.is_resolved},
        )
        return Response(SecurityEventSerializer(updated).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def security_event_resolve_view(request, pk):
    """Mark a security event as resolved."""
    try:
        event = SecurityEvent.objects.get(pk=pk)
    except SecurityEvent.DoesNotExist:
        return Response(
            {"detail": "Security event not found."}, status=status.HTTP_404_NOT_FOUND
        )

    resolution_notes = request.data.get("resolution_notes", "")
    event.is_resolved = True
    event.resolved_by = request.user
    event.resolution_notes = resolution_notes
    event.resolved_at = timezone.now()
    event.save(
        update_fields=["is_resolved", "resolved_by", "resolution_notes", "resolved_at"]
    )

    log_governance_action(
        actor=request.user,
        action="resolve_security_event",
        details={"event_id": event.id},
    )
    return Response(
        {
            "detail": "Security event resolved.",
            "event": SecurityEventSerializer(event).data,
        }
    )
