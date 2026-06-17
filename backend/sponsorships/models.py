from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

# Create your models here.


class SponsorAccount(models.Model):
    """
    Represents a sponsorship account.

    A sponsor account can be:
    - Individual: one person sponsoring using their personal account.
    - Corporate: a company or brand such as Nile Special, KCB, MTN, etc.

    BRN and TIN are used as unique identifiers for corporate sponsors.
    They are unique per registration country to support future expansion
    outside Uganda.
    """

    class SponsorType(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Individual"
        CORPORATE = "CORPORATE", "Corporate"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_sponsor_accounts",
    )

    sponsor_type = models.CharField(
        max_length=20,
        choices=SponsorType.choices,
    )

    name = models.CharField(max_length=255)

    registration_country = models.CharField(
        max_length=2,
        default="UG",
        help_text="ISO 3166-1 alpha-2 country code where the sponsor is registered.",
    )

    brn = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Business Registration Number for corporate sponsors.",
    )

    tin = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Tax Identification Number for corporate sponsors.",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["sponsor_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["owner"]),
            models.Index(fields=["registration_country"]),
            models.Index(fields=["registration_country", "brn"]),
            models.Index(fields=["registration_country", "tin"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["registration_country", "brn"],
                condition=(
                    Q(sponsor_type="CORPORATE") & Q(brn__isnull=False) & ~Q(brn="")
                ),
                name="unique_corporate_sponsor_brn_per_country",
            ),
            models.UniqueConstraint(
                fields=["registration_country", "tin"],
                condition=(
                    Q(sponsor_type="CORPORATE") & Q(tin__isnull=False) & ~Q(tin="")
                ),
                name="unique_corporate_sponsor_tin_per_country",
            ),
            models.CheckConstraint(
                condition=(
                    Q(sponsor_type="INDIVIDUAL")
                    | (Q(brn__isnull=False) & ~Q(brn=""))
                    | (Q(tin__isnull=False) & ~Q(tin=""))
                ),
                name="corporate_sponsor_requires_brn_or_tin",
            ),
        ]

    def save(self, *args, **kwargs):
        if isinstance(self.registration_country, str):
            self.registration_country = (
                self.registration_country.strip().upper() or "UG"
            )

        if isinstance(self.brn, str):
            self.brn = self.brn.strip().upper() or None

        if isinstance(self.tin, str):
            self.tin = self.tin.strip().upper() or None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_sponsor_type_display()})"

    @property
    def is_individual(self):
        return self.sponsor_type == self.SponsorType.INDIVIDUAL

    @property
    def is_corporate(self):
        return self.sponsor_type == self.SponsorType.CORPORATE


