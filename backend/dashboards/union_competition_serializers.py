"""Serializers for the permanent competition and season-edition API."""

from decimal import Decimal

from rest_framework import serializers

from .models import CompetitionEdition, CompetitionIdentity, LeagueAdminScope


class CompetitionFormatSerializer(serializers.Serializer):
    """Maintained, versioned structure for identity and edition configuration."""

    VERSION = 1
    FORMAT_CHOICES = (
        "SINGLE_ROUND_ROBIN",
        "DOUBLE_ROUND_ROBIN",
        "GROUPS_AND_KNOCKOUT",
        "STRAIGHT_KNOCKOUT",
        "LEAGUE_AND_PLAYOFFS",
        "SERIES",
    )
    TIE_BREAK_CHOICES = (
        "POINTS",
        "HEAD_TO_HEAD",
        "SCORE_DIFFERENCE",
        "SCORES_FOR",
        "WINS",
        "PLAYOFF",
    )

    version = serializers.IntegerField(
        default=VERSION, min_value=VERSION, max_value=VERSION
    )
    format = serializers.ChoiceField(choices=FORMAT_CHOICES)
    number_of_legs = serializers.IntegerField(required=False, min_value=1, max_value=4)
    number_of_rounds = serializers.IntegerField(
        required=False, min_value=1, max_value=100
    )
    number_of_groups = serializers.IntegerField(
        required=False, min_value=2, max_value=32
    )
    clubs_per_group = serializers.IntegerField(
        required=False, min_value=2, max_value=64
    )
    advancing_per_group = serializers.IntegerField(
        required=False, min_value=1, max_value=32
    )
    playoff_qualification_positions = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, allow_empty=True
    )
    home_and_away = serializers.BooleanField(default=False)
    match_duration_minutes = serializers.IntegerField(min_value=10, max_value=240)
    points_for_win = serializers.IntegerField(default=3, min_value=0, max_value=20)
    points_for_draw = serializers.IntegerField(default=1, min_value=0, max_value=20)
    points_for_loss = serializers.IntegerField(default=0, min_value=-10, max_value=20)
    tie_break_order = serializers.ListField(
        child=serializers.ChoiceField(choices=TIE_BREAK_CHOICES),
        required=False,
        allow_empty=False,
    )
    gameweek_structure = serializers.ChoiceField(
        choices=("WEEKLY", "FORTNIGHTLY", "TOURNAMENT_DAYS", "CUSTOM"),
        default="WEEKLY",
    )
    minimum_clubs = serializers.IntegerField(min_value=2, max_value=256)
    maximum_clubs = serializers.IntegerField(min_value=2, max_value=256)
    promotion_enabled = serializers.BooleanField(default=False)
    relegation_enabled = serializers.BooleanField(default=False)
    number_promoted = serializers.IntegerField(default=0, min_value=0, max_value=32)
    number_relegated = serializers.IntegerField(default=0, min_value=0, max_value=32)
    promotion_playoff_positions = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, allow_empty=True
    )

    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError(
                    {
                        key: "This format option is not supported."
                        for key in sorted(unknown)
                    }
                )
        return super().to_internal_value(data)

    def validate(self, attrs):
        if attrs["minimum_clubs"] > attrs["maximum_clubs"]:
            raise serializers.ValidationError(
                {"maximum_clubs": "Maximum clubs must be at least the minimum clubs."}
            )
        if attrs.get("number_promoted", 0) and not attrs.get("promotion_enabled"):
            raise serializers.ValidationError(
                {"number_promoted": "Enable promotion before setting promoted clubs."}
            )
        if attrs.get("number_relegated", 0) and not attrs.get("relegation_enabled"):
            raise serializers.ValidationError(
                {
                    "number_relegated": "Enable relegation before setting relegated clubs."
                }
            )
        if attrs["format"] == "GROUPS_AND_KNOCKOUT":
            required = ("number_of_groups", "clubs_per_group", "advancing_per_group")
            missing = [field for field in required if field not in attrs]
            if missing:
                raise serializers.ValidationError(
                    {
                        field: "This field is required for a group format."
                        for field in missing
                    }
                )
            if attrs["advancing_per_group"] >= attrs["clubs_per_group"]:
                raise serializers.ValidationError(
                    {
                        "advancing_per_group": "Fewer clubs must advance than enter each group."
                    }
                )
        return attrs


