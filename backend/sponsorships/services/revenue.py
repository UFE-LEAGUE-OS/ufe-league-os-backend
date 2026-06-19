from decimal import Decimal

from ..models import RevenueDistribution, RevenueShareRule


def get_revenue_share_rules_for_agreement(agreement):
    """
    Agreement-specific revenue share rules override package-level rules.
    """

    agreement_rules = RevenueShareRule.objects.filter(agreement=agreement)

    if agreement_rules.exists():
        return agreement_rules

    return RevenueShareRule.objects.filter(sponsor_package=agreement.sponsor_package)


def generate_revenue_distributions_for_payment(payment):
    """
    Create revenue distribution records after a payment is confirmed.
    """

    rules = get_revenue_share_rules_for_agreement(payment.agreement)
    distributions = []

    for rule in rules:
        amount = rule.fixed_amount

        if amount == 0 and rule.percentage > 0:
            amount = (payment.amount_paid * rule.percentage) / Decimal("100")

        if amount <= 0:
            continue

        distributions.append(
            RevenueDistribution.objects.create(
                payment=payment,
                agreement=payment.agreement,
                recipient_type=rule.recipient_type,
                recipient_identifier=rule.recipient_identifier,
                recipient_name=rule.recipient_name,
                amount=amount,
                currency=payment.currency,
                status=RevenueDistribution.Status.ALLOCATED,
            )
        )

    return distributions
