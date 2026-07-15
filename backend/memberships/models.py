from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


# Create your models here.
class MembershipPlan(models.Model):
    class BillingCycle(models.TextChoices):
        MONTHLY = "MONTHLY", "Monthly"
        QUARTERLY = "QUARTERLY", "Quarterly"
        SEMI_ANNUAL = "SEMI_ANNUAL", "Semi-Annual"
        ANNUAL = "ANNUAL", "Annual"

    class Tier(models.TextChoices):
        BASIC = "BASIC", "Basic"
        SILVER = "SILVER", "Silver"
        GOLD = "GOLD", "Gold"
        PLATINUM = "PLATINUM", "Platinum"

    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="membership_plans",
    )

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    tier = models.CharField(max_length=20, choices=Tier.choices, default=Tier.BASIC)
    billing_cycle = models.CharField(
        max_length=20,
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY,
    )
    price_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(max_length=3, default="UGX")

    benefits = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    is_visible = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["club__name", "tier", "billing_cycle"]
        indexes = [
            models.Index(fields=["club", "is_active", "is_visible"]),
            models.Index(fields=["tier"]),
            models.Index(fields=["billing_cycle"]),
        ]

    def __str__(self):
        return f"{self.club.name} - {self.name}"


class MembershipSubscription(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "PENDING_PAYMENT", "Pending Payment"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending Approval"
        ACTIVE = "ACTIVE", "Active"
        PAUSED = "PAUSED", "Paused"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membership_subscriptions",
    )
    plan = models.ForeignKey(
        MembershipPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="membership_subscriptions",
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
    )
    starts_at = models.DateTimeField(blank=True, null=True)
    ends_at = models.DateTimeField(blank=True, null=True)
    cancel_at_next_cycle = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "club"]),
            models.Index(fields=["club", "status"]),
            models.Index(fields=["status", "ends_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "plan", "status"],
                condition=Q(status="ACTIVE"),
                name="unique_active_membership_subscription_per_user_plan",
            )
        ]

    def __str__(self):
        return f"{self.user.email} - {self.plan.name} - {self.status}"


class MembershipPayment(models.Model):
    class PaymentMethod(models.TextChoices):
        MTN_MOMO = "MTN_MOMO", "MTN MoMo"
        AIRTEL_MONEY = "AIRTEL_MONEY", "Airtel Money"
        FLUTTERWAVE = "FLUTTERWAVE", "Flutterwave"
        CARD = "CARD", "Card"
        BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"
        MANUAL = "MANUAL", "Manual"

    class PaymentProvider(models.TextChoices):
        MTN = "MTN", "MTN"
        AIRTEL = "AIRTEL", "Airtel"
        FLUTTERWAVE = "FLUTTERWAVE", "Flutterwave"
        MANUAL = "MANUAL", "Manual"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"
        REFUNDED = "REFUNDED", "Refunded"

    subscription = models.ForeignKey(
        MembershipSubscription,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    subscription_plan = models.ForeignKey(
        MembershipPlan,
        on_delete=models.SET_NULL,
        null=True,
        related_name="payments",
    )

    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(max_length=3, default="UGX")

    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
    )
    provider = models.CharField(
        max_length=30,
        choices=PaymentProvider.choices,
        default=PaymentProvider.MANUAL,
    )

    transaction_reference = models.CharField(max_length=120, blank=True)
    provider_transaction_id = models.CharField(max_length=120, blank=True)
    provider_status = models.CharField(max_length=60, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    checkout_url = models.URLField(blank=True)

    paid_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["subscription", "status"]),
            models.Index(fields=["provider", "status"]),
            models.Index(fields=["transaction_reference"]),
            models.Index(fields=["provider_transaction_id"]),
        ]

    def __str__(self):
        return f"{self.subscription} - {self.amount_paid} {self.currency}"


class MembershipCard(models.Model):
    class CardStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        SUSPENDED = "SUSPENDED", "Suspended"
        REVOKED = "REVOKED", "Revoked"

    subscription = models.OneToOneField(
        MembershipSubscription,
        on_delete=models.CASCADE,
        related_name="membership_card",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membership_cards",
    )
    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="membership_cards",
    )

    card_number = models.CharField(max_length=40, unique=True)
    qr_code_data = models.TextField(blank=True)
    tier = models.CharField(max_length=20)
    billing_cycle = models.CharField(max_length=20)
    issued_at = models.DateTimeField(auto_now_add=True)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=CardStatus.choices,
        default=CardStatus.ACTIVE,
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["user", "status", "valid_until"]),
            models.Index(fields=["club", "status"]),
            models.Index(fields=["card_number"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.club.name} - {self.card_number}"
