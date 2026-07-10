from rest_framework import serializers

from .models import Competition, League, LeagueClubMembership, Match, Season
from .serializers import MatchListSerializer


class SeasonManagementSerializer(serializers.ModelSerializer):
    league_name = serializers.CharField(source="league.name", read_only=True)

    class Meta:
        model = Season
        fields = [
            "id",
            "league",
            "league_name",
            "name",
            "slug",
            "start_date",
            "end_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class CompetitionManagementSerializer(serializers.ModelSerializer):
    league_name = serializers.CharField(source="league.name", read_only=True)
    season_id = serializers.IntegerField(source="season_record_id", read_only=True)
    season_name = serializers.CharField(source="season_record.name", read_only=True)
    matches_count = serializers.IntegerField(read_only=True)
    clubs_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Competition
        fields = [
            "id",
            "league",
            "league_name",
            "name",
            "slug",
            "season",
            "season_id",
            "season_name",
            "is_active",
            "start_date",
            "end_date",
            "matches_count",
            "clubs_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class LeagueClubMembershipSerializer(serializers.ModelSerializer):
    league_name = serializers.CharField(source="league.name", read_only=True)
    league_slug = serializers.CharField(source="league.slug", read_only=True)
    club_name = serializers.CharField(source="club.name", read_only=True)
    club_slug = serializers.CharField(source="club.slug", read_only=True)
    club_short_name = serializers.CharField(source="club.short_name", read_only=True)
    season_name = serializers.CharField(source="season.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    promoted_from_league_name = serializers.CharField(
        source="promoted_from_league.name",
        read_only=True,
    )
    relegated_to_league_name = serializers.CharField(
        source="relegated_to_league.name",
        read_only=True,
    )

    class Meta:
        model = LeagueClubMembership
        fields = [
            "id",
            "league",
            "league_name",
            "league_slug",
            "club",
            "club_name",
            "club_slug",
            "club_short_name",
            "season",
            "season_name",
            "status",
            "status_display",
            "promoted_from_league",
            "promoted_from_league_name",
            "relegated_to_league",
            "relegated_to_league_name",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class FixtureGenerationResultSerializer(serializers.Serializer):
    competition = CompetitionManagementSerializer(read_only=True)
    created_count = serializers.IntegerField(read_only=True)
    fixtures = MatchListSerializer(many=True, read_only=True)
