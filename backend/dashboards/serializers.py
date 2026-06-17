from rest_framework import serializers

from accounts.models import Club
from .models import Union, League, Competition, Match, Standing


class ClubListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for public club listing."""

    class Meta:
        model = Club
        fields = ["id", "name", "slug", "created_at"]


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

    class Meta:
        model = Match
        fields = [
            "id",
            "competition",
            "competition_name",
            "home_club",
            "home_club_name",
            "home_club_slug",
            "away_club",
            "away_club_name",
            "away_club_slug",
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
