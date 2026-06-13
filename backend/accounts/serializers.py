from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Club

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


class UserSerializer(serializers.ModelSerializer):
    """Serializer for returning safe user data to the frontend."""

    full_name = serializers.CharField(read_only=True)
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

        validate_password(attrs["password"])

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

        validate_password(attrs["password"])

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

        validate_password(attrs["password"])

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

        from django.contrib.auth.password_validation import validate_password

        validate_password(attrs["password"])

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


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating the authenticated user's profile."""

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
            "avatar",
        )

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
        first_name = validated_data.get("first_name")
        last_name = validated_data.get("last_name")

        if first_name is not None:
            instance.first_name = first_name.strip()

        if last_name is not None:
            instance.last_name = last_name.strip()

        if "phone_number" in validated_data:
            instance.phone_number = validated_data["phone_number"]

        if "avatar" in validated_data:
            instance.avatar = validated_data["avatar"]

        instance.save()

        return instance
