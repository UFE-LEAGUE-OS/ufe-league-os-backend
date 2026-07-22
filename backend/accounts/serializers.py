from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .dashboard_entitlements import resolve_dashboard_access
from .models import (
    Notification,
    Club,
    NotificationPreference,
    InterestPreference,
    RoleApproval,
    FeedItem,
    Follow,
    Venue,
)
from .google_auth import (
    GoogleEmailNotVerifiedError,
    InvalidGoogleTokenError,
    verify_google_id_token,
)

User = get_user_model()

MAX_AVATAR_SIZE_BYTES = 2 * 1024 * 1024
ALLOWED_AVATAR_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


def normalize_phone_number(phone_number):
    """Normalize Ugandan phone numbers into +256 format"""

    if not phone_number:
        return phone_number

    value = phone_number.strip().replace(" ", "").replace("-", "")

    if value.startswith("+"):
        return value

    if value.startswith("0"):
        return f"+256{value[1:]}"

    if value.startswith("256"):
        return f"+{value}"

    return value


class UserSummarySerializer(serializers.ModelSerializer):
    """Minimal serializer for user representation in related resources."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "avatar",
        )
        read_only_fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "avatar",
        )


class UserSerializer(serializers.ModelSerializer):
    """Serializer for returning safe user data to the frontend."""

    full_name = serializers.CharField(read_only=True)
    username = serializers.CharField(source="public_handle", read_only=True)
    favorite_sport = serializers.CharField(source="favourite_sport", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    avatar_url = serializers.SerializerMethodField()
    is_sponsor = serializers.BooleanField(read_only=True)
    sponsor_type = serializers.CharField(read_only=True)
    roles = serializers.SerializerMethodField()
    club = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "phone_number",
            "first_name",
            "last_name",
            "full_name",
            "username",
            "location",
            "date_of_birth",
            "gender",
            "favourite_sport",
            "favorite_sport",
            "bio",
            "role",
            "role_display",
            "roles",
            "is_sponsor",
            "sponsor_type",
            "club",
            "avatar",
            "avatar_url",
            "is_email_verified",
            "is_phone_verified",
            "date_joined",
        )

        read_only_fields = (
            "id",
            "role",
            "role_display",
            "roles",
            "is_sponsor",
            "sponsor_type",
            "club",
            "avatar_url",
            "is_email_verified",
            "is_phone_verified",
            "date_joined",
        )

    def get_avatar_url(self, obj):
        request = self.context.get("request")

        if not obj.avatar:
            return None

        if request:
            return request.build_absolute_uri(obj.avatar.url)

        return obj.avatar.url

    def get_roles(self, obj):
        return sorted(list(obj.roles))

    def get_club(self, obj):
        if not obj.club:
            return None

        return {
            "id": obj.club.id,
            "name": obj.club.name,
        }


def get_current_user_dashboard_access(user, context=None):
    """Resolve dashboard access once for a current-user response context."""

    context = context if context is not None else {}
    cached_user_id = context.get("_dashboard_access_user_id")
    if cached_user_id == user.pk and "_dashboard_access" in context:
        return context["_dashboard_access"]

    dashboard_access = resolve_dashboard_access(user)
    context["_dashboard_access_user_id"] = user.pk
    context["_dashboard_access"] = dashboard_access
    return dashboard_access


class CurrentUserSerializer(UserSerializer):
    """Safe authenticated-current-user representation with dashboard access."""

    dashboard_access = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = (*UserSerializer.Meta.fields, "dashboard_access")
        read_only_fields = (*UserSerializer.Meta.read_only_fields, "dashboard_access")

    def get_dashboard_access(self, obj):
        return get_current_user_dashboard_access(obj, self.context)


LEGACY_BACKEND_ROUTES = {
    User.Role.FAN: "/api/dashboards/fan/",
    User.Role.SPONSOR: "/api/dashboards/sponsor/",
    User.Role.SUPER_ADMIN: "/api/dashboards/super-admin/",
    User.Role.LEAGUE_ADMIN: "/api/dashboards/league-admin/",
    User.Role.CLUB_ADMIN: "/api/dashboards/club-admin/",
    User.Role.REFEREE: "/api/dashboards/union-admin/",
    User.Role.UNION_ADMIN: "/api/dashboards/union-admin/",
    User.Role.TICKETING_OFFICER: "/api/dashboards/ticketing-officer/",
}


def entitlement_legacy_role(entitlement):
    """Translate an entitlement dashboard into a valid legacy role selector."""

    dashboard = entitlement["dashboard"]
    if dashboard == "UNION_WORKSPACE":
        if entitlement["workspace_role"] == "MATCH_OFFICIAL":
            return User.Role.REFEREE
        if entitlement["workspace_role"] == "TICKETING_OFFICER":
            return User.Role.TICKETING_OFFICER
        return User.Role.UNION_ADMIN
    return {
        "FAN": User.Role.FAN,
        "SPONSOR": User.Role.SPONSOR,
        "SUPER_ADMIN": User.Role.SUPER_ADMIN,
        "LEAGUE_ADMIN": User.Role.LEAGUE_ADMIN,
        "CLUB_ADMIN": User.Role.CLUB_ADMIN,
        "TICKETING_OFFICER": User.Role.TICKETING_OFFICER,
    }.get(dashboard)


def entitlement_role_display(entitlement, role):
    """Return the real entitlement role label, independent of its selector."""

    if entitlement["dashboard"] == "UNION_WORKSPACE":
        from dashboards.models import UnionWorkspaceMembership

        return dict(UnionWorkspaceMembership.Role.choices).get(
            entitlement["workspace_role"],
            entitlement["workspace_role"],
        )
    return dict(User.Role.choices).get(role, role)


def present_dashboard_entitlement(entitlement):
    """Build one legacy-compatible dashboard selector from an entitlement."""

    role = entitlement_legacy_role(entitlement)
    backend_route = (
        "/api/dashboards/referee/"
        if entitlement["dashboard"] == "UNION_WORKSPACE"
        and entitlement.get("workspace_role") == "MATCH_OFFICIAL"
        else (
            "/api/dashboards/ticketing-officer/"
            if entitlement["dashboard"] == "UNION_WORKSPACE"
            and entitlement.get("workspace_role") == "TICKETING_OFFICER"
            else (
                "/api/dashboards/union-admin/"
                if entitlement["dashboard"] == "UNION_WORKSPACE"
                else LEGACY_BACKEND_ROUTES.get(role)
            )
        )
    )
    return {
        "role": role,
        "role_display": entitlement_role_display(entitlement, role),
        "route": entitlement["route"],
        "backend_route": backend_route,
        "entitlement_id": entitlement["id"],
    }


def present_dashboard_access(dashboard_access):
    """Present all entitlements and the default legacy compatibility entry."""

    entries = [
        present_dashboard_entitlement(item) for item in dashboard_access["entitlements"]
    ]
    default_id = dashboard_access["default_entitlement_id"]
    default_entry = next(
        (item for item in entries if item["entitlement_id"] == default_id),
        None,
    )
    return default_entry, entries


def select_dashboard_route_for_role(entries, role):
    """Select a shared dashboard shell without selecting a workspace."""

    matching_entries = [item for item in entries if item["role"] == role]
    routes = {(item["route"], item["backend_route"]) for item in matching_entries}
    if len(routes) != 1:
        return None, None
    return routes.pop()


class RegisterSerializer(serializers.Serializer):
    """Serializer for user registration"""

    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=20)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        email = value.strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "A user with this email address already exists."
            )

        return email

    def validate_phone_number(self, value):
        phone_number = normalize_phone_number(value)

        if User.objects.filter(phone_number=phone_number).exists():
            raise serializers.ValidationError(
                "A user with this phone number already exists."
            )

        return phone_number

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )

        try:
            validate_password(attrs["password"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)}) from e

        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")

        password = validated_data.pop("password")

        user = User.objects.create_user(
            email=validated_data["email"],
            password=password,
            phone_number=validated_data["phone_number"],
            first_name=validated_data["first_name"].strip(),
            last_name=validated_data["last_name"].strip(),
            role=User.Role.FAN,
        )

        return user


class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField(required=False, write_only=True)
    token = serializers.CharField(required=False, write_only=True)
    invitation_token = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        raw_token = attrs.get("id_token") or attrs.get("token")
        if not raw_token:
            raise serializers.ValidationError(
                {"id_token": "A Google ID token is required."}
            )

        try:
            payload = verify_google_id_token(raw_token)
        except (InvalidGoogleTokenError, GoogleEmailNotVerifiedError) as exc:
            raise serializers.ValidationError({"id_token": str(exc)}) from exc

        email = payload.get("email", "").strip().lower()
        if not email:
            raise serializers.ValidationError(
                {"id_token": "Google account does not have an email address."}
            )

        attrs["email"] = email
        attrs["first_name"] = payload.get("given_name", "").strip()
        attrs["last_name"] = payload.get("family_name", "").strip()

        if not attrs["first_name"] and not attrs["last_name"]:
            name_parts = payload.get("name", "").strip().split(" ", 1)
            attrs["first_name"] = name_parts[0] if name_parts else ""
            attrs["last_name"] = name_parts[1] if len(name_parts) > 1 else ""

        return attrs


class BecomeSponsorSerializer(serializers.Serializer):
    sponsor_type = serializers.ChoiceField(choices=User.SponsorType.choices)


class HierarchicalCreateUserSerializer(serializers.Serializer):
    email = serializers.EmailField()
    phone_number = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=User.Role.choices)
    sponsor_type = serializers.ChoiceField(
        choices=User.SponsorType.choices, required=False, allow_blank=True
    )
    club_id = serializers.IntegerField(required=False)

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "A user with this email address already exists."
            )
        return email

    def validate_phone_number(self, value):
        if not value:
            return value
        phone_number = normalize_phone_number(value)
        if User.objects.filter(phone_number=phone_number).exists():
            raise serializers.ValidationError(
                "A user with this phone number already exists."
            )
        return phone_number

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        try:
            validate_password(attrs["password"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)}) from e

        admin_user = self.context.get("admin_user")
        if admin_user:
            from .rbac import can_admin_create_role

            if not can_admin_create_role(admin_user, attrs["role"]):
                raise serializers.ValidationError(
                    {"role": "You cannot create a user with this role."}
                )
        return attrs


class AdminCreateUserSerializer(serializers.Serializer):
    email = serializers.EmailField()
    phone_number = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=User.Role.choices)
    sponsor_type = serializers.ChoiceField(
        choices=User.SponsorType.choices,
        required=False,
        allow_blank=True,
    )
    club_id = serializers.IntegerField(required=False)

    def validate_email(self, value):
        email = value.strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "A user with this email address already exists."
            )

        return email

    def validate_phone_number(self, value):
        if not value:
            return value

        phone_number = normalize_phone_number(value)

        if User.objects.filter(phone_number=phone_number).exists():
            raise serializers.ValidationError(
                "A user with this phone number already exists."
            )

        return phone_number

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )

        try:
            validate_password(attrs["password"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)}) from e

        return attrs


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating the authenticated user's profile."""

    favorite_sport = serializers.CharField(
        source="favourite_sport",
        required=False,
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "phone_number",
            "location",
            "date_of_birth",
            "gender",
            "favourite_sport",
            "favorite_sport",
            "bio",
            "avatar",
        )

    def validate_phone_number(self, value):
        if not value:
            return value

        phone_number = normalize_phone_number(value)

        if (
            User.objects.filter(phone_number=phone_number)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                "A user with this phone number already exists."
            )

        return phone_number

    def validate_avatar(self, value):
        if value is None:
            return value
        if value.size > MAX_AVATAR_SIZE_BYTES:
            raise serializers.ValidationError("Avatar file size must not exceed 2MB.")
        if getattr(value, "content_type", "") not in ALLOWED_AVATAR_CONTENT_TYPES:
            raise serializers.ValidationError(
                "Avatar must be a JPEG, PNG, WEBP, or GIF image."
            )
        return value

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save(update_fields=list(validated_data.keys()))
        return instance


