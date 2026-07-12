from django.contrib import admin

from .models import (
    Competition,
    FixtureOfficialAssignment,
    League,
    LeagueAdminScope,
    Match,
    Standing,
    Union,
    UnionMatchOfficial,
)


@admin.register(Union)
class UnionAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "country", "founded_year", "created_at"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "country"]


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "union", "is_active", "created_at"]
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ["is_active", "union"]
    search_fields = ["name", "union__name"]


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "league", "season", "is_active", "start_date"]
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ["is_active", "league"]
    search_fields = ["name", "league__name"]


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = [
        "home_club",
        "away_club",
        "competition",
        "status",
        "match_date",
        "home_score",
        "away_score",
    ]
    list_filter = ["status", "competition", "match_date"]
    search_fields = ["home_club__name", "away_club__name", "venue"]


@admin.register(Standing)
class StandingAdmin(admin.ModelAdmin):
    list_display = [
        "competition",
        "club",
        "position",
        "played",
        "points",
    ]
    list_filter = ["competition"]
    search_fields = ["club__name", "competition__name"]


@admin.register(LeagueAdminScope)
class LeagueAdminScopeAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "league",
        "competition",
        "role",
        "is_active",
        "updated_at",
    ]
    list_filter = ["role", "is_active", "league", "competition"]
    search_fields = ["user__email", "league__name", "competition__name"]


@admin.register(UnionMatchOfficial)
class UnionMatchOfficialAdmin(admin.ModelAdmin):
    list_display = [
        "full_name",
        "union",
        "role_type",
        "status",
        "email",
    ]
    list_filter = ["union", "role_type", "status", "primary_sport"]
    search_fields = ["full_name", "email", "phone_number"]


@admin.register(FixtureOfficialAssignment)
class FixtureOfficialAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        "match",
        "official",
        "role_type",
        "status",
        "responded_at",
    ]
    list_filter = ["status", "role_type", "match__competition"]
    search_fields = [
        "official__full_name",
        "official__email",
        "match__home_club__name",
        "match__away_club__name",
    ]
