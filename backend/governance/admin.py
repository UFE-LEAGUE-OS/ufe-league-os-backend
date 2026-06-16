from django.contrib import admin

from .models import CompetitionFormat, LeagueStandard, Rule, SportVariant


@admin.register(SportVariant)
class SportVariantAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "slug",
        "players_per_team",
        "match_duration_minutes",
        "is_active",
        "is_verified",
        "created_at",
    ]
    list_filter = ["is_active", "is_verified"]
    search_fields = ["name", "description"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]


@admin.register(CompetitionFormat)
class CompetitionFormatAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "slug",
        "stage_type",
        "is_active",
        "is_verified",
        "created_at",
    ]
    list_filter = ["stage_type", "is_active", "is_verified"]
    search_fields = ["name", "description"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "rule_number",
        "category",
        "priority",
        "version",
        "is_active",
        "is_published",
        "created_at",
    ]
    list_filter = ["category", "priority", "is_active", "is_published"]
    search_fields = ["title", "rule_number", "description"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ["created_at", "updated_at", "published_at"]


@admin.register(LeagueStandard)
class LeagueStandardAdmin(admin.ModelAdmin):
    list_display = [
        "rule",
        "league",
        "is_accepted",
        "assigned_at",
    ]
    list_filter = ["is_accepted"]
    search_fields = ["rule__title", "league__name"]
    readonly_fields = ["assigned_at", "updated_at"]