class ClubSerializer(serializers.ModelSerializer):
    """Read serializer for club profile/branding."""

    logo_url = serializers.SerializerMethodField()
    banner_url = serializers.SerializerMethodField()

    class Meta:
        model = Club
        fields = (
            "id",
            "name",
            "slug",
            "short_name",
            "sport",
            "logo",
            "logo_url",
            "banner",
            "banner_url",
            "primary_color",
            "secondary_color",
        )

    def get_logo_url(self, obj):
        request = self.context.get("request")
        if not obj.logo:
            return None
        if request:
            return request.build_absolute_uri(obj.logo.url)
        return obj.logo.url

    def get_banner_url(self, obj):
        request = self.context.get("request")
        if not obj.banner:
            return None
        if request:
            return request.build_absolute_uri(obj.banner.url)
        return obj.banner.url


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs.get("identifier", "").strip()
        password = attrs.get("password", "")

        user = self.get_user_by_identifier(identifier)
        if user is None or not user.check_password(password):
            raise serializers.ValidationError("Invalid login credentials.")

        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")

        attrs["user"] = user
        return attrs

    @staticmethod
    def get_user_by_identifier(identifier):
        if "@" in identifier:
            return User.objects.filter(email__iexact=identifier).first()

        phone_number = normalize_phone_number(identifier)
        user = User.objects.filter(phone_number=phone_number).first()
        if user:
            return user

        return User.objects.filter(public_handle__iexact=identifier).first()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_code(self, value):
        code = value.strip()
        if not code.isdigit():
            raise serializers.ValidationError("OTP code must contain digits only.")
        if len(code) != 6:
            raise serializers.ValidationError("OTP code must be 6 digits long.")
        return code

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        try:
            validate_password(attrs["password"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)}) from e
        return attrs


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()


class SwitchWorkspaceSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices)

    def validate_role(self, value):
        user = self.context.get("user")
        if not user:
            raise serializers.ValidationError("User context is required.")

        dashboard_access = get_current_user_dashboard_access(user, self.context)
        matching_entitlements = self._matching_entitlements(
            value, dashboard_access["entitlements"]
        )
        if not matching_entitlements:
            raise serializers.ValidationError(
                f"You do not have access to the '{value}' workspace."
            )

        self.context["_matching_entitlements"] = matching_entitlements
        return value

    @staticmethod
    def _matching_entitlements(role, entitlements):
        return [item for item in entitlements if entitlement_legacy_role(item) == role]


class RoleApprovalListSerializer(serializers.ModelSerializer):
    target_user_email = serializers.EmailField(
        source="target_user.email", read_only=True
    )
    requested_by_email = serializers.EmailField(
        source="requested_by.email", read_only=True
    )
    reviewed_by_email = serializers.EmailField(
        source="reviewed_by.email", read_only=True, default=None
    )

    class Meta:
        model = RoleApproval
        fields = (
            "id",
            "target_user",
            "target_user_email",
            "requested_role",
            "requested_by",
            "requested_by_email",
            "reviewed_by",
            "reviewed_by_email",
            "status",
            "reason",
            "rejection_reason",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class RoleApprovalReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["action"] == "reject" and not attrs.get("rejection_reason"):
            raise serializers.ValidationError(
                {"rejection_reason": "Rejection reason is required."}
            )
        return attrs


class CombinedPaymentHistoryItemSerializer(serializers.Serializer):
    id = serializers.CharField()
    source = serializers.CharField()
    source_id = serializers.IntegerField(required=False)
    payment_type = serializers.CharField()
    payment_type_label = serializers.CharField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField()
    status = serializers.CharField()
    status_label = serializers.CharField()
    reference = serializers.CharField(allow_blank=True)
    description = serializers.CharField(allow_blank=True)
    metadata = serializers.DictField()
    created_at = serializers.DateTimeField(required=False)


PaymentHistorySerializer = CombinedPaymentHistoryItemSerializer


class ClubProfileUpdateSerializer(serializers.ModelSerializer):
    """Update serializer for club profile/branding."""

    logo = serializers.ImageField(required=False, allow_null=True)
    banner = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Club
        fields = (
            "name",
            "short_name",
            "sport",
            "logo",
            "banner",
            "primary_color",
            "secondary_color",
        )

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save(update_fields=list(validated_data.keys()))
        return instance


class FeedItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedItem
        fields = (
            "id",
            "user",
            "item_type",
            "title",
            "description",
            "source_content_type",
            "source_object_id",
            "source_name",
            "relevance_score",
            "is_read",
            "link",
            "metadata",
            "created_at",
        )
        read_only_fields = fields


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    event_label = serializers.CharField(
        source="get_event_type_display",
        read_only=True,
    )

    class Meta:
        model = NotificationPreference
        fields = (
            "id",
            "user",
            "event_type",
            "event_label",
            "email_enabled",
            "push_enabled",
            "sms_enabled",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "user",
        )


class NotificationSerializer(serializers.ModelSerializer):
    event_label = serializers.CharField(source="get_event_type_display", read_only=True)
    category_label = serializers.CharField(
        source="get_category_display", read_only=True
    )
    priority_label = serializers.CharField(
        source="get_priority_display", read_only=True
    )

    class Meta:
        model = Notification
        fields = (
            "id",
            "event_type",
            "event_label",
            "category",
            "category_label",
            "priority",
            "priority_label",
            "title",
            "message",
            "action_url",
            "metadata",
            "is_read",
            "read_at",
            "created_at",
        )
        read_only_fields = fields


class WalletSummarySerializer(serializers.Serializer):
    stored_balance_enabled = serializers.BooleanField()
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    balance_note = serializers.CharField()
    currency = serializers.CharField()
    total_spent = serializers.DecimalField(max_digits=14, decimal_places=2)
    successful_payments_count = serializers.IntegerField()
    pending_payments_count = serializers.IntegerField()
    failed_payments_count = serializers.IntegerField()
    refunded_payments_count = serializers.IntegerField()
    tickets_count = serializers.IntegerField()
    memberships_count = serializers.IntegerField()
    sponsorships_count = serializers.IntegerField()
    recent_payments = CombinedPaymentHistoryItemSerializer(many=True)
    tickets = serializers.ListField(child=serializers.DictField())
    memberships = serializers.ListField(child=serializers.DictField())
    sponsorships = serializers.ListField(child=serializers.DictField())


class InterestPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterestPreference
        fields = (
            "id",
            "user",
            "interested_in_clubs",
            "interested_in_leagues",
            "interested_in_unions",
            "interested_in_national_teams",
            "interested_in_transfers",
            "interested_in_highlights",
            "interested_in_tickets",
            "interested_in_merchandise",
            "profile_visibility",
            "show_followed_teams",
            "show_attended_matches",
            "activity_visibility",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "user", "created_at", "updated_at")


class FollowResponseSerializer(serializers.ModelSerializer):
    object_name = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = Follow
        fields = (
            "id",
            "content_type",
            "object_id",
            "object_name",
            "is_following",
            "created_at",
        )
        read_only_fields = fields

    def get_object_name(self, obj):
        followed_object = obj.followed_object
        if followed_object is not None:
            return str(followed_object)
        return f"{obj.content_type}#{obj.object_id}"

    def get_is_following(self, _obj):
        return True


class FollowActionSerializer(serializers.Serializer):
    content_type = serializers.ChoiceField(choices=Follow.ContentType.choices)
    object_id = serializers.IntegerField(min_value=1)


class VenueSerializer(serializers.ModelSerializer):
    """Serializer for club venues."""

    class Meta:
        model = Venue
        fields = (
            "id",
            "club",
            "name",
            "location",
            "pitch_count",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "club", "created_at", "updated_at")
