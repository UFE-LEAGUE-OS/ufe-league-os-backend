"""Explicit serializers for Union competition-eligibility APIs."""

from rest_framework import serializers

from .models import UnionPlayerCompetitionEligibility


def _user_name(user):
    if user is None:
        return None
    return user.full_name or user.email


class UnionPlayerEligibilityListSerializer(serializers.ModelSerializer):
    union_player_number = serializers.CharField(
        source="player.union_player_number",
        read_only=True,
    )
    player_name = serializers.CharField(source="player.full_name", read_only=True)
    club_name = serializers.CharField(source="club.name", read_only=True)
    team_name = serializers.CharField(
        source="team.name",
        read_only=True,
        allow_null=True,
    )
    registration_type = serializers.CharField(
        source="registration.registration_type",
        read_only=True,
    )
    competition_name = serializers.CharField(
        source="competition_identity.name",
        read_only=True,
    )
    edition_name = serializers.CharField(
        source="competition_edition.competition.name",
        read_only=True,
    )
    season_name = serializers.CharField(source="season.name", read_only=True)
    source_submission_status = serializers.CharField(
        source="source_submission.submission_status",
        read_only=True,
        allow_null=True,
    )
    review_warning_count = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = UnionPlayerCompetitionEligibility
        fields = [
            "id",
            "status",
            "player",
            "union_player_number",
            "player_name",
            "club",
            "club_name",
            "team",
            "team_name",
            "registration",
            "registration_type",
            "competition_identity",
            "competition_name",
            "competition_edition",
            "edition_name",
            "season",
            "season_name",
            "source_submission",
            "source_submission_status",
            "eligible_from",
            "eligible_until",
            "review_warning_count",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_review_warning_count(self, obj):
        return len(obj.warnings or [])

    def get_reviewed_by_name(self, obj):
        return _user_name(obj.reviewed_by)


class UnionPlayerEligibilityDetailSerializer(serializers.ModelSerializer):
    union_player_number = serializers.CharField(
        source="player.union_player_number",
        read_only=True,
    )
    player_name = serializers.CharField(source="player.full_name", read_only=True)
    player_status = serializers.CharField(source="player.status", read_only=True)
    club_name = serializers.CharField(source="club.name", read_only=True)
    team_name = serializers.CharField(
        source="team.name",
        read_only=True,
        allow_null=True,
    )
    registration_status = serializers.CharField(
        source="registration.status",
        read_only=True,
    )
    registration_type = serializers.CharField(
        source="registration.registration_type",
        read_only=True,
    )
    registration_effective_from = serializers.DateField(
        source="registration.effective_from",
        read_only=True,
    )
    registration_effective_to = serializers.DateField(
        source="registration.effective_to",
        read_only=True,
        allow_null=True,
    )
    source_submission_status = serializers.CharField(
        source="source_submission.submission_status",
        read_only=True,
        allow_null=True,
    )
    source_submission_revision = serializers.IntegerField(
        source="source_submission.submission_revision",
        read_only=True,
        allow_null=True,
    )
    source_submission_submitted_at = serializers.DateTimeField(
        source="source_submission.submitted_at",
        read_only=True,
        allow_null=True,
    )
    competition_name = serializers.CharField(
        source="competition_identity.name",
        read_only=True,
    )
    edition_name = serializers.CharField(
        source="competition_edition.competition.name",
        read_only=True,
    )
    edition_status = serializers.CharField(
        source="competition_edition.status",
        read_only=True,
    )
    season_name = serializers.CharField(source="season.name", read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = UnionPlayerCompetitionEligibility
        fields = [
            "id",
            "workspace",
            "status",
            "player",
            "union_player_number",
            "player_name",
            "player_status",
            "club",
            "club_name",
            "team",
            "team_name",
            "registration",
            "registration_status",
            "registration_type",
            "registration_effective_from",
            "registration_effective_to",
            "source_submission",
            "source_submission_status",
            "source_submission_revision",
            "source_submission_submitted_at",
            "competition_identity",
            "competition_name",
            "competition_edition",
            "edition_name",
            "edition_status",
            "season",
            "season_name",
            "eligible_from",
            "eligible_until",
            "warnings",
            "restriction_reason",
            "decision_reason",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_reviewed_by_name(self, obj):
        return _user_name(obj.reviewed_by)


class UnionPlayerEligibilityDecisionSerializer(serializers.Serializer):
    workspace = serializers.CharField()
    reason = serializers.CharField(trim_whitespace=True, allow_blank=False)


class UnionPlayerEligibilityApproveSerializer(UnionPlayerEligibilityDecisionSerializer):
    eligible_from = serializers.DateField(required=False, allow_null=True)
    eligible_until = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        eligible_from = attrs.get("eligible_from")
        eligible_until = attrs.get("eligible_until")
        if (
            eligible_from is not None
            and eligible_until is not None
            and eligible_until < eligible_from
        ):
            raise serializers.ValidationError(
                {
                    "eligible_until": (
                        "Eligibility end date cannot precede its start date."
                    )
                }
            )
        return attrs


class UnionPlayerEligibilityActionResultSerializer(serializers.Serializer):
    eligibility = UnionPlayerEligibilityDetailSerializer(read_only=True)
    automatic_validation = serializers.JSONField(read_only=True, allow_null=True)
    idempotent_replay = serializers.BooleanField(read_only=True)
