from django.utils import timezone
from rest_framework import serializers

from accounts.models import Club
from .models import (
    Competition,
    FixtureOfficialAssignment,
    League,
    LeagueClubMembership,
    Season,
    UnionMatchOfficial,
)
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


class UnionMatchOfficialManagementSerializer(serializers.ModelSerializer):
    role_type_display = serializers.CharField(
        source="get_role_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    assignment_count = serializers.SerializerMethodField()
    next_match = serializers.SerializerMethodField()

    class Meta:
        model = UnionMatchOfficial
        fields = [
            "id",
            "union",
            "user",
            "user_email",
            "full_name",
            "email",
            "phone_number",
            "role_type",
            "role_type_display",
            "certification_level",
            "primary_sport",
            "competitions",
            "status",
            "status_display",
            "notes",
            "assignment_count",
            "next_match",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "union",
            "user_email",
            "role_type_display",
            "status_display",
            "assignment_count",
            "next_match",
            "created_at",
            "updated_at",
        ]

    def get_assignment_count(self, obj):
        return obj.assignments.count()

    def get_next_match(self, obj):
        assignment = (
            obj.assignments.select_related(
                "match",
                "match__home_club",
                "match__away_club",
                "match__competition",
            )
            .filter(match__match_date__gte=timezone.now())
            .order_by("match__match_date")
            .first()
        )

        if assignment is None:
            return None

        match = assignment.match
        return {
            "id": match.id,
            "label": f"{match.home_club.name} vs {match.away_club.name}",
            "competition": match.competition.name,
            "match_date": match.match_date,
            "venue": match.venue,
            "role_type": assignment.role_type,
            "role_type_display": assignment.get_role_type_display(),
            "status": assignment.status,
            "status_display": assignment.get_status_display(),
        }


class FixtureOfficialAssignmentManagementSerializer(serializers.ModelSerializer):
    match_label = serializers.SerializerMethodField()
    competition_name = serializers.CharField(
        source="match.competition.name", read_only=True
    )
    match_date = serializers.DateTimeField(source="match.match_date", read_only=True)
    venue = serializers.CharField(source="match.venue", read_only=True)
    official_name = serializers.CharField(source="official.full_name", read_only=True)
    official_email = serializers.EmailField(source="official.email", read_only=True)
    role_type_display = serializers.CharField(
        source="get_role_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = FixtureOfficialAssignment
        fields = [
            "id",
            "match",
            "match_label",
            "competition_name",
            "match_date",
            "venue",
            "official",
            "official_name",
            "official_email",
            "role_type",
            "role_type_display",
            "status",
            "status_display",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "match_label",
            "competition_name",
            "match_date",
            "venue",
            "official_name",
            "official_email",
            "role_type_display",
            "status_display",
            "created_at",
            "updated_at",
        ]

    def get_match_label(self, obj):
        return f"{obj.match.home_club.name} vs {obj.match.away_club.name}"
