from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from accounts.serializers import UserSerializer, normalize_phone_number
from accounts.services import create_email_verification_otp

from .models import SponsorAccount, SponsorAccountMember


User = get_user_model()


def normalize_country_code(value):
    country_code = (value or "UG").strip().upper()

    if len(country_code) != 2 or not country_code.isalpha():
        raise serializers.ValidationError(
            "Registration country must be a valid 2-letter country code."
        )

    return country_code


def normalize_identifier(value):
    if value in ("", None):
        return None

    return value.strip().upper() or None


def validate_ugandan_tin(tin):
    if tin and (not tin.isdigit() or len(tin) != 10):
        raise serializers.ValidationError("Ugandan TIN should be 10 digits.")


def validate_corporate_identifiers(
    sponsor_type,
    registration_country,
    brn,
    tin,
):
    errors = {}

    if sponsor_type != SponsorAccount.SponsorType.CORPORATE:
        return

    if not brn and not tin:
        errors["brn"] = "Corporate sponsors must provide at least a BRN or TIN."

    if registration_country == "UG":
        try:
            validate_ugandan_tin(tin)
        except serializers.ValidationError as exc:
            errors["tin"] = exc.detail[0]

    if brn:
        brn_exists = SponsorAccount.objects.filter(
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            registration_country=registration_country,
            brn=brn,
        ).exists()

        if brn_exists:
            errors["brn"] = (
                "A corporate sponsor with this BRN already exists in this country."
            )

    if tin:
        tin_exists = SponsorAccount.objects.filter(
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            registration_country=registration_country,
            tin=tin,
        ).exists()

        if tin_exists:
            errors["tin"] = (
                "A corporate sponsor with this TIN already exists in this country."
            )

    if errors:
        raise serializers.ValidationError(errors)


class SponsorAccountMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    member_role_display = serializers.CharField(
        source="get_member_role_display",
        read_only=True,
    )

    class Meta:
        model = SponsorAccountMember
        fields = (
            "id",
            "user",
            "member_role",
            "member_role_display",
            "is_active",
            "created_at",
        )


class SponsorAccountSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    sponsor_type_display = serializers.CharField(
        source="get_sponsor_type_display",
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = SponsorAccount
        fields = (
            "id",
            "owner",
            "sponsor_type",
            "sponsor_type_display",
            "name",
            "registration_country",
            "brn",
            "tin",
            "status",
            "status_display",
            "member_count",
            "created_at",
            "updated_at",
        )

    def get_member_count(self, obj):
        return obj.members.filter(is_active=True).count()


class SponsorRegistrationSerializer(serializers.Serializer):
    """
    Public serializer for direct sponsor registration.

    This creates:
    - User account
    - SponsorAccount
    - SponsorAccountMember as OWNER
    - Email OTP
    """

    sponsor_type = serializers.ChoiceField(choices=SponsorAccount.SponsorType.choices)
    company_name = serializers.CharField(required=False, allow_blank=True)
    registration_country = serializers.CharField(
        required=False,
        allow_blank=True,
        default="UG",
    )
    brn = serializers.CharField(required=False, allow_blank=True)
    tin = serializers.CharField(required=False, allow_blank=True)

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

        sponsor_type = attrs["sponsor_type"]
        company_name = attrs.get("company_name", "").strip()
        registration_country = normalize_country_code(
            attrs.get("registration_country", "UG")
        )
        brn = normalize_identifier(attrs.get("brn"))
        tin = normalize_identifier(attrs.get("tin"))

        if sponsor_type == SponsorAccount.SponsorType.CORPORATE and not company_name:
            raise serializers.ValidationError(
                {"company_name": "Company name is required for corporate sponsors."}
            )

        validate_corporate_identifiers(
            sponsor_type=sponsor_type,
            registration_country=registration_country,
            brn=brn,
            tin=tin,
        )

        attrs["company_name"] = company_name
        attrs["registration_country"] = registration_country
        attrs["brn"] = brn
        attrs["tin"] = tin

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("confirm_password")
        password = validated_data.pop("password")

        sponsor_type = validated_data.pop("sponsor_type")
        company_name = validated_data.pop("company_name")
        registration_country = validated_data.pop("registration_country")
        brn = validated_data.pop("brn")
        tin = validated_data.pop("tin")

        user = User.objects.create_user(
            email=validated_data["email"],
            phone_number=validated_data["phone_number"],
            first_name=validated_data["first_name"].strip(),
            last_name=validated_data["last_name"].strip(),
            password=password,
            role=User.Role.FAN,
        )

        account_name = (
            company_name
            if sponsor_type == SponsorAccount.SponsorType.CORPORATE
            else user.full_name
        )

        sponsor_account = SponsorAccount.objects.create(
            owner=user,
            sponsor_type=sponsor_type,
            name=account_name,
            registration_country=registration_country,
            brn=brn,
            tin=tin,
        )

        SponsorAccountMember.objects.create(
            sponsor_account=sponsor_account,
            user=user,
            member_role=SponsorAccountMember.MemberRole.OWNER,
        )

        create_email_verification_otp(user)

        return sponsor_account


class SponsorAccountCreateSerializer(serializers.Serializer):
    """
    Serializer for an existing logged-in user creating a sponsor account.
    """

    sponsor_type = serializers.ChoiceField(choices=SponsorAccount.SponsorType.choices)
    name = serializers.CharField(required=False, allow_blank=True)
    registration_country = serializers.CharField(
        required=False,
        allow_blank=True,
        default="UG",
    )
    brn = serializers.CharField(required=False, allow_blank=True)
    tin = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        user = self.context["request"].user

        sponsor_type = attrs["sponsor_type"]
        name = attrs.get("name", "").strip()
        registration_country = normalize_country_code(
            attrs.get("registration_country", "UG")
        )
        brn = normalize_identifier(attrs.get("brn"))
        tin = normalize_identifier(attrs.get("tin"))

        if sponsor_type == SponsorAccount.SponsorType.INDIVIDUAL:
            if SponsorAccount.objects.filter(
                owner=user,
                sponsor_type=SponsorAccount.SponsorType.INDIVIDUAL,
            ).exists():
                raise serializers.ValidationError(
                    {
                        "sponsor_type": (
                            "You already have an individual sponsor account."
                        )
                    }
                )

            if not name:
                name = user.full_name

        if sponsor_type == SponsorAccount.SponsorType.CORPORATE and not name:
            raise serializers.ValidationError(
                {"name": "Company name is required for corporate sponsors."}
            )

        validate_corporate_identifiers(
            sponsor_type=sponsor_type,
            registration_country=registration_country,
            brn=brn,
            tin=tin,
        )

        attrs["name"] = name
        attrs["registration_country"] = registration_country
        attrs["brn"] = brn
        attrs["tin"] = tin

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user

        sponsor_account = SponsorAccount.objects.create(
            owner=user,
            sponsor_type=validated_data["sponsor_type"],
            name=validated_data["name"],
            registration_country=validated_data["registration_country"],
            brn=validated_data["brn"],
            tin=validated_data["tin"],
        )

        SponsorAccountMember.objects.create(
            sponsor_account=sponsor_account,
            user=user,
            member_role=SponsorAccountMember.MemberRole.OWNER,
        )

        return sponsor_account


class AddSponsorMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    member_role = serializers.ChoiceField(
        choices=[
            SponsorAccountMember.MemberRole.ADMIN,
            SponsorAccountMember.MemberRole.FINANCE,
            SponsorAccountMember.MemberRole.VIEWER,
        ]
    )

    def validate_email(self, value):
        email = value.strip().lower()

        user = User.objects.filter(email__iexact=email).first()

        if user is None:
            raise serializers.ValidationError("No user exists with this email address.")

        self.context["member_user"] = user

        return email

    def validate(self, attrs):
        sponsor_account = self.context["sponsor_account"]
        member_user = self.context["member_user"]

        if SponsorAccountMember.objects.filter(
            sponsor_account=sponsor_account,
            user=member_user,
        ).exists():
            raise serializers.ValidationError(
                {"email": "This user is already a member of this sponsor account."}
            )

        return attrs

    def create(self, validated_data):
        sponsor_account = self.context["sponsor_account"]
        member_user = self.context["member_user"]

        return SponsorAccountMember.objects.create(
            sponsor_account=sponsor_account,
            user=member_user,
            member_role=validated_data["member_role"],
        )

