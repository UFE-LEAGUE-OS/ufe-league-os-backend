"""Explicit serializers for Union player-transfer review APIs."""

from rest_framework import serializers

from .models import (
    UnionPlayerCompetitionEligibility,
    UnionPlayerRegistration,
    UnionPlayerTransfer,
)


class RejectUnexpectedUnionTransferFieldsMixin:
    """Reject fields outside an action's explicit input contract."""

    def to_internal_value(self, data):
        unexpected_fields = set(data) - set(self.fields)
        if unexpected_fields:
            raise serializers.ValidationError(
                {
                    field: "This field is not permitted."
                    for field in sorted(unexpected_fields)
                }
            )
        return super().to_internal_value(data)


def _user_name(user):
    if user is None:
        return None
    return user.full_name or user.email


class UnionPlayerTransferListSerializer(serializers.ModelSerializer):
    union_player_number = serializers.CharField(
        source="player.union_player_number",
        read_only=True,
    )
    player_name = serializers.CharField(source="player.full_name", read_only=True)
    source_club = serializers.IntegerField(
        source="source_registration.club_id",
        read_only=True,
    )
    source_club_name = serializers.CharField(
        source="source_registration.club.name",
        read_only=True,
    )
    destination_club_name = serializers.CharField(
        source="destination_club.name",
        read_only=True,
    )
    destination_team_name = serializers.CharField(
        source="destination_team.name",
        read_only=True,
        allow_null=True,
    )
    initiated_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = UnionPlayerTransfer
        fields = [
            "id",
            "status",
            "transfer_type",
            "player",
            "union_player_number",
            "player_name",
            "source_registration",
            "source_club",
            "source_club_name",
            "destination_club",
            "destination_club_name",
            "destination_team",
            "destination_team_name",
            "effective_on",
            "loan_end_on",
            "source_club_response_status",
            "player_consent_status",
            "initiated_by",
            "initiated_by_name",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "submission_revision",
            "submitted_at",
            "last_resubmitted_at",
            "activated_at",
            "returned_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_initiated_by_name(self, obj):
        return _user_name(obj.initiated_by)

    def get_reviewed_by_name(self, obj):
        return _user_name(obj.reviewed_by)


class UnionPlayerTransferDetailSerializer(serializers.ModelSerializer):
    workspace_name = serializers.CharField(source="workspace.name", read_only=True)
    union_player_number = serializers.CharField(
        source="player.union_player_number",
        read_only=True,
    )
    player_name = serializers.CharField(source="player.full_name", read_only=True)
    player_status = serializers.CharField(source="player.status", read_only=True)
    source_registration_status = serializers.CharField(
        source="source_registration.status",
        read_only=True,
    )
    source_registration_effective_from = serializers.DateField(
        source="source_registration.effective_from",
        read_only=True,
    )
    source_registration_effective_to = serializers.DateField(
        source="source_registration.effective_to",
        read_only=True,
        allow_null=True,
    )
    source_club = serializers.IntegerField(
        source="source_registration.club_id",
        read_only=True,
    )
    source_club_name = serializers.CharField(
        source="source_registration.club.name",
        read_only=True,
    )
    source_team = serializers.IntegerField(
        source="source_registration.team_id",
        read_only=True,
        allow_null=True,
    )
    source_team_name = serializers.CharField(
        source="source_registration.team.name",
        read_only=True,
        allow_null=True,
    )
    destination_club_name = serializers.CharField(
        source="destination_club.name",
        read_only=True,
    )
    destination_team_name = serializers.CharField(
        source="destination_team.name",
        read_only=True,
        allow_null=True,
    )
    source_club_responded_by_name = serializers.SerializerMethodField()
    player_consent_recorded_by_name = serializers.SerializerMethodField()
    initiated_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    cancelled_by_name = serializers.SerializerMethodField()

    class Meta:
        model = UnionPlayerTransfer
        fields = [
            "id",
            "workspace",
            "workspace_name",
            "status",
            "transfer_type",
            "player",
            "union_player_number",
            "player_name",
            "player_status",
            "source_registration",
            "source_registration_status",
            "source_registration_effective_from",
            "source_registration_effective_to",
            "source_club",
            "source_club_name",
            "source_team",
            "source_team_name",
            "destination_club",
            "destination_club_name",
            "destination_team",
            "destination_team_name",
            "destination_registration",
            "return_registration",
            "effective_on",
            "loan_end_on",
            "documents",
            "fee_status",
            "source_club_response_status",
            "source_club_response",
            "source_club_responded_by",
            "source_club_responded_by_name",
            "source_club_response_at",
            "player_consent_status",
            "player_consent_method",
            "player_consent_recorded_by",
            "player_consent_recorded_by_name",
            "player_consented_at",
            "initiated_by",
            "initiated_by_name",
            "submission_revision",
            "automatic_validation",
            "submitted_at",
            "last_resubmitted_at",
            "change_request_reason",
            "decision_reason",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "cancellation_reason",
            "cancelled_by",
            "cancelled_by_name",
            "cancelled_at",
            "activated_at",
            "returned_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_source_club_responded_by_name(self, obj):
        return _user_name(obj.source_club_responded_by)

    def get_player_consent_recorded_by_name(self, obj):
        return _user_name(obj.player_consent_recorded_by)

    def get_initiated_by_name(self, obj):
        return _user_name(obj.initiated_by)

    def get_reviewed_by_name(self, obj):
        return _user_name(obj.reviewed_by)

    def get_cancelled_by_name(self, obj):
        return _user_name(obj.cancelled_by)


class UnionPlayerTransferDecisionSerializer(
    RejectUnexpectedUnionTransferFieldsMixin,
    serializers.Serializer,
):
    workspace = serializers.IntegerField()
    reason = serializers.CharField(trim_whitespace=True, allow_blank=False)


class UnionPlayerTransferOfflineConsentSerializer(
    RejectUnexpectedUnionTransferFieldsMixin,
    serializers.Serializer,
):
    workspace = serializers.IntegerField()
    consent_method = serializers.CharField(trim_whitespace=True, allow_blank=False)
    evidence_reference = serializers.CharField(
        trim_whitespace=True,
        allow_blank=False,
        write_only=True,
    )


class UnionPlayerTransferOfflineDeclineSerializer(
    RejectUnexpectedUnionTransferFieldsMixin,
    serializers.Serializer,
):
    workspace = serializers.IntegerField()
    reason = serializers.CharField(trim_whitespace=True, allow_blank=False)
    evidence_reference = serializers.CharField(
        trim_whitespace=True,
        allow_blank=False,
        write_only=True,
    )


class UnionPlayerTransferRegistrationSummarySerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source="club.name", read_only=True)
    team_name = serializers.CharField(
        source="team.name",
        read_only=True,
        allow_null=True,
    )
    season_name = serializers.CharField(
        source="season.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = UnionPlayerRegistration
        fields = [
            "id",
            "status",
            "registration_type",
            "player",
            "club",
            "club_name",
            "team",
            "team_name",
            "season",
            "season_name",
            "effective_from",
            "effective_to",
            "predecessor",
            "approved_by",
            "approved_at",
        ]
        read_only_fields = fields


class UnionPlayerTransferEligibilitySummarySerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source="club.name", read_only=True)
    team_name = serializers.CharField(
        source="team.name",
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
    season_name = serializers.CharField(source="season.name", read_only=True)

    class Meta:
        model = UnionPlayerCompetitionEligibility
        fields = [
            "id",
            "status",
            "registration",
            "club",
            "club_name",
            "team",
            "team_name",
            "competition_identity",
            "competition_name",
            "competition_edition",
            "edition_name",
            "season",
            "season_name",
            "eligible_from",
            "eligible_until",
            "source_transfer",
            "source_loan_return",
        ]
        read_only_fields = fields


class UnionPlayerTransferDecisionResultSerializer(serializers.Serializer):
    transfer = UnionPlayerTransferDetailSerializer(read_only=True)
    automatic_validation = serializers.JSONField(read_only=True, allow_null=True)
    source_registration = UnionPlayerTransferRegistrationSummarySerializer(
        read_only=True
    )
    destination_registration = UnionPlayerTransferRegistrationSummarySerializer(
        read_only=True,
        allow_null=True,
    )
    return_registration = UnionPlayerTransferRegistrationSummarySerializer(
        read_only=True,
        allow_null=True,
    )
    destination_eligibilities = UnionPlayerTransferEligibilitySummarySerializer(
        many=True,
        read_only=True,
    )
    return_eligibilities = UnionPlayerTransferEligibilitySummarySerializer(
        many=True,
        read_only=True,
    )
    activation_scheduled = serializers.BooleanField(read_only=True)
    idempotent_replay = serializers.BooleanField(read_only=True)

    def to_representation(self, instance):
        result = dict(instance or {})
        transfer = result.get("transfer")
        result.setdefault(
            "automatic_validation",
            getattr(transfer, "automatic_validation", None),
        )
        result.setdefault(
            "source_registration",
            getattr(transfer, "source_registration", None),
        )
        result.setdefault("destination_registration", None)
        result.setdefault("return_registration", None)
        result.setdefault("destination_eligibilities", [])
        result.setdefault("return_eligibilities", [])
        result.setdefault("activation_scheduled", False)
        result.setdefault("idempotent_replay", False)
        return super().to_representation(result)
