from rest_framework import serializers

from .models import Competition, League, LeagueClubMembership, Season
from .serializers import MatchListSerializer


class LeagueManagementSerializer(serializers.ModelSerializer):
    union_name = serializers.CharField(source="union.name", read_only=True)
    sport = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()

    class Meta:
        model = League
        fields = [
            "id",
            "name",
            "slug",
            "union",
            "union_name",
            "sport",
            "description",
            "logo_url",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_sport(self, obj):
        workspace = getattr(getattr(obj, "union", None), "workspace", None)
        return getattr(workspace, "sport", "") or getattr(obj, "sport", "") or ""

    def get_description(self, obj):
        return getattr(obj, "description", "") or ""

    def get_logo_url(self, obj):
        logo = getattr(obj, "logo", None)
        if not logo:
            return None

        url = getattr(logo, "url", None)
        if not url:
            return None

        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(url)

        return url

    def get_is_active(self, obj):
        return bool(getattr(obj, "is_active", True))

    def get_created_at(self, obj):
        value = getattr(obj, "created_at", None)
        return value.isoformat() if value else None

    def get_updated_at(self, obj):
        value = getattr(obj, "updated_at", None)
        return value.isoformat() if value else None


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
