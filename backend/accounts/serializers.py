from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .google_auth import verify_google_id_token, InvalidGoogleTokenError
from .models import (
    Notification,
    Club,
    Follow,
    NotificationPreference,
    InterestPreference,
    RoleApproval,
    Wallet,
    PaymentHistory,
    FeedItem,
)

User = get_user_model()


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


class BecomeSponsorSerializer(serializers.Serializer):
    sponsor_type = serializers.ChoiceField(choices=User.SponsorType.choices)


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

        if attrs["role"] == User.Role.SPONSOR and not attrs.get("sponsor_type"):
            raise serializers.ValidationError(
                {"sponsor_type": "Sponsor type is required for sponsors."}
            )

        return attrs

    def validate_club_id(self, value):
        if value is None:
            return value

        if not Club.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Club does not exist.")

        return value


class CreateClubOfficialSerializer(serializers.Serializer):
    email = serializers.EmailField()
    phone_number = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(
        choices=[
            (User.Role.REFEREE, User.Role.REFEREE.label),
            (User.Role.TICKETING_OFFICER, User.Role.TICKETING_OFFICER.label),
        ]
    )

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


class HierarchicalCreateUserSerializer(serializers.Serializer):
    """
    Serializer for admin-level user creation that validates the target role
    against the hierarchy defined in CREATABLE_ROLES.

    SPONSOR and FAN are NOT creatable by any admin — they are
    self-registration/self-upgrade roles only.
    """

    email = serializers.EmailField()
    phone_number = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=User.Role.choices)
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

    def validate_role(self, value):
        admin_user = self.context.get("admin_user")
        if admin_user is None:
            raise serializers.ValidationError("Admin context is required.")

        from .rbac import can_admin_create_role

        if not can_admin_create_role(admin_user, value):
            raise serializers.ValidationError(
                f"You are not authorized to create a user with the '{value}' role."
            )

        return value

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

    def validate_club_id(self, value):
        if value is None:
            return value

        if not Club.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Club does not exist.")

        return value


class LoginSerializer(serializers.Serializer):
    """Serializer for login with email or phone number."""

    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs.get("identifier", "").strip()
        password = attrs.get("password", "")

        if not identifier:
            raise serializers.ValidationError(
                {"identifier": "Email or phone number is required."}
            )

        if not password:
            raise serializers.ValidationError({"password": "Password is required."})

        user = self.get_user_by_identifier(identifier)

        if user is None or not user.check_password(password):
            raise serializers.ValidationError("Invalid login credentials.")

        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")

        attrs["user"] = user

        return attrs

    def get_user_by_identifier(self, identifier):
        if "@" in identifier:
            return User.objects.filter(email__iexact=identifier.lower()).first()

        phone_number = normalize_phone_number(identifier)

        return User.objects.filter(phone_number=phone_number).first()


class VerifyOTPSerializer(serializers.Serializer):
    """Serializer for verifying an email OTP."""

    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)
    purpose = serializers.ChoiceField(
        choices=["EMAIL_VERIFICATION"],
        default="EMAIL_VERIFICATION",
        required=False,
    )

    def validate_code(self, value):
        code = value.strip()

        if not code.isdigit():
            raise serializers.ValidationError("OTP code must contain digits only.")

        if len(code) != 6:
            raise serializers.ValidationError("OTP code must be 6 digits long.")

        return code


class ResendOTPSerializer(serializers.Serializer):
    """Serializer for requesting a new email verification OTP."""

    email = serializers.EmailField()


MAX_AVATAR_SIZE_BYTES = 2 * 1024 * 1024

ALLOWED_AVATAR_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for requesting a password reset OTP."""

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for confirming password reset using OTP."""

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


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating the authenticated user's profile."""

    username = serializers.CharField(
        source="public_handle",
        required=False,
        allow_blank=True,
    )
    favorite_sport = serializers.CharField(
        source="favourite_sport",
        required=False,
        allow_blank=True,
    )
    avatar = serializers.ImageField(
        required=False,
        allow_null=True,
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "phone_number",
            "username",
            "location",
            "date_of_birth",
            "gender",
            "favourite_sport",
            "favorite_sport",
            "bio",
            "avatar",
        )

    def validate_username(self, value):
        value = (value or "").strip().lower()

        if not value:
            return ""

        existing_user = User.objects.filter(public_handle__iexact=value)

        if self.instance:
            existing_user = existing_user.exclude(pk=self.instance.pk)

        if existing_user.exists():
            raise serializers.ValidationError("This username is already taken.")

        return value

    def validate_phone_number(self, value):
        if value in ("", None):
            return None

        phone_number = normalize_phone_number(value)

        existing_user = User.objects.filter(phone_number=phone_number)

        if self.instance:
            existing_user = existing_user.exclude(pk=self.instance.pk)

        if existing_user.exists():
            raise serializers.ValidationError(
                "A user with this phone number already exists."
            )

        return phone_number

    def validate_avatar(self, value):
        if value is None:
            return value

        if value.size > MAX_AVATAR_SIZE_BYTES:
            raise serializers.ValidationError("Avatar file size must not exceed 2MB.")

        content_type = getattr(value, "content_type", "")

        if content_type not in ALLOWED_AVATAR_CONTENT_TYPES:
            raise serializers.ValidationError(
                "Avatar must be a JPEG, PNG, WEBP, or GIF image."
            )

        return value

    def update(self, instance, validated_data):
        simple_fields = (
            "first_name",
            "last_name",
            "public_handle",
            "location",
            "date_of_birth",
            "gender",
            "favourite_sport",
            "bio",
        )

        for field in simple_fields:
            if field in validated_data:
                value = validated_data[field]

                if isinstance(value, str):
                    value = value.strip()

                setattr(instance, field, value)

        if "phone_number" in validated_data:
            instance.phone_number = validated_data["phone_number"]

        if "avatar" in validated_data:
            instance.avatar = validated_data["avatar"]

        instance.save()

        return instance


