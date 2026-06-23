import base64
import hashlib
import hmac
from decimal import Decimal

from django.conf import settings

from sponsorships.flutterwave import (
    FlutterwaveError,
    make_flutterwave_request,
    verify_flutterwave_transaction,
)
from ticketing.models import TicketOrder
from ticketing.services.orders import (
    confirm_ticket_order_payment,
    mark_ticket_order_payment_failed,
)

SUCCESSFUL_FLUTTERWAVE_STATUSES = {"successful", "succeeded"}


def get_flutterwave_status(value):
    return str(value or "").strip().lower()


def build_ticket_checkout_payload(order, request=None):
    buyer = order.buyer
    amount = Decimal(order.total_amount).quantize(Decimal("0.01"))

    redirect_url = settings.FLUTTERWAVE_TICKET_REDIRECT_URL
    if request is not None and not redirect_url:
        redirect_url = request.build_absolute_uri("/api/ticketing/flutterwave/verify/")

    first_item = order.items.select_related("ticket_type", "ticket_type__match").first()
    description = "League OS match ticket purchase"

    if first_item is not None:
        match = first_item.ticket_type.match
        description = (
            f"{first_item.quantity} x {first_item.ticket_type.name} ticket(s) for "
            f"{match.home_club.name} vs {match.away_club.name}"
        )

    return {
        "tx_ref": order.payment_reference,
        "amount": str(amount),
        "currency": order.currency,
        "redirect_url": redirect_url,
        "customer": {
            "email": buyer.email,
            "name": buyer.full_name or buyer.email,
            "phonenumber": buyer.phone_number or "",
        },
        "customizations": {
            "title": settings.FLUTTERWAVE_TICKET_PAYMENT_TITLE,
            "description": description,
            "logo": settings.FLUTTERWAVE_PAYMENT_LOGO_URL,
        },
        "meta": {
            "payment_context": "ticket_order",
            "order_id": order.id,
            "buyer_id": buyer.id,
        },
    }


def initialize_ticket_flutterwave_payment(order, request=None):
    payload = build_ticket_checkout_payload(order, request=request)
    response = make_flutterwave_request("POST", "/payments", payload=payload)

    checkout_url = response.get("data", {}).get("link")
    if response.get("status") != "success" or not checkout_url:
        raise FlutterwaveError(response.get("message", "Could not initialize payment."))

    return response


def validate_ticket_flutterwave_transaction(order, flutterwave_response):
    data = flutterwave_response.get("data", {})
    provider_status = get_flutterwave_status(data.get("status"))

    if provider_status not in SUCCESSFUL_FLUTTERWAVE_STATUSES:
        return False, "Flutterwave transaction was not successful."

    returned_reference = data.get("tx_ref") or data.get("reference")
    if returned_reference != order.payment_reference:
        return False, "Flutterwave transaction reference does not match ticket order."

    if data.get("currency") != order.currency:
        return False, "Flutterwave transaction currency does not match ticket order."

    amount = Decimal(str(data.get("amount", "0")))
    if amount < order.total_amount:
        return False, "Flutterwave transaction amount is less than expected."

    return True, ""


def confirm_ticket_order_from_gateway(order, flutterwave_response):
    data = flutterwave_response.get("data", {})
    provider_transaction_id = str(data.get("id") or data.get("flw_ref") or "")
    provider_status = data.get("status", "successful")

    return confirm_ticket_order_payment(
        order,
        provider_response=flutterwave_response,
        provider_transaction_id=provider_transaction_id,
        provider_status=provider_status,
    )


def mark_ticket_flutterwave_payment_failed(order, flutterwave_response, status_value):
    return mark_ticket_order_payment_failed(
        order,
        provider_response=flutterwave_response,
        provider_status=status_value,
    )


def flutterwave_webhook_signature_is_valid(request):
    secret_hash = settings.FLUTTERWAVE_SECRET_HASH

    if not secret_hash:
        return True

    legacy_signature = (
        request.headers.get("verif-hash")
        or request.headers.get("verifi-hash")
        or request.headers.get("verify-hash")
    )

    if legacy_signature and hmac.compare_digest(legacy_signature, secret_hash):
        return True

    flutterwave_signature = request.headers.get("flutterwave-signature")
    if not flutterwave_signature:
        return False

    expected_signature = base64.b64encode(
        hmac.new(
            secret_hash.encode("utf-8"),
            request.body,
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    return hmac.compare_digest(expected_signature, flutterwave_signature)


def extract_flutterwave_tx_ref(payload):
    data = payload.get("data", payload)

    return (
        data.get("tx_ref")
        or data.get("reference")
        or payload.get("tx_ref")
        or payload.get("reference")
    )


def get_ticket_order_by_reference(tx_ref):
    return TicketOrder.objects.filter(
        payment_reference=tx_ref,
        provider=TicketOrder.PaymentProvider.FLUTTERWAVE,
    ).first()


def verify_and_confirm_ticket_order(tx_ref):
    order = get_ticket_order_by_reference(tx_ref)

    if order is None:
        return None, None, "Ticket order not found."

    flutterwave_response = verify_flutterwave_transaction(tx_ref)
    is_valid, error_message = validate_ticket_flutterwave_transaction(
        order,
        flutterwave_response,
    )

    if not is_valid:
        status_value = flutterwave_response.get("data", {}).get("status", "failed")
        mark_ticket_flutterwave_payment_failed(
            order, flutterwave_response, status_value
        )
        return order, [], error_message

    confirmed_order, issued_tickets = confirm_ticket_order_from_gateway(
        order,
        flutterwave_response,
    )

    return confirmed_order, issued_tickets, ""
