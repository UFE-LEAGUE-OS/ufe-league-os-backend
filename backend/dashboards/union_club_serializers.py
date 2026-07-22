from rest_framework import serializers

from accounts.models import Club, ClubAdminScope

from .models import ClubAffiliation, LeagueClubMembership
from .union_league_serializers import GovernanceAccountSerializer


class ClubAffiliationWriteSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=ClubAffiliation.Status.choices,
        default=ClubAffiliation.Status.APPLICATION_SUBMITTED,
    )
    compliance_status = serializers.CharField(max_length=50, default="PENDING")
    compliance_notes = serializers.CharField(required=False, allow_blank=True)


class ClubLeagueMembershipWriteSerializer(serializers.Serializer):
    league = serializers.IntegerField(min_value=1)
    season = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=LeagueClubMembership.Status.choices,
        default=LeagueClubMembership.Status.INVITED,
    )
    notes = serializers.CharField(required=False, allow_blank=True)


class ClubAdministratorWriteSerializer(serializers.Serializer):
    account = GovernanceAccountSerializer()
    role = serializers.ChoiceField(choices=ClubAdminScope.Role.choices)


class ClubCreationSerializer(serializers.ModelSerializer):
    affiliation = ClubAffiliationWriteSerializer()
    league_membership = ClubLeagueMembershipWriteSerializer(
        required=False, allow_null=True
    )
    administrator = ClubAdministratorWriteSerializer()

    class Meta:
        model = Club
        fields = (
            "name",
            "short_name",
            "sport",
            "founded_year",
            "description",
            "contact_email",
            "phone_number",
            "website",
            "address",
            "primary_color",
            "secondary_color",
            "is_active",
            "affiliation",
            "league_membership",
            "administrator",
        )


class ClubUpdateSerializer(serializers.ModelSerializer):
    affiliation_status = serializers.ChoiceField(
        choices=ClubAffiliation.Status.choices, required=False, write_only=True
    )
    compliance_status = serializers.CharField(
        max_length=50, required=False, write_only=True
    )
    compliance_notes = serializers.CharField(
        required=False, allow_blank=True, write_only=True
    )

    class Meta:
        model = Club
        fields = (
            "name",
            "short_name",
            "sport",
            "founded_year",
            "description",
            "contact_email",
            "phone_number",
            "website",
            "address",
            "primary_color",
            "secondary_color",
            "is_active",
            "affiliation_status",
            "compliance_status",
            "compliance_notes",
        )


class ClubAdministratorSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = ClubAdminScope
        fields = (
            "id",
            "user",
            "user_email",
            "user_name",
            "club",
            "role",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.email


class GovernanceClubSerializer(serializers.ModelSerializer):
    sport_display = serializers.CharField(source="get_sport_display", read_only=True)
    logo_url = serializers.SerializerMethodField()
    banner_url = serializers.SerializerMethodField()
    affiliation_status = serializers.CharField(read_only=True)
    compliance_status = serializers.CharField(read_only=True)
    compliance_notes = serializers.CharField(read_only=True)
    administrator = serializers.SerializerMethodField()
    memberships = serializers.SerializerMethodField()
    teams = serializers.IntegerField(source="teams_count", read_only=True)
    players = serializers.IntegerField(source="players_count", read_only=True)

    class Meta:
        model = Club
        fields = (
            "id",
            "name",
            "slug",
            "short_name",
            "sport",
            "sport_display",
            "description",
            "contact_email",
            "phone_number",
            "website",
            "address",
            "founded_year",
            "logo_url",
            "banner_url",
            "primary_color",
            "secondary_color",
            "is_active",
            "affiliation_status",
            "compliance_status",
            "compliance_notes",
            "administrator",
            "memberships",
            "teams",
            "players",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def _url(self, value):
        if not value:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(value.url) if request else value.url

    def get_logo_url(self, obj):
        return self._url(obj.logo)

    def get_banner_url(self, obj):
        return self._url(obj.banner)

    def get_administrator(self, obj):
        scope = next((item for item in obj.club_scopes if item.is_active), None)
        if scope is None:
            return None
        return ClubAdministratorSerializer(scope).data

    def get_memberships(self, obj):
        return [
            {
                "id": item.id,
                "league": item.league_id,
                "league_name": item.league.name,
                "season": item.season_id,
                "season_name": item.season.name if item.season else None,
                "status": item.status,
                "status_display": item.get_status_display(),
                "notes": item.notes,
            }
            for item in obj.workspace_memberships
        ]