# ---------------------------------------------------------------------------
# Follow / Unfollow Serializers
# ---------------------------------------------------------------------------


class FollowActionSerializer(serializers.Serializer):
    """Serializer for creating or deleting a follow relationship."""

    content_type = serializers.ChoiceField(
        choices=["CLUB", "LEAGUE", "UNION", "COMPETITION"]
    )
    object_id = serializers.IntegerField()


class FollowResponseSerializer(serializers.ModelSerializer):
    """Serializer for follow response data."""

    object_name = serializers.SerializerMethodField()

    class Meta:
        model = Follow
        fields = ["id", "content_type", "object_id", "object_name", "created_at"]

    def get_object_name(self, obj):
        followed = obj.followed_object
        if followed:
            return str(followed)
        return f"{obj.content_type}#{obj.object_id}"


class FollowListSerializer(serializers.Serializer):
    """Serializer for listing a user's follows grouped by content type."""

    club_count = serializers.IntegerField(read_only=True)
    league_count = serializers.IntegerField(read_only=True)
    union_count = serializers.IntegerField(read_only=True)
    competition_count = serializers.IntegerField(read_only=True)
    clubs = FollowResponseSerializer(many=True, read_only=True)
    leagues = FollowResponseSerializer(many=True, read_only=True)
    unions = FollowResponseSerializer(many=True, read_only=True)
    competitions = FollowResponseSerializer(many=True, read_only=True)


# ---------------------------------------------------------------------------
# Notification Preference Serializers
# ---------------------------------------------------------------------------


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for notification preferences."""

    event_label = serializers.CharField(source="get_event_type_display", read_only=True)

    class Meta:
        model = NotificationPreference
        fields = [
            "id",
            "user",
            "event_type",
            "event_label",
            "email_enabled",
            "push_enabled",
            "sms_enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "event_label", "created_at", "updated_at"]


class NotificationSerializer(serializers.ModelSerializer):
    event_label = serializers.CharField(
        source="get_event_type_display",
        read_only=True,
    )
    category_label = serializers.CharField(
        source="get_category_display",
        read_only=True,
    )
    priority_label = serializers.CharField(
        source="get_priority_display",
        read_only=True,
    )

    class Meta:
        model = Notification
        fields = [
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
        ]
        read_only_fields = fields


class BulkNotificationPreferenceSerializer(serializers.Serializer):
    """Serializer for updating multiple notification preferences at once."""

    preferences = NotificationPreferenceSerializer(many=True)


# ---------------------------------------------------------------------------
# Interest & Privacy Preference Serializers
# ---------------------------------------------------------------------------


class InterestPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for interest and privacy preferences."""

    class Meta:
        model = InterestPreference
        exclude = []
        read_only_fields = ["id", "user", "created_at", "updated_at"]


# ---------------------------------------------------------------------------
# Wallet & Payment History Serializers
# ---------------------------------------------------------------------------


class WalletSerializer(serializers.ModelSerializer):
    """
    Serializer for the user's MVP wallet/payment center.

    The MVP wallet does not store money. The balance remains 0.00 and the
    API exposes stored_balance_enabled=false so the frontend can show the
    correct product meaning.
    """

    stored_balance_enabled = serializers.BooleanField(read_only=True)
    balance_note = serializers.CharField(read_only=True)

    class Meta:
        model = Wallet
        fields = [
            "id",
            "user",
            "balance",
            "currency",
            "is_active",
            "stored_balance_enabled",
            "balance_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "balance",
            "stored_balance_enabled",
            "balance_note",
            "created_at",
            "updated_at",
        ]


class PaymentHistorySerializer(serializers.ModelSerializer):
    """Serializer for legacy/manual payment history records."""

    payment_type_label = serializers.CharField(
        source="get_payment_type_display",
        read_only=True,
    )
    status_label = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = PaymentHistory
        fields = [
            "id",
            "user",
            "payment_type",
            "payment_type_label",
            "amount",
            "currency",
            "status",
            "status_label",
            "reference",
            "description",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "payment_type_label",
            "status_label",
            "created_at",
            "updated_at",
        ]


