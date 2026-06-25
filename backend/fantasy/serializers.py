from rest_framework import serializers

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


class FantasyCompetitionSerializer(serializers.ModelSerializer):
    linked_competition_label = serializers.SerializerMethodField()
    teams_count = serializers.IntegerField(source="teams.count", read_only=True)
    gameweeks_count = serializers.IntegerField(source="gameweeks.count", read_only=True)

    class Meta:
        model = FantasyCompetition
        fields = [
            "id",
            "name",
            "slug",
            "linked_competition",
            "linked_competition_label",
            "sport",
            "season",
            "status",
            "budget",
            "squad_size",
            "lineup_size",
            "max_players_per_club",
            "captain_multiplier",
            "min_player_price",
            "max_player_price",
            "default_player_price",
            "rules_summary",
            "teams_count",
            "gameweeks_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "linked_competition_label",
            "teams_count",
            "gameweeks_count",
            "created_at",
            "updated_at",
        ]

    def get_linked_competition_label(self, obj):
        return str(obj.linked_competition)


class FantasyGameweekSerializer(serializers.ModelSerializer):
    fantasy_competition_name = serializers.CharField(
        source="fantasy_competition.name",
        read_only=True,
    )
    matches_count = serializers.IntegerField(source="matches.count", read_only=True)
    is_locked = serializers.BooleanField(read_only=True)
    can_submit_lineup = serializers.BooleanField(read_only=True)

    class Meta:
        model = FantasyGameweek
        fields = [
            "id",
            "fantasy_competition",
            "fantasy_competition_name",
            "name",
            "number",
            "matches",
            "matches_count",
            "start_at",
            "lock_at",
            "end_at",
            "status",
            "is_locked",
            "can_submit_lineup",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "fantasy_competition_name",
            "matches_count",
            "is_locked",
            "can_submit_lineup",
            "created_at",
            "updated_at",
        ]


class FantasyPlayerSerializer(serializers.ModelSerializer):
    fantasy_competition_name = serializers.CharField(
        source="fantasy_competition.name",
        read_only=True,
    )
    club_name = serializers.CharField(source="club.name", read_only=True)
    position_label = serializers.CharField(
        source="get_position_display",
        read_only=True,
    )
    price_source_label = serializers.CharField(
        source="get_price_source_display",
        read_only=True,
    )

    class Meta:
        model = FantasyPlayer
        fields = [
            "id",
            "fantasy_competition",
            "fantasy_competition_name",
            "club",
            "club_name",
            "display_name",
            "position",
            "position_label",
            "calculated_price",
            "final_price",
            "price_source",
            "price_source_label",
            "price_override_reason",
            "price_locked_at",
            "previous_stats",
            "current_form",
            "is_active",
            "is_available",
            "availability_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "fantasy_competition_name",
            "club_name",
            "position_label",
            "price_source_label",
            "price_locked_at",
            "created_at",
            "updated_at",
        ]


class FantasySquadPlayerSerializer(serializers.ModelSerializer):
    fantasy_player_detail = FantasyPlayerSerializer(
        source="fantasy_player",
        read_only=True,
    )

    class Meta:
        model = FantasySquadPlayer
        fields = [
            "id",
            "fantasy_team",
            "fantasy_player",
            "fantasy_player_detail",
            "price_at_selection",
            "is_active",
            "joined_at",
            "removed_at",
        ]
        read_only_fields = [
            "id",
            "fantasy_team",
            "fantasy_player_detail",
            "price_at_selection",
            "joined_at",
            "removed_at",
        ]


class FantasyTeamSerializer(serializers.ModelSerializer):
    fantasy_competition_name = serializers.CharField(
        source="fantasy_competition.name",
        read_only=True,
    )
    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    active_squad_count = serializers.IntegerField(read_only=True)
    budget_used = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    budget_remaining = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    squad_players = serializers.SerializerMethodField()

    class Meta:
        model = FantasyTeam
        fields = [
            "id",
            "owner",
            "owner_email",
            "fantasy_competition",
            "fantasy_competition_name",
            "name",
            "total_points",
            "current_rank",
            "active_squad_count",
            "budget_used",
            "budget_remaining",
            "squad_players",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "owner",
            "owner_email",
            "fantasy_competition_name",
            "total_points",
            "current_rank",
            "active_squad_count",
            "budget_used",
            "budget_remaining",
            "squad_players",
            "created_at",
            "updated_at",
        ]

    def get_squad_players(self, obj):
        queryset = obj.squad_players.filter(is_active=True).select_related(
            "fantasy_player",
            "fantasy_player__club",
        )
        return FantasySquadPlayerSerializer(queryset, many=True).data


class FantasyTeamCreateSerializer(serializers.Serializer):
    fantasy_competition_id = serializers.PrimaryKeyRelatedField(
        queryset=FantasyCompetition.objects.all(),
        source="fantasy_competition",
    )
    name = serializers.CharField(max_length=120)


class FantasySquadUpdateSerializer(serializers.Serializer):
    player_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )


class FantasyLineupPlayerSerializer(serializers.ModelSerializer):
    fantasy_player_detail = FantasyPlayerSerializer(
        source="fantasy_player",
        read_only=True,
    )

    class Meta:
        model = FantasyLineupPlayer
        fields = [
            "id",
            "lineup",
            "fantasy_player",
            "fantasy_player_detail",
            "is_starter",
            "sort_order",
        ]
        read_only_fields = fields


