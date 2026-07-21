from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone

from memberships.models import MembershipPayment
from ticketing.models import TicketOrder
from sponsorships.models import SponsorPayment

from .models import FinanceAuditLog, Invoice, Receipt


def log_finance_action(
    *,
    club,
    actor=None,
    action,
    target_type="",
    target_id=None,
    target_repr="",
    description="",
    ip_address="",
    metadata=None,
):
    """
    Create a finance audit log entry.
    """
    return FinanceAuditLog.objects.create(
        club=club,
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_repr=target_repr,
        description=description,
        ip_address=ip_address,
        metadata=metadata or {},
    )


@transaction.atomic
def create_invoice_from_membership_payment(payment, created_by=None, ip_address=""):
    """
    Create an invoice for a membership payment.
    """
    subscription = payment.subscription
    club = subscription.club
    user = subscription.user

    invoice = Invoice.objects.create(
        club=club,
        payment_type=Invoice.PaymentType.MEMBERSHIP_FEE,
        membership_payment=payment,
        member=user,
        buyer_name=user.full_name or user.email,
        buyer_email=user.email,
        amount=payment.amount_paid,
        currency=payment.currency,
        status=(
            Invoice.Status.PAID
            if payment.status == MembershipPayment.Status.CONFIRMED
            else Invoice.Status.ISSUED
        ),
        issue_date=timezone.now(),
        paid_date=payment.paid_at,
        created_by=created_by,
    )

    log_finance_action(
        club=club,
        actor=created_by,
        action=FinanceAuditLog.Action.INVOICE_CREATED,
        target_type="Invoice",
        target_id=invoice.id,
        target_repr=str(invoice),
        description=f"Invoice {invoice.invoice_number} created for membership payment {payment.transaction_reference}",
        ip_address=ip_address,
    )

    return invoice


@transaction.atomic
def create_invoice_from_ticket_order(order, created_by=None, ip_address=""):
    """
    Create an invoice for a ticket order.
    """
    # Determine club from the first ticket type's match
    first_item = order.items.select_related("ticket_type__match__home_club").first()
    if not first_item:
        return None

    club = first_item.ticket_type.match.home_club

    invoice = Invoice.objects.create(
        club=club,
        payment_type=Invoice.PaymentType.TICKET_PURCHASE,
        ticket_order=order,
        member=order.buyer,
        buyer_name=order.buyer.full_name or order.buyer.email,
        buyer_email=order.buyer.email,
        amount=order.total_amount,
        currency=order.currency,
        status=(
            Invoice.Status.PAID
            if order.status == TicketOrder.Status.PAID
            else Invoice.Status.ISSUED
        ),
        issue_date=timezone.now(),
        paid_date=order.paid_at,
        created_by=created_by,
    )

    log_finance_action(
        club=club,
        actor=created_by,
        action=FinanceAuditLog.Action.INVOICE_CREATED,
        target_type="Invoice",
        target_id=invoice.id,
        target_repr=str(invoice),
        description=f"Invoice {invoice.invoice_number} created for ticket order #{order.id}",
        ip_address=ip_address,
    )

    return invoice


@transaction.atomic
def create_invoice_from_sponsor_payment(payment, created_by=None, ip_address=""):
    """
    Create an invoice for a sponsorship payment.
    """
    agreement = payment.agreement
    # Determine club from the sponsor package's owner
    sponsor_package = agreement.sponsor_package
    # Try to find the club from the package's scope or owner
    club = None
    if sponsor_package.owner_type == "CLUB":
        from accounts.models import Club

        club = (
            Club.objects.filter(id=int(sponsor_package.owner_identifier)).first()
            if sponsor_package.owner_identifier.isdigit()
            else None
        )

    if not club:
        return None

    invoice = Invoice.objects.create(
        club=club,
        payment_type=Invoice.PaymentType.SPONSORSHIP,
        sponsor_payment=payment,
        buyer_name=agreement.sponsor_account.name,
        buyer_email=(
            agreement.sponsor_account.owner.email
            if agreement.sponsor_account.owner
            else ""
        ),
        amount=payment.amount_paid,
        currency=payment.currency,
        status=(
            Invoice.Status.PAID
            if payment.status in ("CONFIRMED",)
            else Invoice.Status.ISSUED
        ),
        issue_date=timezone.now(),
        paid_date=payment.paid_at,
        created_by=created_by,
    )

    log_finance_action(
        club=club,
        actor=created_by,
        action=FinanceAuditLog.Action.INVOICE_CREATED,
        target_type="Invoice",
        target_id=invoice.id,
        target_repr=str(invoice),
        description=f"Invoice {invoice.invoice_number} created for sponsor payment {payment.transaction_reference}",
        ip_address=ip_address,
    )

    return invoice


