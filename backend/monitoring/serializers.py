from rest_framework import serializers

from .models import (
    Anomaly,
    PaymentAudit,
    ApprovalLog,
    ChargebackRefund,
    TransactionReconciliation,
    SystemLog,
    ComplianceTrail,
    DataAccessAudit,
    SecurityEvent,
)


class ApprovalLogSerializer(serializers.ModelSerializer):
    actor = serializers.StringRelatedField()
    content_object_str = serializers.StringRelatedField(
        source="content_object", read_only=True
    )

    class Meta:
        model = ApprovalLog
        fields = [
            "id",
            "actor",
            "action",
            "category",
            "notes",
            "created_at",
            "content_type",
            "object_id",
            "content_object_str",
        ]
        read_only_fields = ["id", "created_at", "actor", "content_object_str"]


class ChargebackRefundSerializer(serializers.ModelSerializer):
    opened_by = serializers.StringRelatedField()
    handled_by = serializers.StringRelatedField()
    payment_object_str = serializers.StringRelatedField(
        source="payment_object", read_only=True
    )

    class Meta:
        model = ChargebackRefund
        fields = "__all__"


class AnomalySerializer(serializers.ModelSerializer):
    affected_user_email = serializers.CharField(
        source="affected_user.email", read_only=True
    )
    assigned_to_email = serializers.CharField(
        source="assigned_to.email", read_only=True
    )

    class Meta:
        model = Anomaly
        fields = [
            "id",
            "anomaly_type",
            "severity",
            "status",
            "title",
            "description",
            "detection_source",
            "affected_user",
            "affected_user_email",
            "related_object_type",
            "related_object_id",
            "metadata",
            "assigned_to",
            "assigned_to_email",
            "resolved_by",
            "resolution_notes",
            "created_at",
            "updated_at",
            "resolved_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "resolved_at"]


class PaymentAuditSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = PaymentAudit
        fields = [
            "id",
            "user",
            "user_email",
            "payment_source",
            "event_type",
            "amount",
            "currency",
            "reference",
            "provider",
            "provider_reference",
            "status",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class TransactionReconciliationSerializer(serializers.ModelSerializer):
    verified_by_email = serializers.CharField(
        source="verified_by.email", read_only=True
    )

    class Meta:
        model = TransactionReconciliation
        fields = [
            "id",
            "transaction_date",
            "source_system",
            "external_reference",
            "internal_reference",
            "amount",
            "currency",
            "status",
            "is_verified",
            "verified_by",
            "verified_by_email",
            "notes",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SystemLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemLog
        fields = [
            "id",
            "level",
            "logger_name",
            "message",
            "path",
            "method",
            "status_code",
            "ip_address",
            "user_email",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ComplianceTrailSerializer(serializers.ModelSerializer):
    assessed_by_email = serializers.CharField(
        source="assessed_by.email", read_only=True
    )

    class Meta:
        model = ComplianceTrail
        fields = [
            "id",
            "category",
            "title",
            "description",
            "regulation_reference",
            "is_compliant",
            "violation_details",
            "corrective_action",
            "assessed_by",
            "assessed_by_email",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class DataAccessAuditSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = DataAccessAudit
        fields = [
            "id",
            "user",
            "user_email",
            "access_type",
            "resource_type",
            "resource_id",
            "resource_name",
            "ip_address",
            "user_agent",
            "is_authorized",
            "denial_reason",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class SecurityEventSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    resolved_by_email = serializers.CharField(
        source="resolved_by.email", read_only=True
    )

    class Meta:
        model = SecurityEvent
        fields = [
            "id",
            "event_type",
            "severity",
            "user",
            "user_email",
            "ip_address",
            "user_agent",
            "description",
            "is_resolved",
            "resolved_by",
            "resolved_by_email",
            "resolution_notes",
            "metadata",
            "created_at",
            "resolved_at",
        ]
        read_only_fields = ["id", "created_at", "resolved_at"]
