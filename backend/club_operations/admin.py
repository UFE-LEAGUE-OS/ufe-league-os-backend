from django.contrib import admin

from .models import Announcement, ClubDocument, ComplianceChecklist, CommunicationLog


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
