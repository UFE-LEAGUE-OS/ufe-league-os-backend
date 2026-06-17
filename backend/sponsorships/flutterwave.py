import json
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


class FlutterwaveError(Exception):
    """
    Raised when League OS cannot initialize or verify a Flutterwave payment.
    """


def flutterwave_is_configured():
    return bool(settings.FLUTTERWAVE_SECRET_KEY)


def get_flutterwave_base_url():
    return settings.FLUTTERWAVE_BASE_URL.rstrip("/")


def make_flutterwave_request(method, path, payload=None, query_params=None):
    """
    Low-level Flutterwave API client.

    This keeps external API calls out of views.py.
    That makes the views easier to read and the payment provider easier to test.
    """

    if not flutterwave_is_configured():
        raise FlutterwaveError("Flutterwave is not configured.")

    url = f"{get_flutterwave_base_url()}{path}"

    if query_params:
        url = f"{url}?{urlencode(query_params)}"

    body = None
    headers = {
        "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = Request(
        url=url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=settings.FLUTTERWAVE_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8")
        raise FlutterwaveError(error_body or str(exc)) from exc
    except (URLError, TimeoutError) as exc:
        raise FlutterwaveError(str(exc)) from exc


def build_checkout_payload(payment, request=None):
    """
    Build the payload sent to Flutterwave's /payments endpoint.
    """

    agreement = payment.agreement
    sponsor_account = agreement.sponsor_account
    sponsor_user = sponsor_account.owner

    amount = Decimal(payment.amount_paid).quantize(Decimal("0.01"))

    redirect_url = settings.FLUTTERWAVE_REDIRECT_URL
    if request is not None and not redirect_url:
        redirect_url = request.build_absolute_uri(
            "/api/sponsorships/flutterwave/verify/"
        )

    return {
        "tx_ref": payment.transaction_reference,
        "amount": str(amount),
        "currency": payment.currency,
        "redirect_url": redirect_url,
        "customer": {
            "email": sponsor_user.email,
            "name": sponsor_user.full_name or sponsor_account.name,
            "phonenumber": sponsor_user.phone_number or "",
        },
        "customizations": {
            "title": settings.FLUTTERWAVE_PAYMENT_TITLE,
            "description": f"Sponsorship payment for {agreement.sponsor_package.name}",
            "logo": settings.FLUTTERWAVE_PAYMENT_LOGO_URL,
        },
        "meta": {
            "payment_id": payment.id,
            "agreement_id": agreement.id,
            "sponsor_account_id": sponsor_account.id,
        },
    }


def initialize_flutterwave_payment(payment, request=None):
    """
    Ask Flutterwave to create a checkout link for this payment.
    """

    payload = build_checkout_payload(payment, request=request)
    response = make_flutterwave_request("POST", "/payments", payload=payload)

    checkout_url = response.get("data", {}).get("link")
    if response.get("status") != "success" or not checkout_url:
        raise FlutterwaveError(response.get("message", "Could not initialize payment."))

    return response


def verify_flutterwave_transaction(tx_ref):
    """
    Verify a Flutterwave transaction by our transaction reference.
    """

    return make_flutterwave_request(
        "GET",
        "/transactions/verify_by_reference",
        query_params={"tx_ref": tx_ref},
    )
