"""Serializers for the permanent competition and season-edition API."""

from rest_framework import serializers

from .models import CompetitionEdition, CompetitionIdentity


class CompetitionIdentitySerializer(serializers.ModelSerializer):
    union_name = serializers.CharField(source="union.name", read_only=True)
    primary_league_name = serializers.CharField(
        source="primary_league.name", read_only=True
    )
    editions_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CompetitionIdentity
        fields = [
            "id",
            "union",
            "union_name",
            "primary_league",
            "primary_league_name",
            "name",
            "slug",
            "sport",
            "competition_type",
            "description",
            "branding",
            "default_format",
            "default_eligibility_rules",
            "tier",
            "higher_competition",
            "is_active",
            "editions_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "union",
            "union_name",
            "slug",
            "editions_count",
            "created_at",
            "updated_at",
        ]


class CompetitionEditionSerializer(serializers.ModelSerializer):
    identity_name = serializers.CharField(source="identity.name", read_only=True)
    competition_id = serializers.IntegerField(source="competition.id", read_only=True)
    competition_slug = serializers.CharField(source="competition.slug", read_only=True)
    season_name = serializers.CharField(source="season.name", read_only=True)
    published_by_email = serializers.EmailField(
        source="published_by.email", read_only=True
    )

    class Meta:
        model = CompetitionEdition
        fields = [
            "id",
            "identity",
            "identity_name",
            "competition",
            "competition_id",
            "competition_slug",
            "season",
            "season_name",
            "status",
            "registration_opens_at",
            "registration_closes_at",
            "entry_fee",
            "currency",
            "rules",
            "structure",
            "eligibility_rules",
            "copied_from",
            "published_at",
            "published_by",
            "published_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "identity",
            "competition",
            "competition_id",
            "competition_slug",
            "season",
            "season_name",
            "status",
            "copied_from",
            "published_at",
            "published_by",
            "published_by_email",
            "created_at",
            "updated_at",
        ]
