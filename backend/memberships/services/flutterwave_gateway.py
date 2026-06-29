from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from memberships.models import MembershipCard, MembershipPayment, MembershipSubscription
from sponsorships.flutterwave import (
    FlutterwaveError,
    make_flutterwave_request,
    verify_flutterwave_transaction,
)

SUCCESSFUL_FLUTTERWAVE_STATUSES = {"successful", "succeeded"}


def make_membership_payment_reference(subscription):
    return f"LOS-MEMBERSHIP-{subscription.id}-{uuid4().hex[:16]}"


def get_flutterwave_status(value):
    return str(value or "").strip().lower()


def build_membership_checkout_payload(payment, request=None):
    subscription = payment.subscription
    user = subscription.user
    plan = subscription.plan
    amount = Decimal(payment.amount_paid).quantize(Decimal("0.01"))

    redirect_url = settings.FLUTTERWAVE_MEMBERSHIP_REDIRECT_URL
    if request is not None and not redirect_url:
        redirect_url = request.build_absolute_uri(
            "/api/memberships/flutterwave/verify/"
        )

    return {
        "tx_ref": payment.transaction_reference,
        "amount": str(amount),
        "currency": payment.currency,
        "redirect_url": redirect_url,
        "customer": {
            "email": user.email,
            "name": user.full_name or user.email,
            "phonenumber": user.phone_number or "",
        },
        "customizations": {
            "title": settings.FLUTTERWAVE_MEMBERSHIP_PAYMENT_TITLE,
            "description": f"{plan.name} membership for {subscription.club.name}",
            "logo": settings.FLUTTERWAVE_PAYMENT_LOGO_URL,
        },
        "meta": {
            "payment_context": "membership",
            "payment_id": payment.id,
            "subscription_id": subscription.id,
            "plan_id": plan.id,
            "club_id": subscription.club.id,
            "user_id": user.id,
        },
    }


def initialize_membership_flutterwave_payment(payment, request=None):
    payload = build_membership_checkout_payload(payment, request=request)
    response = make_flutterwave_request("POST", "/payments", payload=payload)

    checkout_url = response.get("data", {}).get("link")
    if response.get("status") != "success" or not checkout_url:
        raise FlutterwaveError(response.get("message", "Could not initialize payment."))

    return response


def validate_membership_flutterwave_transaction(payment, flutterwave_response):
    data = flutterwave_response.get("data", {})
    provider_status = get_flutterwave_status(data.get("status"))

    if provider_status not in SUCCESSFUL_FLUTTERWAVE_STATUSES:
        return False, "Flutterwave transaction was not successful."

    returned_reference = data.get("tx_ref") or data.get("reference")
    if returned_reference != payment.transaction_reference:
        return (
            False,
            "Flutterwave transaction reference does not match membership payment.",
        )

    if data.get("currency") != payment.currency:
        return (
            False,
            "Flutterwave transaction currency does not match membership payment.",
        )

    amount = Decimal(str(data.get("amount", "0")))
    if amount < payment.amount_paid:
        return False, "Flutterwave transaction amount is less than expected."

    return True, ""


def activate_membership_after_payment(payment, flutterwave_response):
    data = flutterwave_response.get("data", {})
    now = timezone.now()

    payment.status = MembershipPayment.Status.CONFIRMED
    payment.provider_status = data.get("status", "successful")
    payment.provider_response = flutterwave_response
    payment.provider_transaction_id = str(data.get("id") or data.get("flw_ref") or "")
    payment.paid_at = now
    payment.save(
        update_fields=[
            "status",
            "provider_status",
            "provider_response",
            "provider_transaction_id",
            "paid_at",
            "updated_at",
        ]
    )

    subscription = payment.subscription
    subscription.status = MembershipSubscription.Status.ACTIVE
    subscription.starts_at = now

    if subscription.plan.billing_cycle == "ANNUAL":
        subscription.ends_at = now + timedelta(days=365)
    elif subscription.plan.billing_cycle == "SEMI_ANNUAL":
        subscription.ends_at = now + timedelta(days=182)
    elif subscription.plan.billing_cycle == "QUARTERLY":
        subscription.ends_at = now + timedelta(days=91)
    else:
        subscription.ends_at = now + timedelta(days=30)

    subscription.save(update_fields=["status", "starts_at", "ends_at", "updated_at"])

    MembershipCard.objects.get_or_create(
        subscription=subscription,
        defaults={
            "user": subscription.user,
            "club": subscription.club,
            "tier": subscription.plan.tier,
            "billing_cycle": subscription.plan.billing_cycle,
            "card_number": f"MEM-{subscription.club.slug.upper()}-{uuid4().hex[:8].upper()}",
            "qr_code_data": f"membership:{subscription.id}:{subscription.user.id}",
            "valid_from": subscription.starts_at,
            "valid_until": subscription.ends_at,
            "status": MembershipCard.CardStatus.ACTIVE,
        },
    )

    return payment


def mark_membership_flutterwave_payment_failed(
    payment, flutterwave_response, status_value
):
    normalized_status = get_flutterwave_status(status_value)

    payment.status = (
        MembershipPayment.Status.CANCELLED
        if normalized_status in {"cancelled", "canceled"}
        else MembershipPayment.Status.FAILED
    )
    payment.provider_status = status_value
    payment.provider_response = flutterwave_response
    payment.save(
        update_fields=[
            "status",
            "provider_status",
            "provider_response",
            "updated_at",
        ]
    )

    subscription = payment.subscription
    if subscription.status == MembershipSubscription.Status.PENDING_PAYMENT:
        subscription.status = MembershipSubscription.Status.FAILED
        subscription.save(update_fields=["status", "updated_at"])

    return payment


def verify_and_confirm_membership_payment(tx_ref):
    payment = (
        MembershipPayment.objects.select_related(
            "subscription",
            "subscription__user",
            "subscription__plan",
            "subscription__club",
        )
        .filter(
            transaction_reference=tx_ref,
            provider=MembershipPayment.PaymentProvider.FLUTTERWAVE,
        )
        .first()
    )

    if payment is None:
        return None, "Membership payment not found."

    flutterwave_response = verify_flutterwave_transaction(tx_ref)
    is_valid, error_message = validate_membership_flutterwave_transaction(
        payment,
        flutterwave_response,
    )

    if not is_valid:
        status_value = flutterwave_response.get("data", {}).get("status", "failed")
        mark_membership_flutterwave_payment_failed(
            payment,
            flutterwave_response,
            status_value,
        )
        return payment, error_message

    payment = activate_membership_after_payment(payment, flutterwave_response)
    return payment, ""
