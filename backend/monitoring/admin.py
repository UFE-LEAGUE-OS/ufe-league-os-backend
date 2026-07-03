from django.contrib import admin
from .models import (
    Anomaly,
    PaymentAudit,
    TransactionReconciliation,
    SystemLog,
    ComplianceTrail,
    DataAccessAudit,
    SecurityEvent,
)


@admin.register(Anomaly)
class AnomalyAdmin(admin.ModelAdmin):
    list_display = (
        "anomaly_type",
        "severity",
        "status",
        "title",
        "affected_user",
        "assigned_to",
        "created_at",
    )
    list_filter = ("severity", "status", "anomaly_type", "created_at")
    search_fields = ("title", "description", "detection_source")
    date_hierarchy = "created_at"


@admin.register(PaymentAudit)
class PaymentAuditAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "payment_source",
        "event_type",
        "amount",
        "reference",
        "status",
        "created_at",
    )
    list_filter = ("payment_source", "event_type", "created_at")
    search_fields = ("user__email", "reference", "provider", "provider_reference")
    date_hierarchy = "created_at"


@admin.register(TransactionReconciliation)
class TransactionReconciliationAdmin(admin.ModelAdmin):
    list_display = (
        "source_system",
        "external_reference",
        "internal_reference",
        "amount",
        "status",
        "is_verified",
        "verified_by",
        "transaction_date",
    )
    list_filter = ("status", "source_system", "is_verified", "transaction_date")
    search_fields = ("external_reference", "internal_reference", "notes")
    date_hierarchy = "transaction_date"


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = (
        "level",
        "logger_name",
        "message",
        "path",
        "status_code",
        "user_email",
        "created_at",
    )
    list_filter = ("level", "logger_name", "created_at")
    search_fields = ("message", "logger_name", "path", "user_email")
    date_hierarchy = "created_at"


@admin.register(ComplianceTrail)
class ComplianceTrailAdmin(admin.ModelAdmin):
    list_display = ("category", "title", "is_compliant", "assessed_by", "created_at")
    list_filter = ("category", "is_compliant", "created_at")
    search_fields = (
        "title",
        "description",
        "regulation_reference",
        "violation_details",
    )
    date_hierarchy = "created_at"


@admin.register(DataAccessAudit)
class DataAccessAuditAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "access_type",
        "resource_type",
        "resource_name",
        "is_authorized",
        "created_at",
    )
    list_filter = ("access_type", "resource_type", "is_authorized", "created_at")
    search_fields = (
        "user__email",
        "resource_name",
        "ip_address",
        "user_agent",
        "denial_reason",
    )
    date_hierarchy = "created_at"


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = (
        "event_type",
        "severity",
        "user",
        "description",
        "is_resolved",
        "resolved_by",
        "created_at",
    )
    list_filter = ("event_type", "severity", "is_resolved", "created_at")
    search_fields = (
        "description",
        "user__email",
        "ip_address",
        "user_agent",
        "resolution_notes",
    )
    date_hierarchy = "created_at"