@transaction.atomic
def generate_receipt(invoice, created_by=None, ip_address=""):
    """
    Generate a receipt from an invoice.
    """
    receipt = Receipt.objects.create(
        club=invoice.club,
        payment_type=invoice.payment_type,
        invoice=invoice,
        membership_payment=invoice.membership_payment,
        ticket_order=invoice.ticket_order,
        sponsor_payment=invoice.sponsor_payment,
        member=invoice.member,
        buyer_name=invoice.buyer_name,
        buyer_email=invoice.buyer_email,
        amount=invoice.amount,
        tax_amount=invoice.tax_amount,
        currency=invoice.currency,
        payment_method="",
        transaction_reference="",
        issue_date=timezone.now(),
        payment_date=invoice.paid_date,
        created_by=created_by,
    )

    log_finance_action(
        club=invoice.club,
        actor=created_by,
        action=FinanceAuditLog.Action.RECEIPT_GENERATED,
        target_type="Receipt",
        target_id=receipt.id,
        target_repr=str(receipt),
        description=f"Receipt {receipt.receipt_number} generated for invoice {invoice.invoice_number}",
        ip_address=ip_address,
    )

    return receipt


# ---------------------------------------------------------------------------
# Financial Summary Calculation
# ---------------------------------------------------------------------------


def get_financial_summary(club_id, start_date=None, end_date=None):
    """
    Calculate financial summary for a club within an optional date range.
    Returns a dict with membership_income, ticketing_income, sponsorship_income,
    other_income, club_expenses, total_income, total_expenses, net_balance.
    """

    # Base filters
    membership_filter = Q(
        subscription__club_id=club_id, status=MembershipPayment.Status.CONFIRMED
    )
    ticket_filter = Q(status=TicketOrder.Status.PAID)
    sponsor_filter = Q(
        agreement__sponsor_package__owner_type="CLUB", status="CONFIRMED"
    )

    # Apply date range filters
    if start_date:
        membership_filter &= Q(paid_at__gte=start_date)
        ticket_filter &= Q(paid_at__gte=start_date)
        sponsor_filter &= Q(paid_at__gte=start_date)
    if end_date:
        membership_filter &= Q(paid_at__lte=end_date)
        ticket_filter &= Q(paid_at__lte=end_date)
        sponsor_filter &= Q(paid_at__lte=end_date)

    # Membership income
    membership_agg = MembershipPayment.objects.filter(membership_filter).aggregate(
        total=Sum("amount_paid")
    )
    membership_income = membership_agg["total"] or Decimal("0")

    # Ticketing income - need to filter by match home_club
    ticket_agg = TicketOrder.objects.filter(ticket_filter).aggregate(
        total=Sum("total_amount")
    )
    ticketing_income = ticket_agg["total"] or Decimal("0")

    # Sponsorship income
    sponsor_agg = SponsorPayment.objects.filter(sponsor_filter).aggregate(
        total=Sum("amount_paid")
    )
    sponsorship_income = sponsor_agg["total"] or Decimal("0")

    total_income = membership_income + ticketing_income + sponsorship_income

    # Club expenses - placeholder for future expense model
    club_expenses = Decimal("0")

    total_expenses = club_expenses
    net_balance = total_income - total_expenses

    return {
        "membership_income": membership_income,
        "ticketing_income": ticketing_income,
        "sponsorship_income": sponsorship_income,
        "other_income": Decimal("0"),
        "club_expenses": club_expenses,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_balance": net_balance,
    }
