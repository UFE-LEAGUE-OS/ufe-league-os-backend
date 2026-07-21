from django.contrib import admin

from .models import (
    Announcement,
    ClubDocument,
    ClubOperationAuditLog,
    ComplianceChecklist,
    CommunicationLog,
    CampaignAssignment,
    MatchdayOperationTask,
    MatchdayReport,
    SponsorCampaign,
    TicketingOfficerAssignment,
)


@admin.register(ClubDocument)
class ClubDocumentAdmin(admin.ModelAdmin):
    list_display = [
        "club",
        "title",
        "category",
        "status",
        "expiry_date",
        "uploaded_by",
        "uploaded_at",
    ]
    list_filter = ["category", "status", "club", "uploaded_at"]
    search_fields = ["club__name", "title", "description", "notes"]
    readonly_fields = ["uploaded_by", "uploaded_at", "created_at", "updated_at"]
    date_hierarchy = "uploaded_at"


@admin.register(ComplianceChecklist)
class ComplianceChecklistAdmin(admin.ModelAdmin):
    list_display = [
        "club",
        "title",
        "priority",
        "status",
        "completed",
        "due_date",
        "completed_by",
        "completed_at",
    ]
    list_filter = ["priority", "status", "completed", "club", "due_date"]
    search_fields = ["club__name", "title", "description", "notes"]
    readonly_fields = ["completed_by", "completed_at", "created_at", "updated_at"]
    date_hierarchy = "due_date"


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = [
        "club",
        "title",
        "audience",
        "priority",
        "is_published",
        "published_at",
        "expires_at",
        "created_by",
    ]
    list_filter = ["audience", "priority", "is_published", "club"]
    search_fields = ["club__name", "title", "message"]
    readonly_fields = [
        "created_by",
        "created_at",
        "published_at",
        "is_deleted",
        "deleted_at",
    ]
    date_hierarchy = "created_at"


@admin.register(CommunicationLog)
class CommunicationLogAdmin(admin.ModelAdmin):
    list_display = [
        "club",
        "communication_type",
        "title",
        "audience",
        "sender",
        "status",
        "sent_at",
    ]
    list_filter = ["communication_type", "status", "club"]
    search_fields = ["club__name", "title", "audience"]
    readonly_fields = ["sender", "sent_at", "metadata", "related_announcement"]
    date_hierarchy = "sent_at"


@admin.register(SponsorCampaign)
class SponsorCampaignAdmin(admin.ModelAdmin):
    list_display = [
        "club",
        "sponsor",
        "name",
        "campaign_type",
        "status",
        "start_date",
        "end_date",
        "budget",
        "created_by",
    ]
    list_filter = [
        "status",
        "campaign_type",
        "club",
        "sponsor",
        "start_date",
        "end_date",
    ]
    search_fields = ["club__name", "sponsor__name", "name", "description", "notes"]
    readonly_fields = [
        "created_by",
        "created_at",
        "updated_at",
        "is_deleted",
        "deleted_at",
    ]
    date_hierarchy = "start_date"


@admin.register(CampaignAssignment)
class CampaignAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        "campaign",
        "match",
        "sponsor_package",
        "activation_status",
        "created_by",
        "created_at",
    ]
    list_filter = ["activation_status", "campaign__club", "match", "campaign__sponsor"]
    search_fields = [
        "campaign__name",
        "campaign__club__name",
        "activation_notes",
        "branding_locations",
    ]
    readonly_fields = ["created_by", "created_at", "updated_at"]
    date_hierarchy = "created_at"


@admin.register(MatchdayOperationTask)
class MatchdayOperationTaskAdmin(admin.ModelAdmin):
    list_display = [
        "club",
        "match",
        "title",
        "category",
        "priority",
        "status",
        "assigned_to",
        "due_date",
        "created_by",
    ]
    list_filter = [
        "status",
        "priority",
        "category",
        "club",
        "match",
        "assigned_to",
        "due_date",
    ]
    search_fields = ["club__name", "match__name", "title", "description", "notes"]
    readonly_fields = [
        "created_by",
        "created_at",
        "updated_at",
        "is_deleted",
        "deleted_at",
        "completed_at",
        "completed_by",
    ]
    date_hierarchy = "due_date"


@admin.register(TicketingOfficerAssignment)
class TicketingOfficerAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        "club",
        "match",
        "officer",
        "assignment_role",
        "gate_allocation",
        "shift_start",
        "shift_end",
        "status",
        "assigned_by",
    ]
    list_filter = [
        "status",
        "assignment_role",
        "club",
        "match",
        "officer",
        "shift_start",
    ]
    search_fields = [
        "club__name",
        "match__name",
        "officer__email",
        "officer__first_name",
        "officer__last_name",
        "gate_allocation",
        "notes",
    ]
    readonly_fields = ["assigned_by", "created_at", "updated_at"]
    date_hierarchy = "match__match_date"


@admin.register(MatchdayReport)
class MatchdayReportAdmin(admin.ModelAdmin):
    list_display = [
        "club",
        "match",
        "status",
        "submitted_by",
        "submitted_at",
        "reviewed_by",
        "reviewed_at",
    ]
    list_filter = ["status", "club", "match", "submitted_by", "reviewed_by"]
    search_fields = [
        "club__name",
        "match__name",
        "successes",
        "challenges",
        "recommendations",
        "incidents",
    ]
    readonly_fields = [
        "submitted_by",
        "submitted_at",
        "reviewed_by",
        "reviewed_at",
        "created_at",
        "updated_at",
        "is_deleted",
        "deleted_at",
    ]
    date_hierarchy = "created_at"


@admin.register(ClubOperationAuditLog)
class ClubOperationAuditLogAdmin(admin.ModelAdmin):
    list_display = [
        "club",
        "user",
        "action",
        "target_content_type",
        "target_object_id",
        "timestamp",
    ]
    list_filter = ["action", "club", "user", "timestamp"]
    search_fields = ["club__name", "user__email", "description", "action"]
    readonly_fields = [
        "club",
        "user",
        "action",
        "target_object_id",
        "target_content_type",
        "description",
        "metadata",
        "ip_address",
        "timestamp",
    ]
    date_hierarchy = "timestamp"
