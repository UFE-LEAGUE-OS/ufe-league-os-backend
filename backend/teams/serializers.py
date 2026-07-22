from rest_framework import serializers

from accounts.models import Club
from dashboards.models import CompetitionEdition

from .models import (
    PlayerRegistration,
    Squad,
    SquadMember,
    SquadSubmission,
    StaffMember,
    Team,
)


class TeamSerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source="club.name", read_only=True)
    club_slug = serializers.CharField(source="club.slug", read_only=True)

    class Meta:
        model = Team
        fields = [
            "id",
            "club",
            "club_name",
            "club_slug",
            "name",
            "short_name",
            "team_type",
            "description",
            "is_active",
            "logo",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TeamSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "name", "short_name", "team_type", "logo"]


class SquadSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source="team.name", read_only=True)
    team_type = serializers.CharField(source="team.team_type", read_only=True)
    club_name = serializers.CharField(source="team.club.name", read_only=True)
    competition_name = serializers.CharField(source="competition.name", read_only=True)
    member_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Squad
        fields = [
            "id",
            "team",
            "team_name",
            "team_type",
            "club_name",
            "competition",
            "competition_name",
            "name",
            "season",
            "status",
            "submitted_at",
            "submitted_by",
            "approved_at",
            "approved_by",
            "rejection_reason",
            "notes",
            "member_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SquadSummarySerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source="team.name", read_only=True)
    competition_name = serializers.CharField(source="competition.name", read_only=True)

    class Meta:
        model = Squad
        fields = [
            "id",
            "team",
            "team_name",
            "competition",
            "competition_name",
            "name",
            "season",
            "status",
        ]


class SquadMemberSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source="player.full_name", read_only=True)
    player_registration_number = serializers.CharField(
        source="player.registration_number", read_only=True
    )
    squad_name = serializers.CharField(source="squad.name", read_only=True)

    class Meta:
        model = SquadMember
        fields = [
            "id",
            "squad",
            "squad_name",
            "player",
            "player_name",
            "player_registration_number",
            "jersey_number",
            "position",
            "is_captain",
            "is_vice_captain",
            "joined_date",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class LegacyPlayerRegistrationReadSerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source="club.name", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = PlayerRegistration
        fields = [
            "id",
            "club",
            "club_name",
            "team",
            "team_name",
            "registration_number",
            "first_name",
            "last_name",
            "full_name",
            "date_of_birth",
            "nationality",
            "position",
            "secondary_positions",
            "player_type",
            "jersey_number",
            "height_cm",
            "weight_kg",
            "preferred_foot",
            "status",
            "registered_date",
            "expiry_date",
            "transfer_window",
            "previous_club",
            "contract_until",
            "is_captain",
            "is_vice_captain",
            "metadata",
            "submission_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RejectUnexpectedSubmissionFieldsMixin:
    """Fail closed when a Club submits fields outside an explicit contract."""

    def validate(self, attrs):
        unexpected_fields = set(self.initial_data) - set(self.fields)
        if unexpected_fields:
            raise serializers.ValidationError(
                {
                    field: "This field is not permitted."
                    for field in sorted(unexpected_fields)
                }
            )

        registered_date = attrs.get(
            "registered_date", getattr(self.instance, "registered_date", None)
        )
        expiry_date = attrs.get(
            "expiry_date", getattr(self.instance, "expiry_date", None)
        )
        if registered_date and expiry_date and expiry_date < registered_date:
            raise serializers.ValidationError(
                {"expiry_date": "Expiry date must be after registered date."}
            )
        return attrs


class LegacyPlayerRegistrationUpdateSerializer(
    RejectUnexpectedSubmissionFieldsMixin, serializers.ModelSerializer
):
    class Meta:
        model = PlayerRegistration
        fields = [
            "team",
            "first_name",
            "last_name",
            "date_of_birth",
            "nationality",
            "position",
            "secondary_positions",
            "player_type",
            "jersey_number",
            "height_cm",
            "weight_kg",
            "preferred_foot",
            "registered_date",
            "expiry_date",
            "transfer_window",
            "previous_club",
            "contract_until",
            "is_captain",
            "is_vice_captain",
            "metadata",
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        team = attrs.get("team")
        if team is not None and team.club_id != self.instance.club_id:
            raise serializers.ValidationError(
                {"team": "Team must belong to the player registration Club."}
            )
        return attrs


class ClubPlayerRegistrationDraftCreateSerializer(
    RejectUnexpectedSubmissionFieldsMixin, serializers.ModelSerializer
):
    identity_reference = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    existing_union_player_id = serializers.IntegerField(write_only=True, required=False)
    union_workspace_id = serializers.IntegerField(write_only=True, required=False)
    requested_competition_editions = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=CompetitionEdition.objects.all(),
        required=False,
    )

    class Meta:
        model = PlayerRegistration
        fields = [
            "club",
            "team",
            "registration_number",
            "first_name",
            "last_name",
            "date_of_birth",
            "nationality",
            "position",
            "secondary_positions",
            "player_type",
            "jersey_number",
            "height_cm",
            "weight_kg",
            "preferred_foot",
            "registered_date",
            "expiry_date",
            "transfer_window",
            "previous_club",
            "contract_until",
            "is_captain",
            "is_vice_captain",
            "registration_type",
            "season_record",
            "requested_competition_editions",
            "supporting_documents",
            "club_notes",
            "identity_reference",
            "existing_union_player_id",
            "union_workspace_id",
        ]


class ClubPlayerRegistrationDraftUpdateSerializer(
    RejectUnexpectedSubmissionFieldsMixin, serializers.ModelSerializer
):
    requested_competition_editions = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=CompetitionEdition.objects.all(),
        required=False,
    )

    class Meta:
        model = PlayerRegistration
        fields = [
            "team",
            "registration_number",
            "first_name",
            "last_name",
            "date_of_birth",
            "nationality",
            "position",
            "secondary_positions",
            "player_type",
            "jersey_number",
            "height_cm",
            "weight_kg",
            "preferred_foot",
            "registered_date",
            "expiry_date",
            "transfer_window",
            "previous_club",
            "contract_until",
            "is_captain",
            "is_vice_captain",
            "registration_type",
            "season_record",
            "requested_competition_editions",
            "supporting_documents",
            "club_notes",
        ]


class ClubPlayerRegistrationSubmissionListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    club_name = serializers.CharField(source="club.name", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)

    class Meta:
        model = PlayerRegistration
        fields = [
            "id",
            "registration_number",
            "full_name",
            "club",
            "club_name",
            "team",
            "team_name",
            "registration_type",
            "season_record",
            "submission_status",
            "submission_revision",
            "submitted_at",
            "last_resubmitted_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ClubPlayerRegistrationSubmissionDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    club_name = serializers.CharField(source="club.name", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    union_player_number = serializers.CharField(
        source="union_player.union_player_number",
        read_only=True,
        allow_null=True,
    )
    requested_competition_editions = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True
    )

    class Meta:
        model = PlayerRegistration
        fields = [
            "id",
            "club",
            "club_name",
            "team",
            "team_name",
            "registration_number",
            "first_name",
            "last_name",
            "full_name",
            "date_of_birth",
            "nationality",
            "position",
            "secondary_positions",
            "player_type",
            "jersey_number",
            "height_cm",
            "weight_kg",
            "preferred_foot",
            "registered_date",
            "expiry_date",
            "transfer_window",
            "previous_club",
            "contract_until",
            "is_captain",
            "is_vice_captain",
            "registration_type",
            "season_record",
            "union_player",
            "union_player_number",
            "requested_competition_editions",
            "supporting_documents",
            "club_notes",
            "submission_status",
            "submission_revision",
            "submitted_at",
            "last_resubmitted_at",
            "withdrawal_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ClubPlayerRegistrationWithdrawSerializer(serializers.Serializer):
    withdrawal_reason = serializers.CharField(trim_whitespace=True, allow_blank=False)


class ClubPlayerRegistrationDecisionSerializer(serializers.ModelSerializer):
    requested_competition_editions = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True
    )

    class Meta:
        model = PlayerRegistration
        fields = [
            "id",
            "submission_status",
            "change_request_reason",
            "union_decision_reason",
            "reviewed_at",
            "submission_revision",
            "automatic_validation",
            "requested_competition_editions",
        ]
        read_only_fields = fields


