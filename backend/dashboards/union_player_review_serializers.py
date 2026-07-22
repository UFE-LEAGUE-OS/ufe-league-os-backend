"""Explicit Union review serializers for Club player-registration submissions."""

from rest_framework import serializers

from accounts.models import User
from teams.models import PlayerRegistration

from .models import UnionPlayerRegistration


def _user_name(user):
    if user is None:
        return None
    return user.full_name or user.email


class UnionPlayerRegistrationSubmissionListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    union_player_number = serializers.CharField(
        source="union_player.union_player_number",
        read_only=True,
        allow_null=True,
    )
    club_name = serializers.CharField(source="club.name", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    assigned_reviewer_name = serializers.SerializerMethodField()
    warning_count = serializers.SerializerMethodField()
    blocking_error_count = serializers.SerializerMethodField()

    class Meta:
        model = PlayerRegistration
        fields = [
            "id",
            "registration_number",
            "full_name",
            "union_player_number",
            "club",
            "club_name",
            "team",
            "team_name",
            "season_record",
            "registration_type",
            "submission_status",
            "submission_revision",
            "submitted_at",
            "assigned_reviewer",
            "assigned_reviewer_name",
            "reviewed_at",
            "warning_count",
            "blocking_error_count",
        ]
        read_only_fields = fields

    def get_assigned_reviewer_name(self, obj):
        return _user_name(obj.assigned_reviewer)

    def get_warning_count(self, obj):
        return len((obj.automatic_validation or {}).get("review_warnings", []))

    def get_blocking_error_count(self, obj):
        return len((obj.automatic_validation or {}).get("blocking_errors", []))


class UnionAuthoritativePlayerRegistrationSerializer(serializers.ModelSerializer):
    union_player_number = serializers.CharField(
        source="player.union_player_number", read_only=True
    )
    player_name = serializers.CharField(source="player.full_name", read_only=True)
    club_name = serializers.CharField(source="club.name", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = UnionPlayerRegistration
        fields = [
            "id",
            "workspace",
            "player",
            "union_player_number",
            "player_name",
            "club",
            "club_name",
            "team",
            "team_name",
            "season",
            "source_registration",
            "status",
            "registration_type",
            "effective_from",
            "effective_to",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "decision_reason",
            "predecessor",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_approved_by_name(self, obj):
        return _user_name(obj.approved_by)


class UnionPlayerRegistrationSubmissionDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    club_name = serializers.CharField(source="club.name", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    union_player_number = serializers.CharField(
        source="union_player.union_player_number",
        read_only=True,
        allow_null=True,
    )
    assigned_reviewer_name = serializers.SerializerMethodField()
    submitted_by_name = serializers.SerializerMethodField()
    requested_competition_editions = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True
    )
    permanent_player_summary = serializers.SerializerMethodField()
    authoritative_registration_summary = serializers.SerializerMethodField()

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
            "permanent_player_summary",
            "requested_competition_editions",
            "supporting_documents",
            "club_notes",
            "submission_status",
            "submission_revision",
            "submitted_by",
            "submitted_by_name",
            "submitted_at",
            "last_resubmitted_at",
            "assigned_reviewer",
            "assigned_reviewer_name",
            "change_request_reason",
            "union_decision_reason",
            "reviewed_at",
            "automatic_validation",
            "withdrawal_reason",
            "authoritative_registration_summary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_assigned_reviewer_name(self, obj):
        return _user_name(obj.assigned_reviewer)

    def get_submitted_by_name(self, obj):
        return _user_name(obj.submitted_by)

    def get_permanent_player_summary(self, obj):
        player = obj.union_player
        if player is None:
            return None
        return {
            "id": player.id,
            "union_player_number": player.union_player_number,
            "full_name": player.full_name,
            "nationality": player.nationality,
            "status": player.status,
        }

    def get_authoritative_registration_summary(self, obj):
        registration = (
            UnionPlayerRegistration.objects.filter(source_registration=obj)
            .select_related(
                "workspace",
                "player",
                "club",
                "team",
                "season",
                "approved_by",
            )
            .first()
        )
        if (
            registration is None
            and obj.submission_status == PlayerRegistration.SubmissionStatus.APPROVED
            and obj.registration_type
            == PlayerRegistration.RegistrationType.COMPETITION_REGISTRATION
        ):
            registration = (
                UnionPlayerRegistration.objects.filter(
                    workspace=obj.union_workspace,
                    player=obj.union_player,
                    club=obj.club,
                    status=UnionPlayerRegistration.Status.ACTIVE,
                )
                .select_related(
                    "workspace",
                    "player",
                    "club",
                    "team",
                    "season",
                    "approved_by",
                )
                .first()
            )
        if registration is None:
            return None
        return UnionAuthoritativePlayerRegistrationSerializer(registration).data


class UnionPlayerRegistrationReviewerAssignSerializer(serializers.Serializer):
    reviewer = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
    )


class UnionPlayerRegistrationDecisionSerializer(serializers.Serializer):
    reason = serializers.CharField(trim_whitespace=True, allow_blank=False)


class UnionPlayerRegistrationReviewResultSerializer(serializers.Serializer):
    submission = UnionPlayerRegistrationSubmissionDetailSerializer(read_only=True)
    authoritative_registration = UnionAuthoritativePlayerRegistrationSerializer(
        read_only=True,
        allow_null=True,
    )
    automatic_validation = serializers.JSONField(read_only=True)
    idempotent_replay = serializers.BooleanField(read_only=True)
    eligibility_review_required = serializers.BooleanField(read_only=True)