class SponsorAccountMember(models.Model):
    """
    Links users to sponsor accounts.

    This allows a normal fan/user account to also manage sponsorship.
    """

    class MemberRole(models.TextChoices):
        OWNER = "OWNER", "Owner"
        ADMIN = "ADMIN", "Admin"
        FINANCE = "FINANCE", "Finance"
        VIEWER = "VIEWER", "Viewer"

    sponsor_account = models.ForeignKey(
        SponsorAccount,
        on_delete=models.CASCADE,
        related_name="members",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sponsor_memberships",
    )

    member_role = models.CharField(
        max_length=20,
        choices=MemberRole.choices,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sponsor_account", "user__email"]
        constraints = [
            models.UniqueConstraint(
                fields=["sponsor_account", "user"],
                name="unique_sponsor_account_member",
            )
        ]
        indexes = [
            models.Index(fields=["sponsor_account", "member_role"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.sponsor_account.name} - {self.member_role}"


class SponsorshipOwnerType(models.TextChoices):
    CLUB = "CLUB", "Club"
    LEAGUE = "LEAGUE", "League"
    UNION = "UNION", "Union / Federation"
    PLATFORM = "PLATFORM", "Platform"
    SPORT = "SPORT", "Sport"


class SponsorshipScopeType(models.TextChoices):
    PLAYER = "PLAYER", "Player"
    TEAM = "TEAM", "Team"
    CLUB = "CLUB", "Club"
    LEAGUE = "LEAGUE", "League"
    COMPETITION = "COMPETITION", "Competition"
    UNION = "UNION", "Union / Federation"
    SPORT = "SPORT", "Sport"
    EVENT = "EVENT", "Event"
    MATCH = "MATCH", "Match"
    PLATFORM = "PLATFORM", "Platform"


class SponsorCategory(models.TextChoices):
    GENERAL = "GENERAL", "General"
    BEVERAGE = "BEVERAGE", "Beverage"
    BANKING = "BANKING", "Banking"
    TELECOM = "TELECOM", "Telecom"
    BETTING = "BETTING", "Betting"
    TRANSPORT = "TRANSPORT", "Transport"
    INSURANCE = "INSURANCE", "Insurance"
    EDUCATION = "EDUCATION", "Education"
    MEDIA = "MEDIA", "Media"
    HEALTHCARE = "HEALTHCARE", "Healthcare"
    MERCHANDISE = "MERCHANDISE", "Merchandise"
    OTHER = "OTHER", "Other"


class SponsorPackage(models.Model):
    """
    Defines a sponsorship opportunity.

    Examples:
    - Club jersey sponsor
    - Player welfare sponsor
    - Homepage advert
    - National team matchday sponsor
    - League table sponsor
    """

    class SponsorTypeAllowed(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Individual"
        CORPORATE = "CORPORATE", "Corporate"
        BOTH = "BOTH", "Both"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        ACTIVE = "ACTIVE", "Active"
        ARCHIVED = "ARCHIVED", "Archived"

    class ActivationRule(models.TextChoices):
        AFTER_FULL_PAYMENT = "AFTER_FULL_PAYMENT", "After Full Payment"
        AFTER_FIRST_PAYMENT = "AFTER_FIRST_PAYMENT", "After First Payment"
        AFTER_ADMIN_APPROVAL = "AFTER_ADMIN_APPROVAL", "After Admin Approval"
        AFTER_PLATFORM_FEE = "AFTER_PLATFORM_FEE", "After Platform Fee"
        IMMEDIATE = "IMMEDIATE", "Immediate"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    owner_type = models.CharField(
        max_length=20,
        choices=SponsorshipOwnerType.choices,
    )
    owner_identifier = models.CharField(
        max_length=100,
        blank=True,
        help_text="Temporary identifier until the owner module is fully linked.",
    )
    owner_name = models.CharField(max_length=255)

    scope_type = models.CharField(
        max_length=20,
        choices=SponsorshipScopeType.choices,
    )
    scope_identifier = models.CharField(
        max_length=100,
        blank=True,
        help_text="Temporary identifier until target models are fully linked.",
    )
    scope_name = models.CharField(max_length=255)

    sponsor_type_allowed = models.CharField(
        max_length=20,
        choices=SponsorTypeAllowed.choices,
        default=SponsorTypeAllowed.BOTH,
    )

    category = models.CharField(
        max_length=30,
        choices=SponsorCategory.choices,
        default=SponsorCategory.GENERAL,
    )

    price_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(max_length=3, default="UGX")

    is_exclusive = models.BooleanField(default=False)
    requires_platform_fee = models.BooleanField(default=False)
    platform_fee_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
    )

    activation_rule = models.CharField(
        max_length=40,
        choices=ActivationRule.choices,
        default=ActivationRule.AFTER_ADMIN_APPROVAL,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_sponsor_packages",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_sponsor_packages",
    )
    approved_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["owner_type", "owner_name", "name"]
        indexes = [
            models.Index(fields=["owner_type", "owner_identifier"]),
            models.Index(fields=["scope_type", "scope_identifier"]),
            models.Index(fields=["category"]),
            models.Index(fields=["status"]),
            models.Index(fields=["is_exclusive"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.scope_name}"


class SponsorBenefit(models.Model):
    """
    Defines benefits attached to a sponsor package.

    Examples:
    - Free tickets
    - Discounted tickets
    - Logo placement
    - Sponsor badge
    - Email campaign
    - Campaign analytics
    """

    class BenefitType(models.TextChoices):
        FREE_TICKETS = "FREE_TICKETS", "Free Tickets"
        DISCOUNTED_TICKETS = "DISCOUNTED_TICKETS", "Discounted Tickets"
        RESERVED_SEATING = "RESERVED_SEATING", "Reserved Seating"
        VIP_ACCESS = "VIP_ACCESS", "VIP Access"
        DIGITAL_BADGE = "DIGITAL_BADGE", "Digital Badge"
        PUBLIC_RECOGNITION = "PUBLIC_RECOGNITION", "Public Recognition"
        LOGO_PLACEMENT = "LOGO_PLACEMENT", "Logo Placement"
        HOMEPAGE_AD = "HOMEPAGE_AD", "Homepage Advert"
        FAN_DASHBOARD_AD = "FAN_DASHBOARD_AD", "Fan Dashboard Advert"
        EMAIL_CAMPAIGN = "EMAIL_CAMPAIGN", "Email Campaign"
        PUSH_NOTIFICATION = "PUSH_NOTIFICATION", "Push Notification"
        MERCHANDISE_DISCOUNT = "MERCHANDISE_DISCOUNT", "Merchandise Discount"
        CAMPAIGN_ANALYTICS = "CAMPAIGN_ANALYTICS", "Campaign Analytics"
        OTHER = "OTHER", "Other"

    sponsor_package = models.ForeignKey(
        SponsorPackage,
        on_delete=models.CASCADE,
        related_name="benefits",
    )

    benefit_type = models.CharField(
        max_length=40,
        choices=BenefitType.choices,
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    quantity = models.PositiveIntegerField(default=0)
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    value_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
    )

    requires_payment_confirmation = models.BooleanField(default=True)
    is_platform_controlled = models.BooleanField(
        default=False,
        help_text="Controls benefits only League OS can provide.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sponsor_package", "benefit_type", "name"]
        indexes = [
            models.Index(fields=["benefit_type"]),
            models.Index(fields=["is_platform_controlled"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.sponsor_package.name}"


class SponsorAgreement(models.Model):
    """
    Represents the actual sponsorship deal between a sponsor and an owner.

    This is separate from SponsorPackage because a package is only the offer.
    The agreement is the actual accepted sponsorship.
    """

    class AgreementType(models.TextChoices):
        CASH = "CASH", "Cash"
        IN_KIND = "IN_KIND", "In-kind"
        EXISTING_CONTRACT = "EXISTING_CONTRACT", "Existing Contract"
        PLATFORM_ADVERT = "PLATFORM_ADVERT", "Platform Advert"

    class PaymentSource(models.TextChoices):
        PLATFORM = "PLATFORM", "Paid Through Platform"
        OFF_PLATFORM = "OFF_PLATFORM", "Paid Off Platform"
        IN_KIND = "IN_KIND", "In-kind"
        EXISTING_CONTRACT = "EXISTING_CONTRACT", "Existing Contract"
        FREE = "FREE", "Free / Waived"

    class PaymentModel(models.TextChoices):
        ONE_TIME = "ONE_TIME", "One-time"
        RECURRING = "RECURRING", "Recurring"
        INSTALLMENT = "INSTALLMENT", "Installment"
        EXTERNAL = "EXTERNAL", "External"
        FREE = "FREE", "Free"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        APPROVED = "APPROVED", "Approved"
        PENDING_PAYMENT = "PENDING_PAYMENT", "Pending Payment"
        ACTIVE = "ACTIVE", "Active"
        PAUSED = "PAUSED", "Paused"
        EXPIRED = "EXPIRED", "Expired"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        REJECTED = "REJECTED", "Rejected"

    class PlatformFeeStatus(models.TextChoices):
        NOT_REQUIRED = "NOT_REQUIRED", "Not Required"
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        WAIVED = "WAIVED", "Waived"

    class BenefitsTier(models.TextChoices):
        BASIC = "BASIC", "Basic"
        DIGITAL = "DIGITAL", "Digital"
        PREMIUM = "PREMIUM", "Premium"
        REVENUE_SHARE = "REVENUE_SHARE", "Revenue Share"

    class ActivationRule(models.TextChoices):
        PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED", "Payment Confirmed"
        PLATFORM_FEE_CONFIRMED = (
            "PLATFORM_FEE_CONFIRMED",
            "Platform Fee Confirmed",
        )
        ADMIN_APPROVAL = "ADMIN_APPROVAL", "Admin Approval"
        WAIVED = "WAIVED", "Waived"

    sponsor_account = models.ForeignKey(
        SponsorAccount,
        on_delete=models.CASCADE,
        related_name="agreements",
    )
    sponsor_package = models.ForeignKey(
        SponsorPackage,
        on_delete=models.PROTECT,
        related_name="agreements",
    )

    reference = models.CharField(max_length=80, blank=True)

    agreement_type = models.CharField(
        max_length=30,
        choices=AgreementType.choices,
        default=AgreementType.CASH,
    )
    payment_source = models.CharField(
        max_length=30,
        choices=PaymentSource.choices,
        default=PaymentSource.PLATFORM,
    )
    payment_model = models.CharField(
        max_length=30,
        choices=PaymentModel.choices,
        default=PaymentModel.ONE_TIME,
    )

    total_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(max_length=3, default="UGX")

    starts_at = models.DateField(blank=True, null=True)
    ends_at = models.DateField(blank=True, null=True)

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    platform_fee_required = models.BooleanField(default=False)
    platform_fee_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
    )
    platform_fee_status = models.CharField(
        max_length=30,
        choices=PlatformFeeStatus.choices,
        default=PlatformFeeStatus.NOT_REQUIRED,
    )
    platform_activation_allowed = models.BooleanField(default=False)

    benefits_tier = models.CharField(
        max_length=30,
        choices=BenefitsTier.choices,
        default=BenefitsTier.BASIC,
    )
    activation_rule = models.CharField(
        max_length=40,
        choices=ActivationRule.choices,
        default=ActivationRule.ADMIN_APPROVAL,
    )

    waiver_status = models.CharField(max_length=30, blank=True)
    waiver_reason = models.TextField(blank=True)
    waived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="waived_sponsor_agreements",
    )
    waived_at = models.DateTimeField(blank=True, null=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_sponsor_agreements",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_sponsor_agreements",
    )
    approved_at = models.DateTimeField(blank=True, null=True)

    proof_reference = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["sponsor_account", "status"]),
            models.Index(fields=["sponsor_package", "status"]),
            models.Index(fields=["payment_source"]),
            models.Index(fields=["payment_model"]),
            models.Index(fields=["starts_at", "ends_at"]),
        ]

    def __str__(self):
        return f"{self.sponsor_account.name} - {self.sponsor_package.name}"


class SponsorPaymentSchedule(models.Model):
    """
    Defines expected payments for a sponsorship agreement.

    One-time agreement: one schedule row.
    Recurring agreement: one schedule row per cycle.
    Installment agreement: one schedule row per installment.
    """

    class ScheduleType(models.TextChoices):
        ONE_TIME = "ONE_TIME", "One-time"
        RECURRING = "RECURRING", "Recurring"
        INSTALLMENT = "INSTALLMENT", "Installment"
        PLATFORM_FEE = "PLATFORM_FEE", "Platform Fee"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PARTIALLY_PAID = "PARTIALLY_PAID", "Partially Paid"
        PAID = "PAID", "Paid"
        OVERDUE = "OVERDUE", "Overdue"
        WAIVED = "WAIVED", "Waived"
        CANCELLED = "CANCELLED", "Cancelled"

    agreement = models.ForeignKey(
        SponsorAgreement,
        on_delete=models.CASCADE,
        related_name="payment_schedules",
    )

    schedule_type = models.CharField(
        max_length=30,
        choices=ScheduleType.choices,
    )
    sequence_number = models.PositiveIntegerField(default=1)

    due_date = models.DateField()
    period_start = models.DateField(blank=True, null=True)
    period_end = models.DateField(blank=True, null=True)

    amount_due = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(max_length=3, default="UGX")

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["agreement", "sequence_number", "due_date"]
        indexes = [
            models.Index(fields=["agreement", "status"]),
            models.Index(fields=["schedule_type"]),
            models.Index(fields=["due_date"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["agreement", "sequence_number"],
                name="unique_sponsor_payment_schedule_sequence",
            )
        ]

    def __str__(self):
        return (
            f"{self.agreement} - {self.schedule_type} "
            f"{self.sequence_number} - {self.amount_due}"
        )


class SponsorPayment(models.Model):
    """
    Records actual money received for a sponsorship agreement.

    Manual payments are recorded by staff/sponsor admins.
    Flutterwave payments are initialized by League OS, then confirmed only
    after backend verification with Flutterwave.
    """

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Cash"
        BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile Money"
        CARD = "CARD", "Card"
        CHEQUE = "CHEQUE", "Cheque"
        FLUTTERWAVE = "FLUTTERWAVE", "Flutterwave"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        REJECTED = "REJECTED", "Rejected"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"
        REFUNDED = "REFUNDED", "Refunded"
        PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED", "Partially Refunded"

    class PaymentProvider(models.TextChoices):
        MANUAL = "MANUAL", "Manual"
        FLUTTERWAVE = "FLUTTERWAVE", "Flutterwave"

    agreement = models.ForeignKey(
        SponsorAgreement,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    payment_schedule = models.ForeignKey(
        SponsorPaymentSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )

    amount_paid = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(max_length=3, default="UGX")

    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.BANK_TRANSFER,
    )
    transaction_reference = models.CharField(max_length=120, blank=True)

    provider = models.CharField(
        max_length=30,
        choices=PaymentProvider.choices,
        default=PaymentProvider.MANUAL,
    )
    provider_transaction_id = models.CharField(max_length=120, blank=True)
    provider_status = models.CharField(max_length=60, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    checkout_url = models.URLField(blank=True)
    checkout_initialized_at = models.DateTimeField(blank=True, null=True)

    paid_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
    )

    proof_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="recorded_sponsor_payments",
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_sponsor_payments",
    )
    confirmed_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["agreement", "status"]),
            models.Index(fields=["payment_schedule", "status"]),
            models.Index(fields=["transaction_reference"]),
            models.Index(fields=["provider", "provider_status"]),
            models.Index(fields=["provider_transaction_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["transaction_reference"],
                condition=~Q(transaction_reference=""),
                name="unique_sponsor_payment_transaction_reference",
            ),
        ]

    def __str__(self):
        return f"{self.agreement} - {self.amount_paid} {self.currency}"


class RevenueShareRule(models.Model):
    """
    Defines how revenue from a package or agreement should be split.

    The rule can be attached to a package as a default or directly to an
    agreement as an override.
    """

    class RecipientType(models.TextChoices):
        PLAYER = "PLAYER", "Player"
        CLUB = "CLUB", "Club"
        LEAGUE = "LEAGUE", "League"
        UNION = "UNION", "Union / Federation"
        PLATFORM = "PLATFORM", "Platform"
        EVENT_OWNER = "EVENT_OWNER", "Event Owner"
        OTHER = "OTHER", "Other"

    sponsor_package = models.ForeignKey(
        SponsorPackage,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="revenue_share_rules",
    )
    agreement = models.ForeignKey(
        SponsorAgreement,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="revenue_share_rules",
    )

    recipient_type = models.CharField(
        max_length=30,
        choices=RecipientType.choices,
    )
    recipient_identifier = models.CharField(max_length=100, blank=True)
    recipient_name = models.CharField(max_length=255)

    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    fixed_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
    )

    is_platform_share = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["recipient_type", "recipient_name"]
        indexes = [
            models.Index(fields=["recipient_type"]),
            models.Index(fields=["is_platform_share"]),
        ]

    def __str__(self):
        return f"{self.recipient_name} - {self.percentage}%"


class RevenueDistribution(models.Model):
    """
    Actual distribution generated after a payment is confirmed.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ALLOCATED = "ALLOCATED", "Allocated"
        PAID_OUT = "PAID_OUT", "Paid Out"
        CANCELLED = "CANCELLED", "Cancelled"

    payment = models.ForeignKey(
        SponsorPayment,
        on_delete=models.CASCADE,
        related_name="revenue_distributions",
    )
    agreement = models.ForeignKey(
        SponsorAgreement,
        on_delete=models.CASCADE,
        related_name="revenue_distributions",
    )

    recipient_type = models.CharField(
        max_length=30,
        choices=RevenueShareRule.RecipientType.choices,
    )
    recipient_identifier = models.CharField(max_length=100, blank=True)
    recipient_name = models.CharField(max_length=255)

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(max_length=3, default="UGX")

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["agreement", "recipient_type", "recipient_name"]
        indexes = [
            models.Index(fields=["agreement", "status"]),
            models.Index(fields=["payment", "status"]),
            models.Index(fields=["recipient_type"]),
        ]

    def __str__(self):
        return f"{self.recipient_name} - {self.amount} {self.currency}"


class SponsorWorkflowEvent(models.Model):
    """
    Audit trail for sponsor package, agreement, payment and benefit actions.
    """

    class EventType(models.TextChoices):
        PACKAGE_CREATED = "PACKAGE_CREATED", "Package Created"
        PACKAGE_SUBMITTED = "PACKAGE_SUBMITTED", "Package Submitted"
        PACKAGE_APPROVED = "PACKAGE_APPROVED", "Package Approved"
        PACKAGE_REJECTED = "PACKAGE_REJECTED", "Package Rejected"
        AGREEMENT_CREATED = "AGREEMENT_CREATED", "Agreement Created"
        AGREEMENT_SUBMITTED = "AGREEMENT_SUBMITTED", "Agreement Submitted"
        AGREEMENT_APPROVED = "AGREEMENT_APPROVED", "Agreement Approved"
        AGREEMENT_REJECTED = "AGREEMENT_REJECTED", "Agreement Rejected"
        PAYMENT_REGISTERED = "PAYMENT_REGISTERED", "Payment Registered"
        PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED", "Payment Confirmed"
        PAYMENT_REJECTED = "PAYMENT_REJECTED", "Payment Rejected"
        PLATFORM_FEE_WAIVED = "PLATFORM_FEE_WAIVED", "Platform Fee Waived"
        BENEFIT_ISSUED = "BENEFIT_ISSUED", "Benefit Issued"
        AGREEMENT_ACTIVATED = "AGREEMENT_ACTIVATED", "Agreement Activated"
        AGREEMENT_PAUSED = "AGREEMENT_PAUSED", "Agreement Paused"
        AGREEMENT_EXPIRED = "AGREEMENT_EXPIRED", "Agreement Expired"
        AGREEMENT_CANCELLED = "AGREEMENT_CANCELLED", "Agreement Cancelled"

    sponsor_package = models.ForeignKey(
        SponsorPackage,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="workflow_events",
    )
    agreement = models.ForeignKey(
        SponsorAgreement,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="workflow_events",
    )
    payment = models.ForeignKey(
        SponsorPayment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="workflow_events",
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sponsor_workflow_events",
    )

    event_type = models.CharField(max_length=40, choices=EventType.choices)
    from_status = models.CharField(max_length=40, blank=True)
    to_status = models.CharField(max_length=40, blank=True)
    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type"]),
            models.Index(fields=["actor"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.created_at:%Y-%m-%d %H:%M}"