class ClubPlayerRegistrySearchQuerySerializer(serializers.Serializer):
    club = serializers.PrimaryKeyRelatedField(queryset=Club.objects.all())
    q = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )
    date_of_birth = serializers.DateField(required=False)
    union_workspace_id = serializers.IntegerField(required=False, min_value=1)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50)

    def validate(self, attrs):
        if not attrs.get("q", "").strip() and attrs.get("date_of_birth") is None:
            raise serializers.ValidationError(
                {"q": "Enter a player name, player number, or date of birth."}
            )
        return attrs


class ClubPlayerRegistrySearchSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    union_player_number = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    date_of_birth = serializers.DateField(read_only=True)
    nationality = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    can_be_selected = serializers.BooleanField(read_only=True)
    selection_warning = serializers.CharField(read_only=True, allow_null=True)
    current_club_summary = serializers.DictField(read_only=True, allow_null=True)


class PlayerRegistrationSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    club_name = serializers.CharField(source="club.name", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)

    class Meta:
        model = PlayerRegistration
        fields = [
            "id",
            "registration_number",
            "full_name",
            "club_name",
            "team_name",
            "position",
            "player_type",
            "status",
            "submission_status",
            "jersey_number",
        ]


class StaffMemberSerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source="club.name", read_only=True)
    team_name = serializers.CharField(
        source="team.name", read_only=True, allow_null=True
    )
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = StaffMember
        fields = [
            "id",
            "user",
            "club",
            "club_name",
            "team",
            "team_name",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "custom_role",
            "employment_type",
            "email",
            "phone_number",
            "qualification",
            "experience_years",
            "start_date",
            "end_date",
            "is_active",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class StaffMemberSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    club_name = serializers.CharField(source="club.name", read_only=True)
    team_name = serializers.CharField(
        source="team.name", read_only=True, allow_null=True
    )

    class Meta:
        model = StaffMember
        fields = [
            "id",
            "full_name",
            "club_name",
            "team_name",
            "role",
            "employment_type",
            "is_active",
        ]


class SquadSubmissionSerializer(serializers.ModelSerializer):
    submission_number = serializers.CharField(read_only=True)
    squad_name = serializers.CharField(source="squad.name", read_only=True)
    submitted_by_email = serializers.CharField(
        source="submitted_by.email", read_only=True
    )
    reviewed_by_email = serializers.CharField(
        source="reviewed_by.email", read_only=True, allow_null=True
    )

    class Meta:
        model = SquadSubmission
        fields = [
            "id",
            "submission_number",
            "squad",
            "squad_name",
            "status",
            "submitted_by",
            "submitted_by_email",
            "submitted_at",
            "reviewed_by",
            "reviewed_by_email",
            "reviewed_at",
            "rejection_reason",
            "iteration",
            "previous_submission",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "submission_number",
            "created_at",
            "updated_at",
            "submitted_by",
        ]


class SquadSubmissionSummarySerializer(serializers.ModelSerializer):
    squad_name = serializers.CharField(source="squad.name", read_only=True)

    class Meta:
        model = SquadSubmission
        fields = [
            "id",
            "submission_number",
            "squad",
            "squad_name",
            "status",
            "submitted_at",
            "iteration",
        ]
