from rest_framework import serializers

from .models import CompetitionFormat, LeagueStandard, Rule, SportVariant


class SportVariantSerializer(serializers.ModelSerializer):
    """Serializer for Sport Variant CRUD operations."""

    class Meta:
        model = SportVariant
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "icon",
            "players_per_team",
            "max_substitutes",
            "match_duration_minutes",
            "has_halftime",
            "halftime_duration_minutes",
            "has_extra_time",
            "extra_time_duration_minutes",
            "has_penalties",
            "max_red_cards_default",
            "points_win",
            "points_draw",
            "points_loss",
            "is_active",
            "is_verified",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_verified", "created_at", "updated_at"]


class SportVariantListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing sport variants."""

    class Meta:
        model = SportVariant
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "players_per_team",
            "match_duration_minutes",
            "is_active",
            "is_verified",
            "created_at",
        ]


class CompetitionFormatSerializer(serializers.ModelSerializer):
    """Serializer for Competition Format CRUD operations."""

    class Meta:
        model = CompetitionFormat
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "stage_type",
            "has_home_and_away",
            "max_teams_default",
            "min_teams_default",
            "groups_count",
            "teams_per_group",
            "teams_qualify_per_group",
            "has_third_place_match",
            "has_replays",
            "has_aggregate",
            "away_goals_rule",
            "tie_breakers",
            "is_active",
            "is_verified",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_verified", "created_at", "updated_at"]


class CompetitionFormatListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing competition formats."""

    class Meta:
        model = CompetitionFormat
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "stage_type",
            "is_active",
            "is_verified",
            "created_at",
        ]


class RuleSerializer(serializers.ModelSerializer):
    """Serializer for Rules & Standards CRUD operations."""

    created_by_name = serializers.CharField(
        source="created_by.email", read_only=True, default=None
    )

    class Meta:
        model = Rule
        fields = [
            "id",
            "title",
            "slug",
            "rule_number",
            "category",
            "priority",
            "description",
            "summary",
            "version",
            "effective_date",
            "supersedes",
            "enforcement_notes",
            "is_active",
            "is_published",
            "published_at",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_published",
            "published_at",
            "created_by",
            "created_at",
            "updated_at",
        ]


class RuleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing rules."""

    category_display = serializers.CharField(
        source="get_category_display", read_only=True
    )
    priority_display = serializers.CharField(
        source="get_priority_display", read_only=True
    )

    class Meta:
        model = Rule
        fields = [
            "id",
            "title",
            "slug",
            "rule_number",
            "category",
            "category_display",
            "priority",
            "priority_display",
            "summary",
            "version",
            "is_active",
            "is_published",
            "published_at",
            "created_at",
        ]


class LeagueStandardSerializer(serializers.ModelSerializer):
    """Serializer for League Standard assignments (publish standards to leagues)."""

    rule_title = serializers.CharField(source="rule.title", read_only=True)
    rule_slug = serializers.SlugField(source="rule.slug", read_only=True)
    rule_category = serializers.CharField(source="rule.category", read_only=True)
    rule_priority = serializers.CharField(source="rule.priority", read_only=True)
    rule_version = serializers.CharField(source="rule.version", read_only=True)
    league_name = serializers.CharField(source="league.name", read_only=True)
    league_slug = serializers.SlugField(source="league.slug", read_only=True)
    assigned_by_name = serializers.CharField(
        source="assigned_by.email", read_only=True, default=None
    )
    accepted_by_name = serializers.CharField(
        source="accepted_by.email", read_only=True, default=None
    )

    class Meta:
        model = LeagueStandard
        fields = [
            "id",
            "rule",
            "rule_title",
            "rule_slug",
            "rule_category",
            "rule_priority",
            "rule_version",
            "league",
            "league_name",
            "league_slug",
            "is_accepted",
            "accepted_at",
            "accepted_by",
            "accepted_by_name",
            "rejection_reason",
            "notes",
            "assigned_by",
            "assigned_by_name",
            "assigned_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "assigned_by",
            "assigned_at",
            "is_accepted",
            "accepted_at",
            "accepted_by",
            "updated_at",
        ]


class PublishStandardsSerializer(serializers.Serializer):
    """
    Serializer for publishing one or more rules to one or more leagues.
    """

    rule_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        help_text="List of Rule IDs to publish",
    )
    league_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        help_text="List of League IDs to publish to",
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_rule_ids(self, value):
        existing = set(
            Rule.objects.filter(id__in=value, is_active=True).values_list(
                "id", flat=True
            )
        )
        missing = set(value) - existing
        if missing:
            raise serializers.ValidationError(
                f"Rules with IDs {sorted(missing)} not found or are inactive."
            )
        return value

    def validate_league_ids(self, value):
        from dashboards.models import League

        existing = set(
            League.objects.filter(id__in=value, is_active=True).values_list(
                "id", flat=True
            )
        )
        missing = set(value) - existing
        if missing:
            raise serializers.ValidationError(
                f"Leagues with IDs {sorted(missing)} not found or are inactive."
            )
        return value