class WalletSummarySerializer(serializers.Serializer):
    """
    Response serializer for the MVP wallet/payment center.

    This is not a stored-money wallet. It summarizes what the fan has paid for.
    """

    stored_balance_enabled = serializers.BooleanField()
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)
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
    recent_payments = serializers.ListField()
    tickets = serializers.ListField()
    memberships = serializers.ListField()
    sponsorships = serializers.ListField()


class CombinedPaymentHistoryItemSerializer(serializers.Serializer):
    """Serializer for combined payment history across tickets, memberships, sponsorships."""

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


# ---------------------------------------------------------------------------
# Role Approval Serializers
# ---------------------------------------------------------------------------


class RoleApprovalListSerializer(serializers.ModelSerializer):
    """Serializer for listing role approval requests."""

    target_user_email = serializers.EmailField(
        source="target_user.email", read_only=True
    )
    target_user_name = serializers.SerializerMethodField()
    requested_by_email = serializers.EmailField(
        source="requested_by.email", read_only=True
    )
    requested_by_name = serializers.SerializerMethodField()
    reviewed_by_email = serializers.EmailField(
        source="reviewed_by.email", read_only=True, default=None
    )
    reviewed_by_name = serializers.SerializerMethodField()
    requested_role_display = serializers.CharField(
        source="get_requested_role_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = RoleApproval
        fields = [
            "id",
            "target_user",
            "target_user_email",
            "target_user_name",
            "requested_role",
            "requested_role_display",
            "requested_by",
            "requested_by_email",
            "requested_by_name",
            "reviewed_by",
            "reviewed_by_email",
            "reviewed_by_name",
            "status",
            "status_display",
            "reason",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "target_user",
            "target_user_email",
            "target_user_name",
            "requested_role",
            "requested_role_display",
            "requested_by",
            "requested_by_email",
            "requested_by_name",
            "reviewed_by",
            "reviewed_by_email",
            "reviewed_by_name",
            "status",
            "status_display",
            "created_at",
            "updated_at",
        ]

    def get_target_user_name(self, obj):
        return obj.target_user.full_name or obj.target_user.email

    def get_requested_by_name(self, obj):
        return obj.requested_by.full_name or obj.requested_by.email

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.full_name or obj.reviewed_by.email
        return None


class RoleApprovalReviewSerializer(serializers.Serializer):
    """Serializer for approving or rejecting a role approval request."""

    action = serializers.ChoiceField(choices=["approve", "reject"])
    rejection_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Required if action is 'reject'.",
    )

    def validate(self, attrs):
        if attrs["action"] == "reject" and not attrs.get("rejection_reason"):
            raise serializers.ValidationError(
                {
                    "rejection_reason": "Rejection reason is required when rejecting a request."
                }
            )
        return attrs


# ---------------------------------------------------------------------------
# Switch Workspace Serializer
# ---------------------------------------------------------------------------


class SwitchWorkspaceSerializer(serializers.Serializer):
    """Serializer for switching the active workspace/role context."""

    role = serializers.ChoiceField(choices=User.Role.choices)

    def validate_role(self, value):
        user = self.context.get("user")
        if not user:
            raise serializers.ValidationError("User context is required.")

        if value not in user.roles:
            raise serializers.ValidationError(
                f"You do not have access to the '{value}' workspace."
            )
        return value


# ---------------------------------------------------------------------------
# Feed Item Serializers
# ---------------------------------------------------------------------------


class FeedItemSerializer(serializers.ModelSerializer):
    """Serializer for personalized feed items."""

    class Meta:
        model = FeedItem
        fields = [
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
        ]
        read_only_fields = [
            "id",
            "user",
            "item_type",
            "title",
            "description",
            "source_content_type",
            "source_object_id",
            "source_name",
            "relevance_score",
            "link",
            "metadata",
            "created_at",
        ]


class GoogleAuthSerializer(serializers.Serializer):
    """Serializer for Google OAuth login/signup using an ID token."""

    id_token = serializers.CharField(write_only=True)

    def validate_id_token(self, value):
        """Verify the Google ID token and return the verified payload."""
        try:
            payload = verify_google_id_token(value)
        except InvalidGoogleTokenError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return payload

    def validate(self, attrs):
        payload = attrs["id_token"]

        email = payload.get("email", "").strip().lower()
        if not email:
            raise serializers.ValidationError(
                "Google account does not have an email address."
            )

        attrs["email"] = email
        attrs["first_name"] = payload.get("given_name", "").strip()
        attrs["last_name"] = payload.get("family_name", "").strip()
        attrs["avatar_url"] = payload.get("picture", "")

        # If given_name/family_name missing, use the full name
        if not attrs["first_name"] and not attrs["last_name"]:
            full_name = payload.get("name", "").strip()
            parts = full_name.split(" ", 1)
            attrs["first_name"] = parts[0]
            if len(parts) > 1:
                attrs["last_name"] = parts[1]

        return attrs