class FantasyLineupSerializer(serializers.ModelSerializer):
    fantasy_team_name = serializers.CharField(
        source="fantasy_team.name",
        read_only=True,
    )
    gameweek_name = serializers.CharField(source="gameweek.name", read_only=True)
    captain_name = serializers.CharField(source="captain.display_name", read_only=True)
    vice_captain_name = serializers.CharField(
        source="vice_captain.display_name",
        read_only=True,
    )
    players = FantasyLineupPlayerSerializer(many=True, read_only=True)
    is_locked = serializers.BooleanField(read_only=True)

    class Meta:
        model = FantasyLineup
        fields = [
            "id",
            "fantasy_team",
            "fantasy_team_name",
            "gameweek",
            "gameweek_name",
            "captain",
            "captain_name",
            "vice_captain",
            "vice_captain_name",
            "submitted_at",
            "locked_at",
            "is_locked",
            "players",
        ]
        read_only_fields = [
            "id",
            "fantasy_team_name",
            "gameweek_name",
            "captain_name",
            "vice_captain_name",
            "submitted_at",
            "locked_at",
            "is_locked",
            "players",
        ]


class FantasyLineupSubmitSerializer(serializers.Serializer):
    gameweek_id = serializers.PrimaryKeyRelatedField(
        queryset=FantasyGameweek.objects.all(),
        source="gameweek",
    )
    player_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    captain_id = serializers.IntegerField(min_value=1)
    vice_captain_id = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True,
    )


class FantasyLeagueSerializer(serializers.ModelSerializer):
    fantasy_competition_name = serializers.CharField(
        source="fantasy_competition.name",
        read_only=True,
    )
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    members_count = serializers.IntegerField(source="memberships.count", read_only=True)

    class Meta:
        model = FantasyLeague
        fields = [
            "id",
            "fantasy_competition",
            "fantasy_competition_name",
            "name",
            "league_type",
            "join_code",
            "created_by",
            "created_by_email",
            "is_active",
            "members_count",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "fantasy_competition_name",
            "join_code",
            "created_by",
            "created_by_email",
            "members_count",
            "created_at",
        ]


class FantasyLeagueCreateSerializer(serializers.Serializer):
    fantasy_competition_id = serializers.PrimaryKeyRelatedField(
        queryset=FantasyCompetition.objects.all(),
        source="fantasy_competition",
    )
    name = serializers.CharField(max_length=160)
    league_type = serializers.ChoiceField(
        choices=FantasyLeague.LeagueType.choices,
        default=FantasyLeague.LeagueType.PUBLIC,
    )


class FantasyLeagueJoinSerializer(serializers.Serializer):
    fantasy_team_id = serializers.PrimaryKeyRelatedField(
        queryset=FantasyTeam.objects.all(),
        source="fantasy_team",
    )
    join_code = serializers.CharField(max_length=20)


class FantasyLeagueMembershipSerializer(serializers.ModelSerializer):
    fantasy_league_detail = FantasyLeagueSerializer(
        source="fantasy_league",
        read_only=True,
    )
    fantasy_team_name = serializers.CharField(
        source="fantasy_team.name",
        read_only=True,
    )

    class Meta:
        model = FantasyLeagueMembership
        fields = [
            "id",
            "fantasy_league",
            "fantasy_league_detail",
            "fantasy_team",
            "fantasy_team_name",
            "joined_at",
        ]
        read_only_fields = fields


class FantasyPlayerGameweekScoreSerializer(serializers.ModelSerializer):
    fantasy_player_name = serializers.CharField(
        source="fantasy_player.display_name",
        read_only=True,
    )
    gameweek_name = serializers.CharField(source="gameweek.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    entered_by_email = serializers.EmailField(source="entered_by.email", read_only=True)
    approved_by_email = serializers.EmailField(
        source="approved_by.email",
        read_only=True,
    )

    class Meta:
        model = FantasyPlayerGameweekScore
        fields = [
            "id",
            "fantasy_player",
            "fantasy_player_name",
            "gameweek",
            "gameweek_name",
            "match",
            "points",
            "breakdown",
            "status",
            "status_label",
            "entered_by",
            "entered_by_email",
            "approved_by",
            "approved_by_email",
            "approved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "fantasy_player_name",
            "gameweek_name",
            "status_label",
            "entered_by",
            "entered_by_email",
            "approved_by",
            "approved_by_email",
            "approved_at",
            "created_at",
            "updated_at",
        ]


class FantasyPlayerScoreSubmitSerializer(serializers.Serializer):
    fantasy_player_id = serializers.PrimaryKeyRelatedField(
        queryset=FantasyPlayer.objects.all(),
        source="fantasy_player",
    )
    match_id = serializers.IntegerField(required=False, allow_null=True)
    points = serializers.DecimalField(max_digits=8, decimal_places=2)
    breakdown = serializers.DictField(required=False)
    status = serializers.ChoiceField(
        choices=FantasyPlayerGameweekScore.Status.choices,
        default=FantasyPlayerGameweekScore.Status.SUBMITTED,
    )


class FantasyPlayerPriceUpdateSerializer(serializers.Serializer):
    final_price = serializers.DecimalField(max_digits=6, decimal_places=2)
    price_override_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )


class FantasyTeamGameweekScoreSerializer(serializers.ModelSerializer):
    fantasy_team_name = serializers.CharField(
        source="fantasy_team.name",
        read_only=True,
    )
    owner_email = serializers.EmailField(
        source="fantasy_team.owner.email", read_only=True
    )
    gameweek_name = serializers.CharField(source="gameweek.name", read_only=True)

    class Meta:
        model = FantasyTeamGameweekScore
        fields = [
            "id",
            "fantasy_team",
            "fantasy_team_name",
            "owner_email",
            "gameweek",
            "gameweek_name",
            "points",
            "rank",
            "breakdown",
            "calculated_at",
        ]
        read_only_fields = fields
