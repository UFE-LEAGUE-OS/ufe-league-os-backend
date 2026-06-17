from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from accounts.serializers import UserSerializer, normalize_phone_number
from accounts.services import create_email_verification_otp

from .models import (
    RevenueDistribution,
    RevenueShareRule,
    SponsorAccount,
    SponsorAccountMember,
    SponsorAgreement,
    SponsorBenefit,
    SponsorPackage,
    SponsorPayment,
    SponsorPaymentSchedule,
    SponsorWorkflowEvent,
)

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
            is_sponsor=True,
            sponsor_type=sponsor_type,
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


class SponsorBenefitSerializer(serializers.ModelSerializer):
    benefit_type_display = serializers.CharField(
        source="get_benefit_type_display",
        read_only=True,
    )

    class Meta:
        model = SponsorBenefit
        fields = (
            "id",
            "sponsor_package",
            "benefit_type",
            "benefit_type_display",
            "name",
            "description",
            "quantity",
            "discount_percentage",
            "value_amount",
            "requires_payment_confirmation",
            "is_platform_controlled",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class RevenueShareRuleSerializer(serializers.ModelSerializer):
    recipient_type_display = serializers.CharField(
        source="get_recipient_type_display",
        read_only=True,
    )

    class Meta:
        model = RevenueShareRule
        fields = (
            "id",
            "sponsor_package",
            "agreement",
            "recipient_type",
            "recipient_type_display",
            "recipient_identifier",
            "recipient_name",
            "percentage",
            "fixed_amount",
            "is_platform_share",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate(self, attrs):
        sponsor_package = attrs.get("sponsor_package")
        agreement = attrs.get("agreement")

        if sponsor_package and agreement:
            raise serializers.ValidationError(
                "A revenue share rule should be attached to either a package "
                "or an agreement, not both."
            )

        if not sponsor_package and not agreement:
            raise serializers.ValidationError(
                "A revenue share rule must be attached to a package or an agreement."
            )

        percentage = attrs.get("percentage", 0)
        fixed_amount = attrs.get("fixed_amount", 0)

        if percentage == 0 and fixed_amount == 0:
            raise serializers.ValidationError(
                "Provide either a percentage or a fixed amount."
            )

        return attrs


class SponsorPackageSerializer(serializers.ModelSerializer):
    owner_type_display = serializers.CharField(
        source="get_owner_type_display",
        read_only=True,
    )
    scope_type_display = serializers.CharField(
        source="get_scope_type_display",
        read_only=True,
    )
    sponsor_type_allowed_display = serializers.CharField(
        source="get_sponsor_type_allowed_display",
        read_only=True,
    )
    category_display = serializers.CharField(
        source="get_category_display",
        read_only=True,
    )
    activation_rule_display = serializers.CharField(
        source="get_activation_rule_display",
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    created_by_email = serializers.EmailField(
        source="created_by.email",
        read_only=True,
    )
    approved_by_email = serializers.EmailField(
        source="approved_by.email",
        read_only=True,
    )
    benefits = SponsorBenefitSerializer(many=True, read_only=True)
    revenue_share_rules = RevenueShareRuleSerializer(many=True, read_only=True)

    class Meta:
        model = SponsorPackage
        fields = (
            "id",
            "name",
            "description",
            "owner_type",
            "owner_type_display",
            "owner_identifier",
            "owner_name",
            "scope_type",
            "scope_type_display",
            "scope_identifier",
            "scope_name",
            "sponsor_type_allowed",
            "sponsor_type_allowed_display",
            "category",
            "category_display",
            "price_amount",
            "currency",
            "is_exclusive",
            "requires_platform_fee",
            "platform_fee_amount",
            "activation_rule",
            "activation_rule_display",
            "status",
            "status_display",
            "created_by",
            "created_by_email",
            "approved_by",
            "approved_by_email",
            "approved_at",
            "benefits",
            "revenue_share_rules",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_by",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        requires_platform_fee = attrs.get(
            "requires_platform_fee",
            getattr(self.instance, "requires_platform_fee", False),
        )
        platform_fee_amount = attrs.get(
            "platform_fee_amount",
            getattr(self.instance, "platform_fee_amount", 0),
        )

        if requires_platform_fee and platform_fee_amount <= 0:
            raise serializers.ValidationError(
                {
                    "platform_fee_amount": (
                        "Platform fee amount is required when the package "
                        "requires a platform fee."
                    )
                }
            )

        return attrs


class SponsorPaymentScheduleSerializer(serializers.ModelSerializer):
    schedule_type_display = serializers.CharField(
        source="get_schedule_type_display",
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = SponsorPaymentSchedule
        fields = (
            "id",
            "agreement",
            "schedule_type",
            "schedule_type_display",
            "sequence_number",
            "due_date",
            "period_start",
            "period_end",
            "amount_due",
            "currency",
            "status",
            "status_display",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        period_start = attrs.get("period_start")
        period_end = attrs.get("period_end")

        if period_start and period_end and period_end < period_start:
            raise serializers.ValidationError(
                {"period_end": "Period end cannot be before period start."}
            )

        return attrs


class RevenueDistributionSerializer(serializers.ModelSerializer):
    recipient_type_display = serializers.CharField(
        source="get_recipient_type_display",
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = RevenueDistribution
        fields = (
            "id",
            "payment",
            "agreement",
            "recipient_type",
            "recipient_type_display",
            "recipient_identifier",
            "recipient_name",
            "amount",
            "currency",
            "status",
            "status_display",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class SponsorPaymentSerializer(serializers.ModelSerializer):
    payment_method_display = serializers.CharField(
        source="get_payment_method_display",
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    recorded_by_email = serializers.EmailField(
        source="recorded_by.email",
        read_only=True,
    )
    confirmed_by_email = serializers.EmailField(
        source="confirmed_by.email",
        read_only=True,
    )
    revenue_distributions = RevenueDistributionSerializer(many=True, read_only=True)

    class Meta:
        model = SponsorPayment
        fields = (
            "id",
            "agreement",
            "payment_schedule",
            "amount_paid",
            "currency",
            "payment_method",
            "payment_method_display",
            "transaction_reference",
            "provider",
            "provider_transaction_id",
            "provider_status",
            "checkout_url",
            "checkout_initialized_at",
            "paid_at",
            "status",
            "status_display",
            "proof_url",
            "notes",
            "recorded_by",
            "recorded_by_email",
            "confirmed_by",
            "confirmed_by_email",
            "confirmed_at",
            "revenue_distributions",
            "created_at",
        )
        read_only_fields = (
            "id",
            "recorded_by",
            "confirmed_by",
            "confirmed_at",
            "provider",
            "provider_transaction_id",
            "provider_status",
            "checkout_url",
            "checkout_initialized_at",
            "revenue_distributions",
            "created_at",
        )


class SponsorWorkflowEventSerializer(serializers.ModelSerializer):
    event_type_display = serializers.CharField(
        source="get_event_type_display",
        read_only=True,
    )
    actor_email = serializers.EmailField(
        source="actor.email",
        read_only=True,
    )

    class Meta:
        model = SponsorWorkflowEvent
        fields = (
            "id",
            "sponsor_package",
            "agreement",
            "payment",
            "actor",
            "actor_email",
            "event_type",
            "event_type_display",
            "from_status",
            "to_status",
            "note",
            "created_at",
        )
        read_only_fields = ("id", "actor", "created_at")


class SponsorAgreementSerializer(serializers.ModelSerializer):
    sponsor_account_detail = SponsorAccountSerializer(
        source="sponsor_account",
        read_only=True,
    )
    sponsor_package_detail = SponsorPackageSerializer(
        source="sponsor_package",
        read_only=True,
    )
    agreement_type_display = serializers.CharField(
        source="get_agreement_type_display",
        read_only=True,
    )
    payment_source_display = serializers.CharField(
        source="get_payment_source_display",
        read_only=True,
    )
    payment_model_display = serializers.CharField(
        source="get_payment_model_display",
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    platform_fee_status_display = serializers.CharField(
        source="get_platform_fee_status_display",
        read_only=True,
    )
    benefits_tier_display = serializers.CharField(
        source="get_benefits_tier_display",
        read_only=True,
    )
    activation_rule_display = serializers.CharField(
        source="get_activation_rule_display",
        read_only=True,
    )
    created_by_email = serializers.EmailField(
        source="created_by.email",
        read_only=True,
    )
    approved_by_email = serializers.EmailField(
        source="approved_by.email",
        read_only=True,
    )
    waived_by_email = serializers.EmailField(
        source="waived_by.email",
        read_only=True,
    )
    payment_schedules = SponsorPaymentScheduleSerializer(many=True, read_only=True)
    payments = SponsorPaymentSerializer(many=True, read_only=True)
    revenue_share_rules = RevenueShareRuleSerializer(many=True, read_only=True)
    revenue_distributions = RevenueDistributionSerializer(many=True, read_only=True)
    workflow_events = SponsorWorkflowEventSerializer(many=True, read_only=True)

    class Meta:
        model = SponsorAgreement
        fields = (
            "id",
            "sponsor_account",
            "sponsor_account_detail",
            "sponsor_package",
            "sponsor_package_detail",
            "reference",
            "agreement_type",
            "agreement_type_display",
            "payment_source",
            "payment_source_display",
            "payment_model",
            "payment_model_display",
            "total_value",
            "currency",
            "starts_at",
            "ends_at",
            "status",
            "status_display",
            "platform_fee_required",
            "platform_fee_amount",
            "platform_fee_status",
            "platform_fee_status_display",
            "platform_activation_allowed",
            "benefits_tier",
            "benefits_tier_display",
            "activation_rule",
            "activation_rule_display",
            "waiver_status",
            "waiver_reason",
            "waived_by",
            "waived_by_email",
            "waived_at",
            "created_by",
            "created_by_email",
            "approved_by",
            "approved_by_email",
            "approved_at",
            "proof_reference",
            "notes",
            "payment_schedules",
            "payments",
            "revenue_share_rules",
            "revenue_distributions",
            "workflow_events",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_by",
            "approved_by",
            "approved_at",
            "waived_by",
            "waived_at",
            "payment_schedules",
            "payments",
            "revenue_share_rules",
            "revenue_distributions",
            "workflow_events",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))

        if starts_at and ends_at and ends_at < starts_at:
            raise serializers.ValidationError(
                {"ends_at": "Agreement end date cannot be before start date."}
            )

        platform_fee_required = attrs.get(
            "platform_fee_required",
            getattr(self.instance, "platform_fee_required", False),
        )
        platform_fee_amount = attrs.get(
            "platform_fee_amount",
            getattr(self.instance, "platform_fee_amount", 0),
        )

        if platform_fee_required and platform_fee_amount <= 0:
            raise serializers.ValidationError(
                {
                    "platform_fee_amount": (
                        "Platform fee amount is required when platform fee "
                        "is required."
                    )
                }
            )

        return attrs
