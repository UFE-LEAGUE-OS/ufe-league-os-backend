"""Explicit API contracts for maintained and legacy player transfers."""

from rest_framework import serializers

from accounts.models import Club
from dashboards.models import (
    UnionPlayerRegistration,
    UnionPlayerTransfer,
    UnionWorkspace,
)

from .models import PlayerTransfer, Team


class RejectUnexpectedTransferFieldsMixin:
    """Reject fields outside an endpoint's explicit transfer contract."""

    unexpected_field_message = "This field is not permitted."

    def to_internal_value(self, data):
        unexpected_fields = set(data) - set(self.fields)
        if unexpected_fields:
            raise serializers.ValidationError(
                {
                    field: self.unexpected_field_message
                    for field in sorted(unexpected_fields)
                }
            )
        return super().to_internal_value(data)


class ClubPlayerTransferDraftCreateSerializer(
    RejectUnexpectedTransferFieldsMixin,
    serializers.ModelSerializer,
):
    unexpected_field_message = (
        "This field is not permitted. Maintained transfer creation requires "
        "workspace, source_registration, destination_club, effective_on and "
        "transfer_type."
    )
    workspace = serializers.PrimaryKeyRelatedField(
        queryset=UnionWorkspace.objects.all()
    )
    source_registration = serializers.PrimaryKeyRelatedField(
        queryset=UnionPlayerRegistration.objects.all()
    )
    destination_club = serializers.PrimaryKeyRelatedField(queryset=Club.objects.all())
    destination_team = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.all(),
        required=False,
        allow_null=True,
    )
    transfer_type = serializers.ChoiceField(
        choices=("PERMANENT", "FREE_TRANSFER", "LOAN")
    )
    documents = serializers.ListField(
        child=serializers.JSONField(),
        required=False,
        default=list,
    )
    fee_status = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    class Meta:
        model = UnionPlayerTransfer
        fields = [
            "workspace",
            "source_registration",
            "destination_club",
            "destination_team",
            "effective_on",
            "transfer_type",
            "loan_end_on",
            "documents",
            "fee_status",
        ]
        extra_kwargs = {
            "loan_end_on": {"required": False, "allow_null": True},
        }


class ClubPlayerTransferDraftUpdateSerializer(
    RejectUnexpectedTransferFieldsMixin,
    serializers.ModelSerializer,
):
    destination_team = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.all(),
        required=False,
        allow_null=True,
    )
    transfer_type = serializers.ChoiceField(
        choices=("PERMANENT", "FREE_TRANSFER", "LOAN"),
        required=False,
    )
    documents = serializers.ListField(
        child=serializers.JSONField(),
        required=False,
    )
    fee_status = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = UnionPlayerTransfer
        fields = [
            "destination_team",
            "effective_on",
            "transfer_type",
            "loan_end_on",
            "documents",
            "fee_status",
        ]
        extra_kwargs = {
            "effective_on": {"required": False},
            "loan_end_on": {"required": False, "allow_null": True},
        }


class ClubPlayerTransferSubmissionListSerializer(serializers.ModelSerializer):
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
            "submission_revision",
            "submitted_at",
            "last_resubmitted_at",
            "reviewed_at",
            "activated_at",
            "returned_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ClubPlayerTransferSubmissionDetailSerializer(serializers.ModelSerializer):
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
    reviewed_by_name = serializers.SerializerMethodField()
    cancelled_by_name = serializers.SerializerMethodField()

    @staticmethod
    def _user_name(user):
        if user is None:
            return None
        return user.get_full_name().strip() or user.email

    def get_source_club_responded_by_name(self, obj):
        return self._user_name(obj.source_club_responded_by)

    def get_player_consent_recorded_by_name(self, obj):
        return self._user_name(obj.player_consent_recorded_by)

    def get_reviewed_by_name(self, obj):
        return self._user_name(obj.reviewed_by)

    def get_cancelled_by_name(self, obj):
        return self._user_name(obj.cancelled_by)

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


class ClubPlayerTransferCancelSerializer(
    RejectUnexpectedTransferFieldsMixin,
    serializers.Serializer,
):
    reason = serializers.CharField(trim_whitespace=True, allow_blank=False)


class ClubPlayerTransferSourceResponseSerializer(
    RejectUnexpectedTransferFieldsMixin,
    serializers.Serializer,
):
    response_status = serializers.ChoiceField(choices=("ACKNOWLEDGED", "OBJECTED"))
    response = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        default="",
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["response_status"] == "OBJECTED" and not attrs["response"].strip():
            raise serializers.ValidationError(
                {"response": "A written response is required for an objection."}
            )
        return attrs


class PlayerTransferDirectConsentSerializer(
    RejectUnexpectedTransferFieldsMixin,
    serializers.Serializer,
):
    consent_method = serializers.CharField(
        trim_whitespace=True,
        allow_blank=False,
    )


class PlayerTransferDirectDeclineSerializer(
    RejectUnexpectedTransferFieldsMixin,
    serializers.Serializer,
):
    reason = serializers.CharField(trim_whitespace=True, allow_blank=False)


class LegacyPlayerTransferReadSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source="player.full_name", read_only=True)
    player_registration_number = serializers.CharField(
        source="player.registration_number",
        read_only=True,
    )
    from_club_name = serializers.CharField(source="from_club.name", read_only=True)
    to_club_name = serializers.CharField(source="to_club.name", read_only=True)

    class Meta:
        model = PlayerTransfer
        fields = [
            "id",
            "transfer_number",
            "player",
            "player_name",
            "player_registration_number",
            "from_club",
            "from_club_name",
            "to_club",
            "to_club_name",
            "transfer_type",
            "transfer_fee",
            "currency",
            "transfer_date",
            "contract_until",
            "status",
            "requested_by",
            "approved_by",
            "approved_at",
            "rejection_reason",
            "documents",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class LegacyPlayerTransferSummarySerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source="player.full_name", read_only=True)
    from_club_name = serializers.CharField(source="from_club.name", read_only=True)
    to_club_name = serializers.CharField(source="to_club.name", read_only=True)

    class Meta:
        model = PlayerTransfer
        fields = [
            "id",
            "transfer_number",
            "player_name",
            "from_club_name",
            "to_club_name",
            "transfer_type",
            "transfer_fee",
            "currency",
            "transfer_date",
            "status",
        ]
        read_only_fields = fields


class LegacyPlayerTransferCompatibilityResultSerializer(serializers.Serializer):
    workflow = serializers.CharField(read_only=True)
    deprecated_direct_creation = serializers.BooleanField(read_only=True)
    submission = ClubPlayerTransferSubmissionDetailSerializer(read_only=True)
