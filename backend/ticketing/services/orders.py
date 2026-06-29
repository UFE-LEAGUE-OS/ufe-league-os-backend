from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import Notification, NotificationPreference
from accounts.services import create_in_app_notification

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


def get_ticket_reservation_expires_at(now=None):
    now = now or timezone.now()
    reservation_minutes = getattr(settings, "TICKET_RESERVATION_MINUTES", 10)
    return now + timedelta(minutes=reservation_minutes)


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
    Create a pending Flutterwave ticket order and reserve stock temporarily.

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
            reservation_expires_at=get_ticket_reservation_expires_at(),
        )

        TicketOrderItem.objects.create(
            order=order,
            ticket_type=locked_ticket_type,
            quantity=quantity,
            unit_price=locked_ticket_type.price,
            total_price=total_amount,
        )

        return order


def expire_ticket_order_reservation(order, provider_status="reservation_expired"):
    """
    Release an unpaid order reservation.

    Because reserved stock is calculated from active pending orders, releasing the
    reservation means marking when it was released and moving the order out of
    the payable pending state.
    """

    with transaction.atomic():
        locked_order = TicketOrder.objects.select_for_update().get(id=order.id)

        if locked_order.status != TicketOrder.Status.PENDING:
            return locked_order

        if locked_order.reservation_released_at is not None:
            return locked_order

        locked_order.status = TicketOrder.Status.CANCELLED
        locked_order.provider_status = provider_status
        locked_order.reservation_released_at = timezone.now()
        locked_order.save(
            update_fields=[
                "status",
                "provider_status",
                "reservation_released_at",
                "updated_at",
            ]
        )

        return locked_order


def expire_stale_ticket_reservations(now=None):
    """
    Expire all unpaid reservations whose payment window has passed.

    This can be run manually by QA/devs or scheduled later by Celery/cron.
    """

    now = now or timezone.now()

    expired_orders = (
        TicketOrder.objects.select_for_update()
        .filter(
            status=TicketOrder.Status.PENDING,
            reservation_released_at__isnull=True,
            reservation_expires_at__isnull=False,
            reservation_expires_at__lte=now,
        )
        .order_by("id")
    )

    expired_count = 0
    with transaction.atomic():
        for order in expired_orders:
            order.status = TicketOrder.Status.CANCELLED
            order.provider_status = "reservation_expired"
            order.reservation_released_at = now
            order.save(
                update_fields=[
                    "status",
                    "provider_status",
                    "reservation_released_at",
                    "updated_at",
                ]
            )
            expired_count += 1

    return expired_count


def ensure_order_reservation_can_be_paid(order):
    """
    Ensure a pending order can still be paid before issuing tickets.
    """

    if order.is_reservation_expired:
        raise ValidationError(
            {
                "order": (
                    "This ticket reservation has expired. "
                    "Please start checkout again."
                )
            }
        )

    if not order.is_payable:
        raise ValidationError({"order": "This ticket order is no longer payable."})


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

    if order.is_reservation_expired:
        expire_ticket_order_reservation(order)
        raise ValidationError(
            {
                "order": (
                    "This ticket reservation has expired. "
                    "Please start checkout again."
                )
            }
        )

    with transaction.atomic():
        locked_order = TicketOrder.objects.select_for_update().get(id=order.id)

        if locked_order.status == TicketOrder.Status.PAID:
            return locked_order, list(locked_order.tickets.all())

        if locked_order.status != TicketOrder.Status.PENDING:
            raise ValidationError(
                {"order": "Only pending ticket orders can be confirmed."}
            )

        ensure_order_reservation_can_be_paid(locked_order)

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

            current_order_reserved_quantity = item.quantity
            effective_remaining = (
                ticket_type.remaining_quantity + current_order_reserved_quantity
            )

            if effective_remaining < item.quantity:
                raise ValidationError(
                    {
                        "quantity": (
                            "Requested quantity exceeds available ticket stock. "
                            f"Only {ticket_type.remaining_quantity} ticket(s) remain."
                        )
                    }
                )

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
        locked_order.reservation_released_at = locked_order.paid_at
        locked_order.save(
            update_fields=[
                "status",
                "provider_response",
                "provider_transaction_id",
                "provider_status",
                "paid_at",
                "reservation_released_at",
                "updated_at",
            ]
        )

        create_in_app_notification(
            user=locked_order.buyer,
            event_type=NotificationPreference.EventType.TICKET_UPDATES,
            category=Notification.Category.TICKET,
            priority=Notification.Priority.HIGH,
            title="QR ticket issued",
            message="Your ticket payment was confirmed and your QR ticket is ready.",
            action_url="/dashboard/tickets",
            metadata={
                "order_id": locked_order.id,
                "tickets_count": len(issued_tickets),
                "payment_reference": locked_order.payment_reference,
            },
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
        locked_order.reservation_released_at = timezone.now()
        locked_order.save(
            update_fields=[
                "status",
                "provider_status",
                "provider_response",
                "reservation_released_at",
                "updated_at",
            ]
        )

        return locked_order


def normalize_scanned_ticket_code(scanned_code):
    value = str(scanned_code or "").strip()
    if value.startswith("LOS-TICKET:"):
        return value.split(":", 1)[1].strip()
    return value


def validate_ticket_code(scanned_code, scanned_by, match_id=None):
    """
    Validate and check in a ticket.

    Invalid scans are still logged for audit purposes.
    """

    scanned_code = normalize_scanned_ticket_code(scanned_code)

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
