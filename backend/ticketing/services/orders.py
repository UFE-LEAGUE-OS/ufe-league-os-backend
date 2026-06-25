from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from dashboards.models import Match
from ticketing.models import (
    Ticket,
    TicketOrder,
    TicketOrderItem,
    TicketType,
    TicketValidationLog,
)

PAYABLE_MATCH_STATUSES = {
    Match.Status.SCHEDULED,
    Match.Status.POSTPONED,
}


def make_ticket_order_reference(ticket_type):
    return f"LOS-TICKET-{ticket_type.match_id}-{uuid4().hex[:16]}"


def ticket_type_is_on_sale(ticket_type, now=None):
    now = now or timezone.now()

    if ticket_type.status != TicketType.Status.ACTIVE:
        return False

    if ticket_type.match.status not in PAYABLE_MATCH_STATUSES:
        return False

    if ticket_type.sale_start_at and ticket_type.sale_start_at > now:
        return False

    if ticket_type.sale_end_at and ticket_type.sale_end_at < now:
        return False

    return True


def validate_ticket_type_can_be_purchased(ticket_type, quantity):
    if quantity < 1:
        raise ValidationError({"quantity": "Quantity must be at least 1."})

    if not ticket_type_is_on_sale(ticket_type):
        raise ValidationError(
            {"ticket_type": "This ticket type is not currently available for sale."}
        )

    if ticket_type.remaining_quantity < quantity:
        raise ValidationError(
            {
                "quantity": (
                    "Requested quantity exceeds available ticket stock. "
                    f"Only {ticket_type.remaining_quantity} ticket(s) remain."
                )
            }
        )


def create_ticket_order(buyer, ticket_type, quantity):
    """
    Create a pending Flutterwave ticket order.

    Tickets are not issued here. They are issued only after successful backend
    verification of the Flutterwave payment.
    """

    quantity = int(quantity)

    with transaction.atomic():
        locked_ticket_type = TicketType.objects.select_for_update().get(
            id=ticket_type.id
        )

        validate_ticket_type_can_be_purchased(locked_ticket_type, quantity)

        total_amount = (locked_ticket_type.price * Decimal(quantity)).quantize(
            Decimal("0.01")
        )

        order = TicketOrder.objects.create(
            buyer=buyer,
            total_amount=total_amount,
            currency=locked_ticket_type.currency,
            status=TicketOrder.Status.PENDING,
            provider=TicketOrder.PaymentProvider.FLUTTERWAVE,
            payment_reference=make_ticket_order_reference(locked_ticket_type),
        )

        TicketOrderItem.objects.create(
            order=order,
            ticket_type=locked_ticket_type,
            quantity=quantity,
            unit_price=locked_ticket_type.price,
            total_price=total_amount,
        )

        return order


def confirm_ticket_order_payment(
    order,
    provider_response=None,
    provider_transaction_id="",
    provider_status="successful",
):
    """
    Mark an order paid and issue tickets.

    This is idempotent. If the order was already paid, it returns existing
    tickets and does not issue duplicates.
    """

    provider_response = provider_response or {}

    with transaction.atomic():
        locked_order = TicketOrder.objects.select_for_update().get(id=order.id)

        if locked_order.status == TicketOrder.Status.PAID:
            return locked_order, list(locked_order.tickets.all())

        if locked_order.status != TicketOrder.Status.PENDING:
            raise ValidationError(
                {"order": "Only pending ticket orders can be confirmed."}
            )

        order_items = list(
            locked_order.items.select_related(
                "ticket_type",
                "ticket_type__match",
            ).select_for_update()
        )

        if not order_items:
            raise ValidationError({"order": "Ticket order has no items."})

        issued_tickets = []

        for item in order_items:
            ticket_type = TicketType.objects.select_for_update().get(
                id=item.ticket_type_id
            )

            validate_ticket_type_can_be_purchased(ticket_type, item.quantity)

            ticket_type.quantity_sold += item.quantity
            update_fields = ["quantity_sold", "updated_at"]

            if ticket_type.is_sold_out:
                ticket_type.status = TicketType.Status.SOLD_OUT
                update_fields.append("status")

            ticket_type.save(update_fields=update_fields)

            for _ in range(item.quantity):
                ticket = Ticket.objects.create(
                    order=locked_order,
                    ticket_type=ticket_type,
                    match=ticket_type.match,
                    owner=locked_order.buyer,
                )
                issued_tickets.append(ticket)

        locked_order.status = TicketOrder.Status.PAID
        locked_order.provider_response = provider_response
        locked_order.provider_transaction_id = provider_transaction_id
        locked_order.provider_status = provider_status
        locked_order.paid_at = timezone.now()
        locked_order.save(
            update_fields=[
                "status",
                "provider_response",
                "provider_transaction_id",
                "provider_status",
                "paid_at",
                "updated_at",
            ]
        )

        return locked_order, issued_tickets


