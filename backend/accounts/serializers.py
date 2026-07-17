from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import (
    Notification,
    Club,
    NotificationPreference,
    InterestPreference,
    RoleApproval,
    Wallet,
    PaymentHistory,
    FeedItem,
    Venue,
)
from .google_auth import verify_google_id_token  # noqa: F401

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


class GoogleAuthSerializer(serializers.Serializer):
    token = serializers.CharField()
    invitation_token = serializers.CharField(required=False, allow_blank=True)


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

    class Meta:
        model = User
        fields = (
            "phone_number",
            "location",
            "date_of_birth",
            "gender",
            "favourite_sport",
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
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    code = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        try:
            validate_password(attrs["new_password"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)}) from e
        return attrs


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()


class SwitchWorkspaceSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(required=False, allow_null=True)


class RoleApprovalListSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoleApproval
        fields = ("id", "user", "requested_role", "status", "approved_by", "created_at")
        read_only_fields = ("id", "created_at")


class RoleApprovalReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=RoleApproval.Status.choices)


class CombinedPaymentHistoryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentHistory
        fields = (
            "id",
            "wallet",
            "amount",
            "currency",
            "status",
            "reference",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


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
            "content_type",
            "object_id",
            "title",
            "description",
            "image",
            "published_at",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = (
            "id",
            "user",
            "email_enabled",
            "push_enabled",
            "membership_updates",
            "ticket_updates",
            "sponsorship_updates",
            "governance_updates",
        )
        read_only_fields = (
            "id",
            "user",
        )


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            "id",
            "user",
            "category",
            "title",
            "message",
            "is_read",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "user", "created_at", "updated_at")


class WalletSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ("id", "user", "balance", "currency", "created_at", "updated_at")
        read_only_fields = ("id", "user", "created_at", "updated_at")


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


class FollowResponseSerializer(serializers.Serializer):
    is_following = serializers.BooleanField()


class FollowActionSerializer(serializers.Serializer):
    content_type = serializers.CharField(max_length=50)
    object_id = serializers.IntegerField()


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