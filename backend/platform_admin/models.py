from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

User = settings.AUTH_USER_MODEL


class ApprovalLog(models.Model):
    """
    A centralized log for all significant approval actions across the platform.
    This provides a single place for super administrators to monitor governance.
    """

    class Action(models.TextChoices):
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        SUBMITTED = "SUBMITTED", "Submitted"
        VERIFIED = "VERIFIED", "Verified"

    class Category(models.TextChoices):
        ROLE_MANAGEMENT = "ROLE_MANAGEMENT", "Role Management"
        SPONSORSHIP = "SPONSORSHIP", "Sponsorship"
        PAYMENT = "PAYMENT", "Payment"
        COMPLIANCE = "COMPLIANCE", "Compliance"
        OTHER = "OTHER", "Other"

    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="approvals_made"
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    category = models.CharField(
        max_length=30, choices=Category.choices, default=Category.OTHER
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Generic relation to the object being approved/rejected
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        app_label = "monitoring"
        ordering = ["-created_at"]
        verbose_name = "Approval Log"
        verbose_name_plural = "Approval Logs"

    def __str__(self):
        return f"{self.category} {self.action} by {self.actor} at {self.created_at}"


class ChargebackRefund(models.Model):
    """
    Tracks and manages payment chargebacks and refund requests.
    """

    class DisputeType(models.TextChoices):
        CHARGEBACK = "CHARGEBACK", "Chargeback"
        REFUND_REQUEST = "REFUND_REQUEST", "Refund Request"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        INVESTIGATING = "INVESTIGATING", "Investigating"
        WON = "WON", "Won (Chargeback)"
        LOST = "LOST", "Lost (Chargeback)"
        REFUNDED = "REFUNDED", "Refunded"
        REJECTED = "REJECTED", "Rejected (Refund)"

    # Generic relation to the payment object (e.g., SponsorPayment, TicketOrder)
    payment_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    payment_object_id = models.PositiveIntegerField()
    payment_object = GenericForeignKey("payment_content_type", "payment_object_id")

    dispute_type = models.CharField(max_length=20, choices=DisputeType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    reason = models.TextField(help_text="Reason provided by the customer for the dispute.")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)

    evidence = models.JSONField(
        default=dict, blank=True, help_text="Links or details of evidence submitted."
    )
    resolution_notes = models.TextField(
        blank=True, help_text="Internal notes on how the dispute was resolved."
    )

    opened_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    opened_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="disputes_opened",
        help_text="The user who initiated the dispute.",
    )
    handled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="disputes_handled",
        help_text="The admin who resolved the dispute.",
    )

    class Meta:
        app_label = "monitoring"
        ordering = ["-opened_at"]
        verbose_name = "Chargeback & Refund"
        verbose_name_plural = "Chargebacks & Refunds"

    def __str__(self):
        return f"{self.dispute_type} #{self.id} - {self.status}"