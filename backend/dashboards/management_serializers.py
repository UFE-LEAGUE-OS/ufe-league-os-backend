from rest_framework import serializers

from accounts.models import Club
from .models import Competition, League, LeagueClubMembership, Season
from .serializers import MatchListSerializer


class ClubManagementSerializer(serializers.ModelSerializer):
    sport_display = serializers.CharField(source="get_sport_display", read_only=True)
    admin_name = serializers.SerializerMethodField()
    admin_email = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    banner_url = serializers.SerializerMethodField()
    teams = serializers.SerializerMethodField()
    players = serializers.SerializerMethodField()
    compliance = serializers.SerializerMethodField()
    memberships = serializers.SerializerMethodField()

    class Meta:
        model = Club
        fields = [
            "id",
            "name",
            "slug",
            "short_name",
            "sport",
            "sport_display",
            "logo_url",
            "banner_url",
            "primary_color",
            "secondary_color",
            "admin",
            "admin_name",
            "admin_email",
            "teams",
            "players",
            "compliance",
            "memberships",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "sport_display",
            "logo_url",
            "banner_url",
            "admin_name",
            "admin_email",
            "teams",
            "players",
            "compliance",
            "memberships",
            "created_at",
        ]

    def _file_url(self, file_field):
        if not file_field:
            return None

        url = getattr(file_field, "url", None)
        if not url:
            return None

        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url

    def get_logo_url(self, obj):
        return self._file_url(getattr(obj, "logo", None))

    def get_banner_url(self, obj):
        return self._file_url(getattr(obj, "banner", None))

    def get_admin_name(self, obj):
        if not obj.admin:
            return ""
        return obj.admin.get_full_name() or obj.admin.email

    def get_admin_email(self, obj):
        return obj.admin.email if obj.admin else ""

    def get_teams(self, obj):
        return max(1, obj.league_memberships.values("season_id").distinct().count())

    def get_players(self, obj):
        return getattr(obj, "players_count", 0) or 0

    def get_compliance(self, obj):
        if not obj.admin:
            return "Admin needed"
        if not obj.logo:
            return "Logo needed"
        return "Ready"

    def get_memberships(self, obj):
        memberships = obj.league_memberships.select_related(
            "league", "season", "promoted_from_league", "relegated_to_league"
        ).order_by("league__name", "season__name")

        return [
            {
                "id": membership.id,
                "league": membership.league_id,
                "league_name": membership.league.name,
                "season": membership.season_id,
                "season_name": membership.season.name if membership.season else None,
                "status": membership.status,
                "status_display": membership.get_status_display(),
                "promoted_from_league_name": (
                    membership.promoted_from_league.name
                    if membership.promoted_from_league
                    else None
                ),
                "relegated_to_league_name": (
                    membership.relegated_to_league.name
                    if membership.relegated_to_league
                    else None
                ),
                "notes": membership.notes,
            }
            for membership in memberships
        ]


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
