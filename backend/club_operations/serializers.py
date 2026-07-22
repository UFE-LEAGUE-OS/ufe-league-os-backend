from rest_framework import serializers


from .models import (
    CampaignAssignment,
    MatchdayOperationTask,
    MatchdayReport,
    SponsorCampaign,
    TicketingOfficerAssignment,
)


class SponsorCampaignSerializer(serializers.ModelSerializer):
    sponsor_name = serializers.CharField(source="sponsor.name", read_only=True)
    club_name = serializers.CharField(source="club.name", read_only=True)
    created_by_email = serializers.CharField(source="created_by.email", read_only=True)

    class Meta:
        model = SponsorCampaign
        fields = [
            "id",
            "club",
            "club_name",
            "sponsor",
            "sponsor_name",
            "sponsor_package",
            "name",
            "description",
            "objective",
            "campaign_type",
            "status",
            "start_date",
            "end_date",
            "budget",
            "expected_reach",
            "branding_requirements",
            "deliverables",
            "notes",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
            "is_deleted",
            "deleted_at",
        ]
        read_only_fields = [
            "id",
            "club",
            "created_at",
            "updated_at",
            "is_deleted",
            "deleted_at",
        ]


class CampaignAssignmentSerializer(serializers.ModelSerializer):
    club = serializers.CharField(source="club.name", read_only=True)
    campaign_name = serializers.CharField(source="campaign.name", read_only=True)
    match_name = serializers.CharField(source="match.__str__", read_only=True)
    sponsor_package_name = serializers.CharField(
        source="sponsor_package.name", read_only=True
    )

    class Meta:
        model = CampaignAssignment
        fields = [
            "id",
            "club",
            "campaign",
            "campaign_name",
            "match",
            "match_name",
            "sponsor_package",
            "sponsor_package_name",
            "activation_notes",
            "branding_locations",
            "booth_requirements",
            "banner_locations",
            "led_board_allocation",
            "vip_allocation",
            "activation_status",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        campaign = attrs.get("campaign") or self.instance.campaign
        match = attrs.get("match") or getattr(self.instance, "match", None)
        if match:
            if campaign.club_id not in [match.home_club_id, match.away_club_id]:
                raise serializers.ValidationError(
                    {"match": "Match does not belong to the campaign's club."}
                )
            if (
                match.match_date < campaign.start_date
                or match.match_date > campaign.end_date
            ):
                raise serializers.ValidationError(
                    {"match": "Match date is outside the campaign date range."}
                )
        return attrs


class MatchdayOperationTaskSerializer(serializers.ModelSerializer):
    club = serializers.CharField(source="club.name", read_only=True)
    club_name = serializers.CharField(source="club.name", read_only=True)
    match_name = serializers.CharField(source="match.__str__", read_only=True)
    assigned_to_email = serializers.CharField(
        source="assigned_to.email", read_only=True
    )
    completed_by_email = serializers.CharField(
        source="completed_by.email", read_only=True
    )

    class Meta:
        model = MatchdayOperationTask
        fields = [
            "id",
            "club",
            "club_name",
            "match",
            "match_name",
            "title",
            "description",
            "category",
            "priority",
            "assigned_to",
            "assigned_to_email",
            "due_date",
            "due_time",
            "status",
            "completion_notes",
            "completed_at",
            "completed_by",
            "completed_by_email",
            "created_by",
            "created_at",
            "updated_at",
            "is_deleted",
            "deleted_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "is_deleted",
            "deleted_at",
            "completed_at",
            "completed_by",
        ]


class TicketingOfficerAssignmentSerializer(serializers.ModelSerializer):
    club = serializers.CharField(source="club.name", read_only=True)
    officer_email = serializers.CharField(source="officer.email", read_only=True)
    officer_name = serializers.CharField(source="officer.get_full_name", read_only=True)
    match_name = serializers.CharField(source="match.__str__", read_only=True)
    assigned_by_email = serializers.CharField(
        source="assigned_by.email", read_only=True
    )

    class Meta:
        model = TicketingOfficerAssignment
        fields = [
            "id",
            "club",
            "match",
            "match_name",
            "officer",
            "officer_email",
            "officer_name",
            "assignment_role",
            "gate_allocation",
            "shift_start",
            "shift_end",
            "check_in_time",
            "check_out_time",
            "status",
            "notes",
            "assigned_by",
            "assigned_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        from accounts.models import Club

        officer = attrs.get("officer") or getattr(self.instance, "officer", None)
        club = attrs.get("club")
        if club is None and not self.instance:
            request = self.context.get("request")
            if request and request.user.is_authenticated:
                club = Club.objects.filter(admin=request.user).first()
        if officer and club:
            if officer.club_id != club.id:
                raise serializers.ValidationError(
                    {"officer": "Officer must belong to the same club."}
                )
        return attrs


class MatchdayReportSerializer(serializers.ModelSerializer):
    club = serializers.CharField(source="club.name", read_only=True)
    match_name = serializers.CharField(source="match.__str__", read_only=True)
    club_name = serializers.CharField(source="club.name", read_only=True)
    submitted_by_email = serializers.CharField(
        source="submitted_by.email", read_only=True
    )
    reviewed_by_email = serializers.CharField(
        source="reviewed_by.email", read_only=True
    )

    class Meta:
        model = MatchdayReport
        fields = [
            "id",
            "match",
            "match_name",
            "club",
            "club_name",
            "submitted_by",
            "submitted_by_email",
            "reviewed_by",
            "reviewed_by_email",
            "status",
            "review_notes",
            "submitted_at",
            "reviewed_at",
            "created_at",
            "updated_at",
            "is_deleted",
            "deleted_at",
            "attendance_tickets_sold",
            "attendance_complimentary_tickets",
            "attendance_estimated",
            "revenue_ticket",
            "revenue_merchandise",
            "revenue_other",
            "sponsor_campaigns_executed",
            "sponsor_visibility",
            "deliverables_completed",
            "incidents",
            "medical_incidents",
            "security_incidents",
            "delays",
            "stadium_issues",
            "equipment_issues",
            "photos_metadata",
            "documents",
            "successes",
            "challenges",
            "recommendations",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "is_deleted",
            "deleted_at",
            "submitted_by",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
        ]
