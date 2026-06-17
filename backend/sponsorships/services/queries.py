from ..models import (
    SponsorAgreement,
    SponsorPackage,
    SponsorPayment,
    SponsorPaymentSchedule,
)


def get_sponsor_package_for_request(package_id):
    return (
        SponsorPackage.objects.select_related("created_by", "approved_by")
        .prefetch_related("benefits", "revenue_share_rules")
        .filter(id=package_id)
        .first()
    )


def get_sponsor_agreement_for_request(agreement_id):
    return (
        SponsorAgreement.objects.select_related(
            "sponsor_account",
            "sponsor_package",
            "created_by",
            "approved_by",
            "waived_by",
        )
        .prefetch_related(
            "payment_schedules",
            "payments__revenue_distributions",
            "revenue_share_rules",
            "revenue_distributions",
            "workflow_events",
        )
        .filter(id=agreement_id)
        .first()
    )


def get_sponsor_payment_for_request(payment_id):
    return (
        SponsorPayment.objects.select_related(
            "agreement",
            "agreement__sponsor_account",
            "agreement__sponsor_package",
            "payment_schedule",
            "recorded_by",
            "confirmed_by",
        )
        .prefetch_related("revenue_distributions")
        .filter(id=payment_id)
        .first()
    )


def get_pending_payment_schedule_for_agreement(agreement, payment_schedule_id=None):
    schedules = SponsorPaymentSchedule.objects.filter(
        agreement=agreement,
        status__in=[
            SponsorPaymentSchedule.Status.PENDING,
            SponsorPaymentSchedule.Status.PARTIALLY_PAID,
        ],
    ).order_by("sequence_number", "due_date")

    if payment_schedule_id:
        return schedules.filter(id=payment_schedule_id).first()

    return schedules.first()