class CompetitionIdentitySerializer(serializers.ModelSerializer):
    """Read representation that preserves stored format dictionaries verbatim."""

    union_name = serializers.CharField(source="union.name", read_only=True)
    primary_league_name = serializers.CharField(
        source="primary_league.name", read_only=True
    )
    editions_count = serializers.IntegerField(read_only=True)
    default_format = serializers.JSONField(read_only=True)

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


class CompetitionIdentityWriteSerializer(serializers.ModelSerializer):
    """Validated write contract for a permanent competition identity."""

    default_format = CompetitionFormatSerializer()

    class Meta:
        model = CompetitionIdentity
        fields = [
            "primary_league",
            "name",
            "sport",
            "competition_type",
            "description",
            "branding",
            "default_format",
            "default_eligibility_rules",
            "tier",
            "higher_competition",
            "is_active",
        ]


class CompetitionEditionSerializer(serializers.ModelSerializer):
    identity_name = serializers.CharField(source="identity.name", read_only=True)
    competition_id = serializers.IntegerField(source="competition.id", read_only=True)
    competition_slug = serializers.CharField(source="competition.slug", read_only=True)
    season_name = serializers.CharField(source="season.name", read_only=True)
    published_by_email = serializers.EmailField(
        source="published_by.email", read_only=True
    )
    structure = CompetitionFormatSerializer(required=False)
    allowed_transitions = serializers.SerializerMethodField()

    def get_allowed_transitions(self, obj):
        from .union_competitions import COMPETITION_EDITION_TRANSITIONS

        return sorted(COMPETITION_EDITION_TRANSITIONS.get(obj.status, set()))

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
            "allowed_transitions",
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
            "allowed_transitions",
        ]


class CompetitionAdministratorSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.SerializerMethodField()
    effective_permissions = serializers.SerializerMethodField()

    class Meta:
        model = LeagueAdminScope
        fields = (
            "id",
            "user",
            "user_email",
            "user_name",
            "role",
            "is_active",
            "effective_permissions",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.email

    def get_effective_permissions(self, obj):
        permissions = ["competition.view"]
        if obj.role != LeagueAdminScope.Role.VIEWER:
            permissions.extend(("competition.manage", "fixtures.manage"))
        if obj.role == LeagueAdminScope.Role.REGISTRAR:
            permissions.append("registrations.manage")
        return permissions


class CompetitionAdministratorWriteSerializer(serializers.Serializer):
    user = serializers.IntegerField(min_value=1)
    role = serializers.ChoiceField(choices=LeagueAdminScope.Role.choices)


class FirstEditionWriteSerializer(serializers.Serializer):
    season = serializers.IntegerField(min_value=1)
    registration_opens_at = serializers.DateTimeField(required=False, allow_null=True)
    registration_closes_at = serializers.DateTimeField(required=False, allow_null=True)
    entry_fee = serializers.DecimalField(
        required=False,
        allow_null=True,
        min_value=Decimal("0.00"),
        max_digits=12,
        decimal_places=2,
    )
    currency = serializers.RegexField(r"^[A-Z]{3}$", default="UGX")
    rules = serializers.DictField(required=False, default=dict)
    eligibility_rules = serializers.DictField(required=False, default=dict)

    def validate(self, attrs):
        opens = attrs.get("registration_opens_at")
        closes = attrs.get("registration_closes_at")
        if opens and closes and closes < opens:
            raise serializers.ValidationError(
                {"registration_closes_at": "Registration cannot close before it opens."}
            )
        return attrs


class CompetitionCreationSerializer(serializers.Serializer):
    identity = CompetitionIdentityWriteSerializer()
    first_edition = FirstEditionWriteSerializer()
    administrators = CompetitionAdministratorWriteSerializer(many=True, required=False)

    def validate_administrators(self, value):
        user_ids = [item["user"] for item in value]
        if len(user_ids) != len(set(user_ids)):
            raise serializers.ValidationError("Each user may be assigned only once.")
        return value