def mark_ticket_order_payment_failed(
    order,
    provider_response=None,
    provider_status="failed",
):
    provider_response = provider_response or {}
    normalized_status = str(provider_status or "").strip().lower()

    with transaction.atomic():
        locked_order = TicketOrder.objects.select_for_update().get(id=order.id)

        if locked_order.status == TicketOrder.Status.PAID:
            return locked_order

        failed_status = TicketOrder.Status.CANCELLED
        if normalized_status != "cancelled":
            failed_status = TicketOrder.Status.FAILED

        locked_order.status = failed_status
        locked_order.provider_status = provider_status
        locked_order.provider_response = provider_response
        locked_order.save(
            update_fields=[
                "status",
                "provider_status",
                "provider_response",
                "updated_at",
            ]
        )

        return locked_order


def validate_ticket_code(scanned_code, scanned_by, match_id=None):
    """
    Validate and check in a ticket.

    Invalid scans are still logged for audit purposes.
    """

    scanned_code = str(scanned_code or "").strip()

    with transaction.atomic():
        ticket = (
            Ticket.objects.select_for_update()
            .select_related("match", "ticket_type", "owner")
            .filter(ticket_code=scanned_code)
            .first()
        )

        if ticket is None:
            log = TicketValidationLog.objects.create(
                ticket=None,
                match_id=match_id,
                scanned_by=scanned_by,
                scanned_code=scanned_code,
                result=TicketValidationLog.Result.INVALID,
                message="Ticket code was not found.",
            )
            return None, log

        if match_id is not None and ticket.match_id != int(match_id):
            log = TicketValidationLog.objects.create(
                ticket=ticket,
                match_id=match_id,
                scanned_by=scanned_by,
                scanned_code=scanned_code,
                result=TicketValidationLog.Result.WRONG_MATCH,
                message="Ticket belongs to a different match.",
            )
            return ticket, log

        if ticket.status in [Ticket.Status.CANCELLED, Ticket.Status.REFUNDED]:
            log = TicketValidationLog.objects.create(
                ticket=ticket,
                match=ticket.match,
                scanned_by=scanned_by,
                scanned_code=scanned_code,
                result=TicketValidationLog.Result.CANCELLED,
                message="Ticket is not active.",
            )
            return ticket, log

        if ticket.status == Ticket.Status.USED:
            log = TicketValidationLog.objects.create(
                ticket=ticket,
                match=ticket.match,
                scanned_by=scanned_by,
                scanned_code=scanned_code,
                result=TicketValidationLog.Result.ALREADY_USED,
                message="Ticket has already been used.",
            )
            return ticket, log

        ticket.status = Ticket.Status.USED
        ticket.used_at = timezone.now()
        ticket.checked_in_by = scanned_by
        ticket.save(update_fields=["status", "used_at", "checked_in_by"])

        log = TicketValidationLog.objects.create(
            ticket=ticket,
            match=ticket.match,
            scanned_by=scanned_by,
            scanned_code=scanned_code,
            result=TicketValidationLog.Result.VALID,
            message="Ticket is valid and has been checked in.",
        )

        return ticket, log
