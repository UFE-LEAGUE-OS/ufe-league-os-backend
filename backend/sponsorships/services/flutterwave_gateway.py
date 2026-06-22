import base64
import hashlib
import hmac
from decimal import Decimal
from uuid import uuid4

from django.conf import settings

from ..models import SponsorPayment
from .payments import confirm_sponsor_payment, mark_gateway_payment_failed

SUCCESSFUL_FLUTTERWAVE_STATUSES = {"successful", "succeeded"}


def make_sponsor_payment_reference(agreement):
    """
    Create a unique transaction reference for Flutterwave.

    This tx_ref is how League OS links its local SponsorPayment to
    the external Flutterwave transaction.
    """

    return f"LOS-SPONSOR-{agreement.id}-{uuid4().hex[:16]}"


def get_flutterwave_status(value):
    return str(value or "").strip().lower()


def validate_flutterwave_transaction(payment, flutterwave_response):
    """
    Never confirm payment unless these checks pass:

    1. Flutterwave says the transaction succeeded.
    2. Flutterwave returns the same tx_ref we created.
    3. Flutterwave returns the same currency.
    4. Flutterwave returns an amount that is not less than expected.
    """

    data = flutterwave_response.get("data", {})
    provider_status = get_flutterwave_status(data.get("status"))

    if provider_status not in SUCCESSFUL_FLUTTERWAVE_STATUSES:
        return False, "Flutterwave transaction was not successful."

    returned_reference = data.get("tx_ref") or data.get("reference")
    if returned_reference != payment.transaction_reference:
        return False, "Flutterwave transaction reference does not match payment record."

    if data.get("currency") != payment.currency:
        return False, "Flutterwave transaction currency does not match payment record."

    amount = Decimal(str(data.get("amount", "0")))
    if amount < payment.amount_paid:
        return False, "Flutterwave transaction amount is less than expected."

    return True, ""


def confirm_sponsor_payment_from_gateway(payment, flutterwave_response):
    """
    Confirm a SponsorPayment after Flutterwave verification succeeds.
    """

    return confirm_sponsor_payment(
        payment,
        actor=None,
        provider_response=flutterwave_response,
        note="Flutterwave payment verified and confirmed.",
        activation_note="Agreement activated after Flutterwave payment confirmation.",
    )


def mark_flutterwave_payment_failed(payment, flutterwave_response, status_value):
    normalized_status = get_flutterwave_status(status_value)

    if normalized_status == "cancelled":
        failed_status = SponsorPayment.Status.CANCELLED
    else:
        failed_status = SponsorPayment.Status.FAILED

    return mark_gateway_payment_failed(
        payment,
        provider_response=flutterwave_response,
        provider_status=status_value,
        failed_status=failed_status,
        note="Flutterwave payment failed or was cancelled.",
    )


def flutterwave_webhook_signature_is_valid(request):
    """
    Supports Flutterwave webhook signature styles.

    Some Flutterwave docs reference 'verif-hash'.
    Newer docs also mention 'flutterwave-signature' using HMAC-SHA256.
    We support both so the integration is safer during documentation/version changes.
    """

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
