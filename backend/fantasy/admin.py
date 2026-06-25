from django.contrib import admin

from .models import (
    FantasyCompetition,
    FantasyGameweek,
    FantasyLeague,
    FantasyLeagueMembership,
    FantasyLineup,
    FantasyLineupPlayer,
    FantasyPlayer,
    FantasyPlayerGameweekScore,
    FantasySquadPlayer,
    FantasyTeam,
    FantasyTeamGameweekScore,
)


class FantasySquadPlayerInline(admin.TabularInline):
    model = FantasySquadPlayer
    extra = 0
    readonly_fields = ("joined_at", "removed_at")


class FantasyLineupPlayerInline(admin.TabularInline):
    model = FantasyLineupPlayer
    extra = 0


@admin.register(FantasyCompetition)
class FantasyCompetitionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sport",
        "linked_competition",
        "status",
        "budget",
        "squad_size",
        "lineup_size",
        "max_players_per_club",
        "created_at",
    )
    list_filter = ("sport", "status")
    search_fields = ("name", "slug", "linked_competition__name")


@admin.register(FantasyGameweek)
class FantasyGameweekAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "fantasy_competition",
        "number",
        "status",
        "start_at",
        "lock_at",
        "end_at",
    )
    list_filter = ("status", "fantasy_competition")
    search_fields = ("name", "fantasy_competition__name")
    filter_horizontal = ("matches",)


@admin.register(FantasyPlayer)
class FantasyPlayerAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "fantasy_competition",
        "club",
        "position",
        "calculated_price",
        "final_price",
        "price_source",
        "is_active",
        "is_available",
    )
    list_filter = (
        "fantasy_competition",
        "club",
        "position",
        "price_source",
        "is_active",
        "is_available",
    )
    search_fields = ("display_name", "club__name", "fantasy_competition__name")


@admin.register(FantasyTeam)
class FantasyTeamAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "fantasy_competition",
        "total_points",
        "current_rank",
        "created_at",
    )
    list_filter = ("fantasy_competition",)
    search_fields = ("name", "owner__email", "fantasy_competition__name")
    inlines = [FantasySquadPlayerInline]


@admin.register(FantasySquadPlayer)
class FantasySquadPlayerAdmin(admin.ModelAdmin):
    list_display = (
        "fantasy_team",
        "fantasy_player",
        "price_at_selection",
        "is_active",
        "joined_at",
        "removed_at",
    )
    list_filter = ("is_active", "fantasy_player__club")
    search_fields = ("fantasy_team__name", "fantasy_player__display_name")


@admin.register(FantasyLineup)
class FantasyLineupAdmin(admin.ModelAdmin):
    list_display = (
        "fantasy_team",
        "gameweek",
        "captain",
        "vice_captain",
        "submitted_at",
        "locked_at",
    )
    list_filter = ("gameweek",)
    search_fields = ("fantasy_team__name", "captain__display_name")
    inlines = [FantasyLineupPlayerInline]


@admin.register(FantasyLineupPlayer)
class FantasyLineupPlayerAdmin(admin.ModelAdmin):
    list_display = ("lineup", "fantasy_player", "is_starter", "sort_order")
    list_filter = ("is_starter",)
    search_fields = ("lineup__fantasy_team__name", "fantasy_player__display_name")


@admin.register(FantasyLeague)
class FantasyLeagueAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "fantasy_competition",
        "league_type",
        "join_code",
        "created_by",
        "is_active",
        "created_at",
    )
    list_filter = ("league_type", "is_active", "fantasy_competition")
    search_fields = ("name", "join_code", "created_by__email")


@admin.register(FantasyLeagueMembership)
class FantasyLeagueMembershipAdmin(admin.ModelAdmin):
    list_display = ("fantasy_league", "fantasy_team", "joined_at")
    search_fields = ("fantasy_league__name", "fantasy_team__name")


@admin.register(FantasyPlayerGameweekScore)
class FantasyPlayerGameweekScoreAdmin(admin.ModelAdmin):
    list_display = (
        "fantasy_player",
        "gameweek",
        "match",
        "points",
        "status",
        "entered_by",
        "approved_by",
        "approved_at",
    )
    list_filter = ("status", "gameweek")
    search_fields = ("fantasy_player__display_name", "entered_by__email")


@admin.register(FantasyTeamGameweekScore)
class FantasyTeamGameweekScoreAdmin(admin.ModelAdmin):
    list_display = (
        "fantasy_team",
        "gameweek",
        "points",
        "rank",
        "calculated_at",
    )
    list_filter = ("gameweek",)
    search_fields = ("fantasy_team__name",)
