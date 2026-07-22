from rest_framework import serializers

from .models import Competition, League, LeagueAdminScope


class LeagueSerializer(serializers.ModelSerializer):
    union_name = serializers.CharField(source="union.name", read_only=True)
    sport = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    competitions_count = serializers.IntegerField(read_only=True)
    clubs_count = serializers.IntegerField(read_only=True)
    administrators_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = League
        fields = (
            "id",
            "name",
            "slug",
            "union",
            "union_name",
            "sport",
            "description",
            "founded_year",
            "logo_url",
            "is_active",
            "competitions_count",
            "clubs_count",
            "administrators_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_sport(self, obj):
        return getattr(getattr(obj.union, "workspace", None), "sport", "")

    def get_logo_url(self, obj):
        if not obj.logo:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.logo.url) if request else obj.logo.url


class LeagueWriteSerializer(serializers.ModelSerializer):
    sport = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = League
        fields = ("name", "description", "founded_year", "logo", "is_active", "sport")

    def validate_name(self, value):
        workspace = self.context["workspace"]
        qs = League.objects.filter(
            union=workspace.related_union, name__iexact=value.strip()
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A League with this name already exists in this workspace."
            )
        return value.strip()

    def validate(self, attrs):
        workspace = self.context["workspace"]
        submitted = attrs.pop("sport", None)
        expected = (workspace.sport or "").strip().upper().replace(" ", "_")
        if expected != "MULTI_SPORT" and submitted:
            normalized = submitted.strip().upper().replace(" ", "_")
            if normalized != expected:
                raise serializers.ValidationError(
                    {"sport": "Sport must match the active workspace."}
                )
        return attrs


class GovernanceAccountSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone_number = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)


class LeagueAdministratorWriteSerializer(serializers.Serializer):
    account = GovernanceAccountSerializer()
    competition = serializers.PrimaryKeyRelatedField(
        queryset=Competition.objects.all(), required=False, allow_null=True
    )
    role = serializers.ChoiceField(choices=LeagueAdminScope.Role.choices)


class LeagueAdministratorSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.SerializerMethodField()
    competition_name = serializers.CharField(
        source="competition.name", read_only=True, allow_null=True
    )
    effective_permissions = serializers.SerializerMethodField()

    class Meta:
        model = LeagueAdminScope
        fields = (
            "id",
            "user",
            "user_email",
            "user_name",
            "league",
            "competition",
            "competition_name",
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
            permissions.append("competition.manage")
        if obj.role in {
            LeagueAdminScope.Role.LEAGUE_ADMIN,
            LeagueAdminScope.Role.COMPETITION_ADMIN,
            LeagueAdminScope.Role.FIXTURES_MANAGER,
        }:
            permissions.append("fixtures.manage")
        if obj.role in {
            LeagueAdminScope.Role.LEAGUE_ADMIN,
            LeagueAdminScope.Role.REGISTRAR,
        }:
            permissions.append("registrations.manage")
        if obj.role in {
            LeagueAdminScope.Role.LEAGUE_ADMIN,
            LeagueAdminScope.Role.OFFICIALS_COORDINATOR,
        }:
            permissions.append("officials.manage")
        return permissions
