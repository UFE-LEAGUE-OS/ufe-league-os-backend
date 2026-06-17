from django.db import transaction
from django.utils import timezone

from ..models import (
    SponsorAgreement,
    SponsorPayment,
    SponsorPaymentSchedule,
    SponsorWorkflowEvent,
)
from .revenue import generate_revenue_distributions_for_payment
from .workflow import create_sponsor_workflow_event


def agreement_has_confirmed_payment(agreement):
    return agreement.payments.filter(status=SponsorPayment.Status.CONFIRMED).exists()


def agreement_platform_fee_is_clear(agreement):
    if not agreement.platform_fee_required:
        return True

    return agreement.platform_fee_status in [
        SponsorAgreement.PlatformFeeStatus.PAID,
        SponsorAgreement.PlatformFeeStatus.WAIVED,
    ]


def update_payment_schedule_after_confirmation(payment_schedule):
    if payment_schedule is None:
        return

    confirmed_total = sum(
        payment.amount_paid
        for payment in payment_schedule.payments.filter(
            status=SponsorPayment.Status.CONFIRMED,
        )
    )

    if confirmed_total >= payment_schedule.amount_due:
        payment_schedule.status = SponsorPaymentSchedule.Status.PAID
    elif confirmed_total > 0:
        payment_schedule.status = SponsorPaymentSchedule.Status.PARTIALLY_PAID
    else:
        payment_schedule.status = SponsorPaymentSchedule.Status.PENDING

    payment_schedule.save(update_fields=["status", "updated_at"])


def confirm_sponsor_payment(
    payment,
    *,
    actor=None,
    note="Sponsor payment confirmed.",
    activation_note="Agreement activated after payment confirmation.",
    provider_response=None,
):
    """
    Confirm a sponsor payment and run all dependent business rules.

    This is used by both:
    - manual payment confirmation
    - Flutterwave payment confirmation

    The view should only handle HTTP request/response work.
    This service handles the business rules.
    """

    provider_data = {}
    if provider_response is not None:
        provider_data = provider_response.get("data", {})

    with transaction.atomic():
        payment = SponsorPayment.objects.select_for_update().get(id=payment.id)

        if payment.status == SponsorPayment.Status.CONFIRMED:
            return payment, list(payment.revenue_distributions.all())

        old_payment_status = payment.status

        payment.status = SponsorPayment.Status.CONFIRMED
        payment.confirmed_at = timezone.now()

        update_fields = [
            "status",
            "confirmed_at",
        ]

        if actor is not None:
            payment.confirmed_by = actor
            update_fields.append("confirmed_by")

        if payment.paid_at is None:
            payment.paid_at = timezone.now()
            update_fields.append("paid_at")

        if provider_response is not None:
            payment.provider_status = provider_data.get("status", "successful")
            payment.provider_transaction_id = str(provider_data.get("id", ""))
            payment.provider_response = provider_response
            update_fields.extend(
                [
                    "provider_status",
                    "provider_transaction_id",
                    "provider_response",
                ]
            )

        payment.save(update_fields=update_fields)

        update_payment_schedule_after_confirmation(payment.payment_schedule)
        distributions = generate_revenue_distributions_for_payment(payment)

        agreement = payment.agreement
        old_agreement_status = agreement.status

        if agreement.status == SponsorAgreement.Status.APPROVED:
            agreement.status = SponsorAgreement.Status.PENDING_PAYMENT

        if (
            agreement.activation_rule
            == SponsorAgreement.ActivationRule.PAYMENT_CONFIRMED
            and agreement_platform_fee_is_clear(agreement)
        ):
            agreement.status = SponsorAgreement.Status.ACTIVE
            agreement.platform_activation_allowed = True

        agreement.save(
            update_fields=[
                "status",
                "platform_activation_allowed",
                "updated_at",
            ]
        )

        create_sponsor_workflow_event(
            sponsor_package=agreement.sponsor_package,
            agreement=agreement,
            payment=payment,
            actor=actor,
            event_type=SponsorWorkflowEvent.EventType.PAYMENT_CONFIRMED,
            from_status=old_payment_status,
            to_status=payment.status,
            note=note,
        )

        if (
            old_agreement_status != agreement.status
            and agreement.status == SponsorAgreement.Status.ACTIVE
        ):
            create_sponsor_workflow_event(
                sponsor_package=agreement.sponsor_package,
                agreement=agreement,
                payment=payment,
                actor=actor,
                event_type=SponsorWorkflowEvent.EventType.AGREEMENT_ACTIVATED,
                from_status=old_agreement_status,
                to_status=agreement.status,
                note=activation_note,
            )

    return payment, distributions


def reject_sponsor_payment(
    payment,
    *,
    actor,
    note="Sponsor payment rejected.",
):
    old_status = payment.status

    payment.status = SponsorPayment.Status.REJECTED
    payment.confirmed_by = actor
    payment.confirmed_at = timezone.now()
    payment.save(update_fields=["status", "confirmed_by", "confirmed_at"])

    create_sponsor_workflow_event(
        sponsor_package=payment.agreement.sponsor_package,
        agreement=payment.agreement,
        payment=payment,
        actor=actor,
        event_type=SponsorWorkflowEvent.EventType.PAYMENT_REJECTED,
        from_status=old_status,
        to_status=payment.status,
        note=note,
    )

    return payment


def mark_gateway_payment_failed(
    payment,
    *,
    provider_response,
    provider_status,
    failed_status,
    note,
):
    old_status = payment.status

    payment.status = failed_status
    payment.provider_status = provider_status
    payment.provider_response = provider_response
    payment.save(update_fields=["status", "provider_status", "provider_response"])

    create_sponsor_workflow_event(
        sponsor_package=payment.agreement.sponsor_package,
        agreement=payment.agreement,
        payment=payment,
        actor=None,
        event_type=SponsorWorkflowEvent.EventType.PAYMENT_REJECTED,
        from_status=old_status,
        to_status=payment.status,
        note=note,
    )

    return payment
