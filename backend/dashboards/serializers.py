from rest_framework import serializers

from accounts.models import Club
from .models import (
    Union,
    League,
    Competition,
    Match,
    Standing,
    UnionWorkspace,
    UnionWorkspaceMembership,
)


def build_file_url(request, file_field):
    if not file_field:
        return ""

    try:
        url = file_field.url
    except ValueError:
        return ""

    return request.build_absolute_uri(url) if request else url


class ClubListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for public club listing."""

    logo_url = serializers.SerializerMethodField()
    banner_url = serializers.SerializerMethodField()
    sport_display = serializers.CharField(source="get_sport_display", read_only=True)

    class Meta:
        model = Club
        fields = [
            "id",
            "name",
            "slug",
            "short_name",
            "sport",
            "sport_display",
            "logo",
            "logo_url",
            "banner",
            "banner_url",
            "primary_color",
            "secondary_color",
            "created_at",
        ]

    def get_logo_url(self, obj):
        return build_file_url(self.context.get("request"), obj.logo)

    def get_banner_url(self, obj):
        return build_file_url(self.context.get("request"), obj.banner)


class UnionSerializer(serializers.ModelSerializer):
    """Serializer for public union listing."""

    class Meta:
        model = Union
        fields = [
            "id",
            "name",
            "slug",
            "logo",
            "description",
            "website",
            "founded_year",
            "country",
            "created_at",
        ]


class LeagueSerializer(serializers.ModelSerializer):
    """Serializer for public league listing."""

    union_name = serializers.CharField(source="union.name", read_only=True)

    class Meta:
        model = League
        fields = [
            "id",
            "name",
            "slug",
            "logo",
            "description",
            "union",
            "union_name",
            "founded_year",
            "is_active",
            "created_at",
        ]


class CompetitionSerializer(serializers.ModelSerializer):
    """Serializer for public competition listing."""

    league_name = serializers.CharField(source="league.name", read_only=True)

    class Meta:
        model = Competition
        fields = [
            "id",
            "name",
            "slug",
            "season",
            "league",
            "league_name",
            "is_active",
            "start_date",
            "end_date",
            "created_at",
        ]


class MatchListSerializer(serializers.ModelSerializer):
    """Serializer for public fixture/result listing."""

    competition_name = serializers.CharField(source="competition.name", read_only=True)
    home_club_name = serializers.CharField(source="home_club.name", read_only=True)
    away_club_name = serializers.CharField(source="away_club.name", read_only=True)
    home_club_slug = serializers.SlugField(source="home_club.slug", read_only=True)
    away_club_slug = serializers.SlugField(source="away_club.slug", read_only=True)
    home_club_logo_url = serializers.SerializerMethodField()
    away_club_logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            "id",
            "competition",
            "competition_name",
            "home_club",
            "home_club_name",
            "home_club_slug",
            "home_club_logo_url",
            "away_club",
            "away_club_name",
            "away_club_slug",
            "away_club_logo_url",
            "status",
            "match_date",
            "venue",
            "round",
            "home_score",
            "away_score",
            "home_halftime_score",
            "away_halftime_score",
            "has_extra_time",
            "has_penalties",
            "home_penalty_score",
            "away_penalty_score",
            "is_featured",
            "created_at",
        ]

    def get_home_club_logo_url(self, obj):
        return build_file_url(self.context.get("request"), obj.home_club.logo)

    def get_away_club_logo_url(self, obj):
        return build_file_url(self.context.get("request"), obj.away_club.logo)


class MatchDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for a single match, including computed properties."""

    competition_name = serializers.CharField(source="competition.name", read_only=True)
    competition_slug = serializers.SlugField(source="competition.slug", read_only=True)
    home_club_name = serializers.CharField(source="home_club.name", read_only=True)
    home_club_slug = serializers.SlugField(source="home_club.slug", read_only=True)
    home_club_logo_url = serializers.SerializerMethodField()
    away_club_name = serializers.CharField(source="away_club.name", read_only=True)
    away_club_slug = serializers.SlugField(source="away_club.slug", read_only=True)
    away_club_logo_url = serializers.SerializerMethodField()
    is_fixture = serializers.BooleanField(read_only=True)
    has_result = serializers.BooleanField(read_only=True)

    class Meta:
        model = Match
        fields = [
            "id",
            "competition",
            "competition_name",
            "competition_slug",
            "home_club",
            "home_club_name",
            "home_club_slug",
            "home_club_logo_url",
            "away_club",
            "away_club_name",
            "away_club_slug",
            "away_club_logo_url",
            "status",
            "match_date",
            "venue",
            "round",
            "home_score",
            "away_score",
            "home_halftime_score",
            "away_halftime_score",
            "has_extra_time",
            "has_penalties",
            "home_penalty_score",
            "away_penalty_score",
            "is_featured",
            "is_fixture",
            "has_result",
            "created_at",
            "updated_at",
        ]

    def get_home_club_logo_url(self, obj):
        return build_file_url(self.context.get("request"), obj.home_club.logo)

    def get_away_club_logo_url(self, obj):
        return build_file_url(self.context.get("request"), obj.away_club.logo)


class StandingSerializer(serializers.ModelSerializer):
    """Serializer for public standings listing."""

    club_name = serializers.CharField(source="club.name", read_only=True)
    club_slug = serializers.SlugField(source="club.slug", read_only=True)

    class Meta:
        model = Standing
        fields = [
            "id",
            "club",
            "club_name",
            "club_slug",
            "position",
            "played",
            "won",
            "drawn",
            "lost",
            "goals_for",
            "goals_against",
            "goal_difference",
            "points",
            "form",
        ]


class StandingTableSerializer(serializers.Serializer):
    """Serializer for the calculated standings table response."""

    competition_name = serializers.CharField(read_only=True)
    competition_id = serializers.IntegerField(read_only=True)
    entries = serializers.ListField(child=StandingSerializer(), read_only=True)


class UnionWorkspaceSerializer(serializers.ModelSerializer):
    admin_count = serializers.SerializerMethodField()

    class Meta:
        model = UnionWorkspace
        fields = [
            "id",
            "name",
            "slug",
            "acronym",
            "sport",
            "workspace_type",
            "description",
            "primary_color",
            "status",
            "admin_count",
            "created_at",
        ]

    def get_admin_count(self, obj):
        return obj.memberships.filter(is_active=True).count()


class UnionWorkspaceMembershipSerializer(serializers.ModelSerializer):
    workspace = UnionWorkspaceSerializer(read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    effective_permissions = serializers.ListField(read_only=True)

    class Meta:
        model = UnionWorkspaceMembership
        fields = [
            "id",
            "workspace",
            "role",
            "role_display",
            "effective_permissions",
            "is_active",
            "created_at",
        ]


class UnionWorkspaceUserSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_first_name = serializers.CharField(source="user.first_name", read_only=True)
    user_last_name = serializers.CharField(source="user.last_name", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)
    workspace_slug = serializers.CharField(source="workspace.slug", read_only=True)
    workspace_acronym = serializers.CharField(
        source="workspace.acronym", read_only=True
    )
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    effective_permissions = serializers.ListField(read_only=True)

    class Meta:
        model = UnionWorkspaceMembership
        fields = [
            "id",
            "user_id",
            "user_email",
            "user_first_name",
            "user_last_name",
            "user_full_name",
            "workspace_slug",
            "workspace_acronym",
            "role",
            "role_display",
            "effective_permissions",
            "is_active",
            "created_at",
            "updated_at",
        ]
