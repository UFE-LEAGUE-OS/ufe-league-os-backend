from django.contrib import admin

from .models import (
    PlayerRegistration,
    PlayerTransfer,
    Squad,
    SquadMember,
    SquadSubmission,
    StaffMember,
    Team,
)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "team_type", "is_active", "created_at"]
    list_filter = ["club", "team_type", "is_active", "created_at"]
    search_fields = ["name", "short_name", "club__name"]
    ordering = ["club__name", "team_type", "name"]


@admin.register(Squad)
class SquadAdmin(admin.ModelAdmin):
    list_display = ["name", "team", "competition", "season", "status", "submitted_at"]
    list_filter = ["status", "competition", "season"]
    search_fields = ["name", "team__name", "competition__name"]
    ordering = ["-created_at"]


@admin.register(PlayerRegistration)
class PlayerRegistrationAdmin(admin.ModelAdmin):
    list_display = [
        "full_name",
        "registration_number",
        "club",
        "team",
        "position",
        "status",
        "player_type",
        "registered_date",
    ]
    list_filter = ["club", "team", "status", "player_type", "registered_date"]
    search_fields = [
        "first_name",
        "last_name",
        "registration_number",
        "position",
        "nationality",
    ]
    ordering = ["club__name", "team__name", "last_name", "first_name"]
    readonly_fields = ["full_name"]


@admin.register(SquadMember)
class SquadMemberAdmin(admin.ModelAdmin):
    list_display = [
        "player",
        "squad",
        "jersey_number",
        "position",
        "is_captain",
        "is_vice_captain",
    ]
    list_filter = ["squad", "is_captain", "is_vice_captain"]
    search_fields = [
        "player__first_name",
        "player__last_name",
        "squad__name",
        "position",
    ]
    ordering = ["squad", "jersey_number", "player__last_name"]


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = [
        "full_name",
        "club",
        "team",
        "role",
        "employment_type",
        "is_active",
        "start_date",
    ]
    list_filter = ["club", "team", "role", "employment_type", "is_active"]
    search_fields = ["first_name", "last_name", "role", "email", "phone_number"]
    ordering = ["club__name", "team__name", "role", "last_name"]
    readonly_fields = ["full_name"]


@admin.register(PlayerTransfer)
class PlayerTransferAdmin(admin.ModelAdmin):
    list_display = [
        "transfer_number",
        "player",
        "from_club",
        "to_club",
        "transfer_type",
        "transfer_fee",
        "currency",
        "transfer_date",
        "status",
    ]
    list_filter = ["status", "transfer_type", "transfer_date", "from_club", "to_club"]
    search_fields = [
        "transfer_number",
        "player__first_name",
        "player__last_name",
        "notes",
    ]
    ordering = ["-transfer_date", "-created_at"]
    readonly_fields = ["transfer_number"]


@admin.register(SquadSubmission)
class SquadSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        "submission_number",
        "squad",
        "status",
        "submitted_by",
        "submitted_at",
        "iteration",
    ]
    list_filter = ["status", "submitted_at", "iteration"]
    search_fields = ["submission_number", "squad__name", "rejection_reason"]
    ordering = ["-created_at"]
    readonly_fields = ["submission_number"]
