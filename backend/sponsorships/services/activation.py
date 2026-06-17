from ..models import SponsorAgreement, SponsorPayment


def agreement_has_confirmed_payment(agreement):
    return agreement.payments.filter(status=SponsorPayment.Status.CONFIRMED).exists()


def agreement_platform_fee_is_clear(agreement):
    if not agreement.platform_fee_required:
        return True

    return agreement.platform_fee_status in [
        SponsorAgreement.PlatformFeeStatus.PAID,
        SponsorAgreement.PlatformFeeStatus.WAIVED,
    ]


def agreement_can_activate(agreement):
    if agreement.activation_rule == SponsorAgreement.ActivationRule.WAIVED:
        return True

    if agreement.activation_rule == SponsorAgreement.ActivationRule.ADMIN_APPROVAL:
        return True

    if agreement.activation_rule == SponsorAgreement.ActivationRule.PAYMENT_CONFIRMED:
        return agreement_has_confirmed_payment(agreement)

    if (
        agreement.activation_rule
        == SponsorAgreement.ActivationRule.PLATFORM_FEE_CONFIRMED
    ):
        return agreement_platform_fee_is_clear(agreement)

    return False


def get_activation_blocking_reason(agreement):
    if agreement.activation_rule == SponsorAgreement.ActivationRule.PAYMENT_CONFIRMED:
        if not agreement_has_confirmed_payment(agreement):
            return "At least one sponsorship payment must be confirmed first."

    if (
        agreement.activation_rule
        == SponsorAgreement.ActivationRule.PLATFORM_FEE_CONFIRMED
    ):
        if not agreement_platform_fee_is_clear(agreement):
            return "The platform fee must be paid or waived before activation."

    if agreement.platform_fee_required and not agreement_platform_fee_is_clear(
        agreement
    ):
        return "The platform fee must be paid or waived before activation."

    return ""
