from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Invoice(models.Model):
    """
    Represents a financial invoice issued for a payment.
    Can be linked to membership payments, ticket orders, or sponsorship payments.
    """

    class PaymentType(models.TextChoices):
        MEMBERSHIP_FEE = "MEMBERSHIP_FEE", "Membership Fee"
        TICKET_PURCHASE = "TICKET_PURCHASE", "Ticket Purchase"
        SPONSORSHIP = "SPONSORSHIP", "Sponsorship"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ISSUED = "ISSUED", "Issued"
        PAID = "PAID", "Paid"
        PARTIALLY_PAID = "PARTIALLY_PAID", "Partially Paid"
        OVERDUE = "OVERDUE", "Overdue"
        CANCELLED = "CANCELLED", "Cancelled"
        REFUNDED = "REFUNDED", "Refunded"

    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="invoices",
    )
    invoice_number = models.CharField(
        max_length=80, unique=True, blank=True, help_text="Auto-generated if blank."
    )
    payment_type = models.CharField(
        max_length=30, choices=PaymentType.choices, default=PaymentType.OTHER
    )

    # Polymorphic-like references: one of these should be set
    membership_payment = models.ForeignKey(
        "memberships.MembershipPayment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    ticket_order = models.ForeignKey(
        "ticketing.TicketOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    sponsor_payment = models.ForeignKey(
        "sponsorships.SponsorPayment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    buyer_name = models.CharField(max_length=255, blank=True)
    buyer_email = models.EmailField(blank=True)

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    tax_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(max_length=3, default="UGX")

    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.DRAFT
    )

    issue_date = models.DateTimeField(blank=True, null=True)
    due_date = models.DateTimeField(blank=True, null=True)
    paid_date = models.DateTimeField(blank=True, null=True)

    notes = models.TextField(blank=True)
    download_url = models.URLField(
        blank=True, help_text="URL to download PDF if available."
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["club", "status"]),
            models.Index(fields=["club", "payment_type"]),
            models.Index(fields=["invoice_number"]),
            models.Index(fields=["issue_date"]),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number or self.id} - {self.club.name}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self._generate_invoice_number()
        super().save(*args, **kwargs)

    def _generate_invoice_number(self):
        import hashlib
        import time

        raw = f"INV-{self.club_id}-{int(time.time())}-{self.id or 'new'}"
        short_hash = hashlib.md5(raw.encode()).hexdigest()[:8].upper()
        return f"INV-{self.club.slug.upper()}-{short_hash}"


class Receipt(models.Model):
    """
    Represents a receipt issued after a payment is confirmed.
    """

    class PaymentType(models.TextChoices):
        MEMBERSHIP_FEE = "MEMBERSHIP_FEE", "Membership Fee"
        TICKET_PURCHASE = "TICKET_PURCHASE", "Ticket Purchase"
        SPONSORSHIP = "SPONSORSHIP", "Sponsorship"
        OTHER = "OTHER", "Other"

    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="receipts",
    )
    receipt_number = models.CharField(
        max_length=80, unique=True, blank=True, help_text="Auto-generated if blank."
    )
    payment_type = models.CharField(
        max_length=30, choices=PaymentType.choices, default=PaymentType.OTHER
    )

    # Link to the invoice (optional)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipts",
    )

    # Polymorphic-like references
    membership_payment = models.ForeignKey(
        "memberships.MembershipPayment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipts",
    )
    ticket_order = models.ForeignKey(
        "ticketing.TicketOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipts",
    )
    sponsor_payment = models.ForeignKey(
        "sponsorships.SponsorPayment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipts",
    )

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipts",
    )
    buyer_name = models.CharField(max_length=255, blank=True)
    buyer_email = models.EmailField(blank=True)

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    tax_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(max_length=3, default="UGX")

    payment_method = models.CharField(max_length=60, blank=True)
    transaction_reference = models.CharField(max_length=120, blank=True)

    issue_date = models.DateTimeField(blank=True, null=True)
    payment_date = models.DateTimeField(blank=True, null=True)

    notes = models.TextField(blank=True)
    download_url = models.URLField(
        blank=True, help_text="URL to download PDF if available."
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_receipts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["club", "payment_type"]),
            models.Index(fields=["receipt_number"]),
            models.Index(fields=["issue_date"]),
        ]

    def __str__(self):
        return f"Receipt {self.receipt_number or self.id} - {self.club.name}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = self._generate_receipt_number()
        super().save(*args, **kwargs)

    def _generate_receipt_number(self):
        import hashlib
        import time

        raw = f"RCT-{self.club_id}-{int(time.time())}-{self.id or 'new'}"
        short_hash = hashlib.md5(raw.encode()).hexdigest()[:8].upper()
        return f"RCT-{self.club.slug.upper()}-{short_hash}"


class FinanceAuditLog(models.Model):
    """
    Audit trail for all finance-related actions.
    Separate from accounts.AuditLog which is used for RBAC/access violations.
    """

    class Action(models.TextChoices):
        INVOICE_CREATED = "INVOICE_CREATED", "Invoice Created"
        INVOICE_UPDATED = "INVOICE_UPDATED", "Invoice Updated"
        RECEIPT_GENERATED = "RECEIPT_GENERATED", "Receipt Generated"
        PAYMENT_UPDATED = "PAYMENT_UPDATED", "Payment Updated"
        REPORT_VIEWED = "REPORT_VIEWED", "Report Viewed"
        FINANCIAL_RECORD_MODIFIED = (
            "FINANCIAL_RECORD_MODIFIED",
            "Financial Record Modified",
        )

    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="finance_audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="finance_audit_logs",
    )
    action = models.CharField(max_length=50, choices=Action.choices)
    target_type = models.CharField(
        max_length=50, blank=True, help_text="Model name of the target object."
    )
    target_id = models.PositiveIntegerField(
        null=True, blank=True, help_text="ID of the target object."
    )
    target_repr = models.CharField(
        max_length=255, blank=True, help_text="String representation of the target."
    )
    description = models.TextField(blank=True)
    ip_address = models.CharField(max_length=45, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Finance Audit Log"
        verbose_name_plural = "Finance Audit Logs"
        indexes = [
            models.Index(fields=["club", "action"]),
            models.Index(fields=["actor", "action"]),
            models.Index(fields=["action"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} - {self.actor} - {self.created_at}"
