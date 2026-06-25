from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class TicketType(models.Model):
    """
    Ticket category for a match.

    Examples:
    - Ordinary
    - VIP
    - Student
    - Early Bird
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        SOLD_OUT = "SOLD_OUT", "Sold Out"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled"

    match = models.ForeignKey(
        "dashboards.Match",
        on_delete=models.CASCADE,
        related_name="ticket_types",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(max_length=10, default="UGX")

    quantity_available = models.PositiveIntegerField(default=0)
    quantity_sold = models.PositiveIntegerField(default=0)

    sale_start_at = models.DateTimeField(blank=True, null=True)
    sale_end_at = models.DateTimeField(blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_ticket_types",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["match", "price", "name"]
        indexes = [
            models.Index(fields=["match", "status"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["match", "name"],
                name="unique_ticket_type_name_per_match",
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.match}"

    @property
    def active_reserved_quantity(self):
        """
        Quantity currently held by pending, unexpired orders.

        This protects ticket stock during the Flutterwave checkout window.
        The reservation is released when the order is paid, cancelled, failed,
        or manually expired by the reservation-expiry command.
        """

        total = (
            self.order_items.filter(
                order__status=TicketOrder.Status.PENDING,
                order__reservation_released_at__isnull=True,
                order__reservation_expires_at__gt=timezone.now(),
            ).aggregate(total=models.Sum("quantity"))["total"]
            or 0
        )
        return total

    @property
    def remaining_quantity(self):
        remaining = (
            self.quantity_available - self.quantity_sold - self.active_reserved_quantity
        )
        return max(remaining, 0)

    @property
    def is_sold_out(self):
        return (
            self.quantity_available > 0
            and self.quantity_sold >= self.quantity_available
        )


class TicketOrder(models.Model):
    """
    A fan ticket purchase order.

    Tickets are not issued when this order is created. Tickets are only issued
    after the backend verifies the Flutterwave payment.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        CANCELLED = "CANCELLED", "Cancelled"
        REFUNDED = "REFUNDED", "Refunded"
        FAILED = "FAILED", "Failed"

    class PaymentProvider(models.TextChoices):
        MANUAL = "MANUAL", "Manual"
        FLUTTERWAVE = "FLUTTERWAVE", "Flutterwave"

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ticket_orders",
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(max_length=10, default="UGX")

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    provider = models.CharField(
        max_length=20,
        choices=PaymentProvider.choices,
        default=PaymentProvider.FLUTTERWAVE,
    )
    payment_reference = models.CharField(max_length=120, blank=True)
    provider_transaction_id = models.CharField(max_length=120, blank=True)
    provider_status = models.CharField(max_length=120, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)

    checkout_url = models.URLField(blank=True)
    checkout_initialized_at = models.DateTimeField(blank=True, null=True)

    reservation_expires_at = models.DateTimeField(blank=True, null=True)
    reservation_released_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["buyer", "status"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["payment_reference"]),
            models.Index(fields=["provider", "provider_status"]),
            models.Index(fields=["status", "reservation_expires_at"]),
        ]

    def __str__(self):
        return f"Ticket Order #{self.id} - {self.buyer.email} - {self.status}"

    @property
    def is_reservation_active(self):
        if self.status != self.Status.PENDING:
            return False

        if self.reservation_released_at is not None:
            return False

        if self.reservation_expires_at is None:
            return True

        return self.reservation_expires_at > timezone.now()

    @property
    def is_reservation_expired(self):
        if self.status != self.Status.PENDING:
            return False

        if self.reservation_released_at is not None:
            return False

        if self.reservation_expires_at is None:
            return False

        return self.reservation_expires_at <= timezone.now()

    @property
    def is_payable(self):
        return self.status == self.Status.PENDING and self.is_reservation_active


class TicketOrderItem(models.Model):
    """
    A purchased quantity of one ticket type inside a ticket order.
    """

    order = models.ForeignKey(
        TicketOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )
    ticket_type = models.ForeignKey(
        TicketType,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["order", "ticket_type"]),
            models.Index(fields=["ticket_type"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "ticket_type"],
                name="unique_ticket_type_per_ticket_order",
            )
        ]

    def __str__(self):
        return f"{self.quantity} x {self.ticket_type.name} for order #{self.order_id}"


class Ticket(models.Model):
    """
    A single issued ticket.

    ticket_code will later be encoded into a QR code.
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        USED = "USED", "Used"
        CANCELLED = "CANCELLED", "Cancelled"
        REFUNDED = "REFUNDED", "Refunded"

    order = models.ForeignKey(
        TicketOrder,
        on_delete=models.CASCADE,
        related_name="tickets",
    )
    ticket_type = models.ForeignKey(
        TicketType,
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    match = models.ForeignKey(
        "dashboards.Match",
        on_delete=models.CASCADE,
        related_name="tickets",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets",
    )

    ticket_code = models.UUIDField(default=uuid4, unique=True, editable=False)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    issued_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(blank=True, null=True)

    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="checked_in_tickets",
    )

    class Meta:
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["match", "status"]),
            models.Index(fields=["owner", "status"]),
        ]

    def __str__(self):
        return f"{self.ticket_type.name} ticket - {self.ticket_code}"

    @property
    def qr_payload(self):
        return str(self.ticket_code)


class TicketValidationLog(models.Model):
    """
    Records ticket scan/check-in attempts.
    """

    class Result(models.TextChoices):
        VALID = "VALID", "Valid"
        INVALID = "INVALID", "Invalid"
        ALREADY_USED = "ALREADY_USED", "Already Used"
        CANCELLED = "CANCELLED", "Cancelled"
        WRONG_MATCH = "WRONG_MATCH", "Wrong Match"

    ticket = models.ForeignKey(
        Ticket,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="validation_logs",
    )
    match = models.ForeignKey(
        "dashboards.Match",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ticket_validation_logs",
    )
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ticket_validation_logs",
    )

    scanned_code = models.CharField(max_length=120)
    result = models.CharField(max_length=30, choices=Result.choices)
    message = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["scanned_code"]),
            models.Index(fields=["result", "created_at"]),
            models.Index(fields=["match", "created_at"]),
        ]

    def __str__(self):
        return f"{self.scanned_code} - {self.result}"
