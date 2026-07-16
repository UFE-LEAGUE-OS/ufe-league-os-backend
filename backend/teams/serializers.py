from rest_framework import serializers


from .models import (
    PlayerRegistration,
    PlayerTransfer,
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


class PlayerRegistrationSerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source="club.name", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = PlayerRegistration
        fields = [
            "id",
            "user",
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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        if attrs.get("expiry_date") and attrs.get("registered_date"):
            if attrs["expiry_date"] < attrs["registered_date"]:
                raise serializers.ValidationError(
                    "Expiry date must be after registered date."
                )
        return attrs


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


class PlayerTransferSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source="player.full_name", read_only=True)
    player_registration_number = serializers.CharField(
        source="player.registration_number", read_only=True
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
        read_only_fields = [
            "id",
            "transfer_number",
            "created_at",
            "updated_at",
            "requested_by",
        ]


class PlayerTransferSummarySerializer(serializers.ModelSerializer):
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
