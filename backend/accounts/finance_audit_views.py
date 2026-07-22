import csv
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Prefetch, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import AuditLog, Club, User
from accounts.permissions import IsAuthenticatedAudit
from dashboards.models import Match
from memberships.models import (
    MembershipPayment,
    MembershipPlan,
    MembershipSubscription,
)
from ticketing.models import TicketOrder, TicketOrderItem, TicketType


STAT_ACCENTS = ["#7c5cff", "#22c55e", "#38bdf8", "#f59e0b", "#ef4444", "#14b8a6"]
SLICE_COLORS = ["#7c5cff", "#22c55e", "#38bdf8", "#f59e0b", "#ef4444", "#14b8a6"]


def _money(value):
    return float(value or 0)


def _format_ugx(value):
    return f"UGX {int(round(_money(value))):,}"


def _stat(key, label, value, index=0, footer_value="0%", caption="vs prior period"):
    direction = "up"
    if isinstance(footer_value, str) and footer_value.strip().startswith("-"):
        direction = "down"

    return {
        "key": key,
        "label": label,
        "value": value,
        "accent": STAT_ACCENTS[index % len(STAT_ACCENTS)],
        "sparkline": [],
        "footer": {
            "kind": "trend",
            "direction": direction,
            "value": footer_value,
            "caption": caption,
        },
    }


def _can_access_club_finance(user, club):
    if user.is_staff or user.role == User.Role.SUPER_ADMIN:
        return True

    if user.role in {User.Role.CLUB_ADMIN, User.Role.TICKETING_OFFICER}:
        return user.club_id == club.id or club.admin_id == user.id

    return False


def _get_club_or_response(request, club_id):
    club = Club.objects.filter(id=club_id).first()
    if club is None:
        return None, Response(
            {"detail": "Club not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _can_access_club_finance(request.user, club):
        return None, Response(
            {"detail": "You do not have permission to view this club's finance data."},
            status=status.HTTP_403_FORBIDDEN,
        )

    return club, None


def _parse_date(value):
    if not value:
        return None
    try:
        return timezone.datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _apply_date_filters(queryset, request, field):
    start_date = _parse_date(request.query_params.get("start_date"))
    end_date = _parse_date(request.query_params.get("end_date"))

    if start_date:
        queryset = queryset.filter(**{f"{field}__date__gte": start_date})
    if end_date:
        queryset = queryset.filter(**{f"{field}__date__lte": end_date})

    return queryset


def _membership_status(value):
    return {
        MembershipPayment.Status.CONFIRMED: "COMPLETED",
        MembershipPayment.Status.PENDING: "PENDING",
        MembershipPayment.Status.FAILED: "FAILED",
        MembershipPayment.Status.CANCELLED: "FAILED",
        MembershipPayment.Status.REFUNDED: "REFUNDED",
    }.get(value, value)


def _ticket_status(value):
    return {
        TicketOrder.Status.PAID: "COMPLETED",
        TicketOrder.Status.PENDING: "PENDING",
        TicketOrder.Status.FAILED: "FAILED",
        TicketOrder.Status.CANCELLED: "FAILED",
        TicketOrder.Status.REFUNDED: "REFUNDED",
    }.get(value, value)


def _payment_timestamp(payment):
    return payment.paid_at or payment.created_at


def _order_timestamp(order):
    return order.paid_at or order.created_at


def _month_key(dt):
    return timezone.localtime(dt).strftime("%b") if dt else ""


def _date_key(dt):
    return timezone.localtime(dt).date().isoformat() if dt else ""


def _trend_by_day(records, amount_getter, date_getter):
    totals = defaultdict(float)
    for record in records:
        dt = date_getter(record)
        if dt:
            totals[_date_key(dt)] += _money(amount_getter(record))
    return [{"date": date, "amount": amount} for date, amount in sorted(totals.items())]


def _trend_by_month(records, amount_getter, date_getter):
    totals = defaultdict(float)
    for record in records:
        dt = date_getter(record)
        if dt:
            totals[_month_key(dt)] += _money(amount_getter(record))
    return [{"month": month, "amount": amount} for month, amount in totals.items()]


def _membership_payments_queryset(club_id, request):
    queryset = MembershipPayment.objects.select_related(
        "subscription",
        "subscription__user",
        "subscription_plan",
    ).filter(subscription__club_id=club_id)
    queryset = _apply_date_filters(queryset, request, "created_at")

    plan = request.query_params.get("plan")
    if plan and plan != "ALL":
        queryset = queryset.filter(subscription_plan__name=plan)

    method = request.query_params.get("payment_method")
    if method and method != "ALL":
        method_by_label = {label: value for value, label in MembershipPayment.PaymentMethod.choices}
        queryset = queryset.filter(payment_method=method_by_label.get(method, method))

    status_filter = request.query_params.get("status")
    if status_filter and status_filter != "ALL":
        reverse_status = {
            "COMPLETED": MembershipPayment.Status.CONFIRMED,
            "PENDING": MembershipPayment.Status.PENDING,
            "FAILED": MembershipPayment.Status.FAILED,
            "REFUNDED": MembershipPayment.Status.REFUNDED,
        }.get(status_filter)
        if reverse_status:
            queryset = queryset.filter(status=reverse_status)

    search = request.query_params.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(subscription__user__email__icontains=search)
            | Q(subscription__user__first_name__icontains=search)
            | Q(subscription__user__last_name__icontains=search)
            | Q(subscription_plan__name__icontains=search)
            | Q(transaction_reference__icontains=search)
            | Q(provider_transaction_id__icontains=search)
        )

    return queryset


def _ticket_orders_queryset(club_id, request):
    club_matches = Match.objects.filter(Q(home_club_id=club_id) | Q(away_club_id=club_id))
    queryset = (
        TicketOrder.objects.select_related("buyer")
        .prefetch_related(
            Prefetch(
                "items",
                queryset=TicketOrderItem.objects.select_related(
                    "ticket_type",
                    "ticket_type__match",
                    "ticket_type__match__home_club",
                    "ticket_type__match__away_club",
                ),
            )
        )
        .filter(items__ticket_type__match__in=club_matches)
        .distinct()
    )
    queryset = _apply_date_filters(queryset, request, "created_at")

    match_id = request.query_params.get("match_id")
    if match_id:
        queryset = queryset.filter(items__ticket_type__match_id=match_id)

    method = request.query_params.get("payment_method")
    if method and method != "ALL":
        method_by_label = {label: value for value, label in TicketOrder.PaymentProvider.choices}
        queryset = queryset.filter(provider=method_by_label.get(method, method))

    status_filter = request.query_params.get("status")
    if status_filter and status_filter != "ALL":
        reverse_status = {
            "COMPLETED": TicketOrder.Status.PAID,
            "PENDING": TicketOrder.Status.PENDING,
            "FAILED": TicketOrder.Status.FAILED,
            "REFUNDED": TicketOrder.Status.REFUNDED,
        }.get(status_filter)
        if reverse_status:
            queryset = queryset.filter(status=reverse_status)

    search = request.query_params.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(buyer__email__icontains=search)
            | Q(buyer__first_name__icontains=search)
            | Q(buyer__last_name__icontains=search)
            | Q(payment_reference__icontains=search)
            | Q(provider_transaction_id__icontains=search)
            | Q(items__ticket_type__match__home_club__name__icontains=search)
            | Q(items__ticket_type__match__away_club__name__icontains=search)
        ).distinct()

    return queryset


def _full_name(user):
    name = getattr(user, "full_name", "") or ""
    return name or getattr(user, "email", "")


def _match_label(match):
    return f"{match.home_club.name} vs {match.away_club.name}"


def _ticket_order_match(order):
    first_item = next(iter(order.items.all()), None)
    if not first_item:
        return None
    return first_item.ticket_type.match


def _ticket_order_quantity(order):
    return sum(item.quantity for item in order.items.all())


def _percentage(current, previous):
    if not previous:
        return "0%"
    return f"{((current - previous) / previous) * 100:.1f}%"


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def finance_overview_view(request, club_id):
    club, error_response = _get_club_or_response(request, club_id)
    if error_response:
        return error_response

    membership_payments = _membership_payments_queryset(club.id, request)
    ticket_orders = _ticket_orders_queryset(club.id, request)

    membership_total = membership_payments.filter(
        status=MembershipPayment.Status.CONFIRMED
    ).aggregate(total=Sum("amount_paid"))["total"] or Decimal("0")
    ticket_total = ticket_orders.filter(status=TicketOrder.Status.PAID).aggregate(
        total=Sum("total_amount")
    )["total"] or Decimal("0")
    pending_total = membership_payments.filter(
        status=MembershipPayment.Status.PENDING
    ).aggregate(total=Sum("amount_paid"))["total"] or Decimal("0")
    pending_total += ticket_orders.filter(status=TicketOrder.Status.PENDING).aggregate(
        total=Sum("total_amount")
    )["total"] or Decimal("0")

    stats = [
        _stat("membershipRevenue", "Membership Revenue", _format_ugx(membership_total), 0),
        _stat("ticketingRevenue", "Ticketing Revenue", _format_ugx(ticket_total), 1),
        _stat("pendingPayments", "Pending Payments", _format_ugx(pending_total), 2),
        _stat(
            "auditEvents",
            "Audit Events",
            str(AuditLog.objects.count()),
            3,
            footer_value="Live",
            caption="activity log",
        ),
    ]
    return Response({"stats": stats})


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def membership_payments_overview_view(request, club_id):
    club, error_response = _get_club_or_response(request, club_id)
    if error_response:
        return error_response

    payments = list(_membership_payments_queryset(club.id, request)[:200])
    confirmed = [p for p in payments if p.status == MembershipPayment.Status.CONFIRMED]
    pending = [p for p in payments if p.status == MembershipPayment.Status.PENDING]
    refunded = [p for p in payments if p.status == MembershipPayment.Status.REFUNDED]
    total_revenue = sum(_money(p.amount_paid) for p in confirmed)
    active_members = MembershipSubscription.objects.filter(
        club=club,
        status=MembershipSubscription.Status.ACTIVE,
    ).count()
    renewals = len(confirmed)
    expired = MembershipSubscription.objects.filter(
        club=club,
        status=MembershipSubscription.Status.EXPIRED,
    ).count()

    plan_totals = defaultdict(lambda: {"amount": 0.0, "members": set()})
    for payment in confirmed:
        plan_name = payment.subscription_plan.name if payment.subscription_plan else "Unassigned"
        plan_totals[plan_name]["amount"] += _money(payment.amount_paid)
        plan_totals[plan_name]["members"].add(payment.subscription.user_id)
    plan_total_amount = sum(value["amount"] for value in plan_totals.values()) or 1

    return Response(
        {
            "stats": {
                "totalRevenue": _stat("totalRevenue", "Total Revenue", _format_ugx(total_revenue), 0),
                "activeMembers": _stat("activeMembers", "Active Members", str(active_members), 1),
                "renewals": _stat("renewals", "Renewals", str(renewals), 2),
                "expiredMemberships": _stat("expiredMemberships", "Expired Memberships", str(expired), 3),
                "refunds": _stat("refunds", "Refunds", _format_ugx(sum(_money(p.amount_paid) for p in refunded)), 4),
            },
            "summary": {
                "totalCollected": total_revenue,
                "successfulPayments": len(confirmed),
                "pendingPayments": len(pending),
                "refunded": sum(_money(p.amount_paid) for p in refunded),
            },
            "revenueTrend": _trend_by_day(confirmed, lambda p: p.amount_paid, _payment_timestamp),
            "monthlyRevenue": _trend_by_month(confirmed, lambda p: p.amount_paid, _payment_timestamp),
            "planBreakdown": [
                {
                    "plan": plan,
                    "amount": value["amount"],
                    "memberCount": len(value["members"]),
                    "share": value["amount"] / plan_total_amount,
                    "color": SLICE_COLORS[index % len(SLICE_COLORS)],
                }
                for index, (plan, value) in enumerate(plan_totals.items())
            ],
            "payments": [
                {
                    "id": str(payment.id),
                    "memberName": _full_name(payment.subscription.user),
                    "memberRef": payment.subscription.user.email,
                    "plan": payment.subscription_plan.name if payment.subscription_plan else "Unassigned",
                    "amount": _money(payment.amount_paid),
                    "method": payment.get_payment_method_display(),
                    "transactionId": payment.transaction_reference or payment.provider_transaction_id or f"MEM-{payment.id}",
                    "status": _membership_status(payment.status),
                    "paidAt": _payment_timestamp(payment).isoformat(),
                }
                for payment in payments
            ],
            "availablePlans": list(
                MembershipPlan.objects.filter(club=club).values_list("name", flat=True)
            ),
            "availablePaymentMethods": [choice[1] for choice in MembershipPayment.PaymentMethod.choices],
        }
    )


def _write_csv(filename, headers, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    writer.writerows(rows)
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def membership_payments_export_view(request, club_id):
    club, error_response = _get_club_or_response(request, club_id)
    if error_response:
        return error_response

    rows = []
    for payment in _membership_payments_queryset(club.id, request):
        rows.append(
            [
                payment.id,
                _full_name(payment.subscription.user),
                payment.subscription.user.email,
                payment.subscription_plan.name if payment.subscription_plan else "",
                _money(payment.amount_paid),
                payment.get_payment_method_display(),
                payment.transaction_reference,
                _membership_status(payment.status),
                _payment_timestamp(payment).isoformat(),
            ]
        )
    return _write_csv(
        f"membership-payments-{club.id}.csv",
        ["ID", "Member", "Email", "Plan", "Amount", "Method", "Reference", "Status", "Paid At"],
        rows,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def ticketing_payments_overview_view(request, club_id):
    club, error_response = _get_club_or_response(request, club_id)
    if error_response:
        return error_response

    orders = list(_ticket_orders_queryset(club.id, request)[:200])
    paid = [order for order in orders if order.status == TicketOrder.Status.PAID]
    failed = [order for order in orders if order.status == TicketOrder.Status.FAILED]
    refunded = [order for order in orders if order.status == TicketOrder.Status.REFUNDED]
    total_revenue = sum(_money(order.total_amount) for order in paid)
    tickets_sold = sum(_ticket_order_quantity(order) for order in paid)
    online_total = sum(_money(order.total_amount) for order in paid if order.provider == TicketOrder.PaymentProvider.FLUTTERWAVE)

    method_totals = defaultdict(float)
    revenue_by_match = defaultdict(float)
    for order in paid:
        method_totals[order.get_provider_display()] += _money(order.total_amount)
        match = _ticket_order_match(order)
        if match:
            revenue_by_match[(match.id, _match_label(match))] += _money(order.total_amount)
    method_total_amount = sum(method_totals.values()) or 1
    max_match_revenue = max(revenue_by_match.values(), default=1)

    upcoming_matches = Match.objects.filter(
        Q(home_club=club) | Q(away_club=club),
        status=Match.Status.SCHEDULED,
        match_date__gte=timezone.now(),
    ).order_by("match_date")[:8]

    available_matches = Match.objects.filter(Q(home_club=club) | Q(away_club=club)).order_by("-match_date")

    return Response(
        {
            "stats": {
                "ticketsSold": _stat("ticketsSold", "Tickets Sold", str(tickets_sold), 0),
                "totalRevenue": _stat("totalRevenue", "Total Revenue", _format_ugx(total_revenue), 1),
                "onlinePayments": _stat("onlinePayments", "Online Payments", _format_ugx(online_total), 2),
                "mobileMoney": _stat("mobileMoney", "Mobile Money", _format_ugx(0), 3),
                "failedPayments": _stat("failedPayments", "Failed Payments", str(len(failed)), 4),
                "refundRequests": _stat("refundRequests", "Refund Requests", str(len(refunded)), 5),
            },
            "salesTrend": _trend_by_day(paid, lambda order: order.total_amount, _order_timestamp),
            "paymentMethodBreakdown": [
                {
                    "method": method,
                    "amount": amount,
                    "share": amount / method_total_amount,
                    "color": SLICE_COLORS[index % len(SLICE_COLORS)],
                }
                for index, (method, amount) in enumerate(method_totals.items())
            ],
            "revenueByMatch": [
                {
                    "matchId": match_id,
                    "matchLabel": label,
                    "amount": amount,
                    "share": amount / max_match_revenue,
                }
                for (match_id, label), amount in revenue_by_match.items()
            ],
            "upcomingMatchesRevenue": [
                {
                    "matchId": match.id,
                    "matchLabel": _match_label(match),
                    "matchDate": match.match_date.isoformat(),
                    "expectedRevenue": _money(
                        TicketType.objects.filter(match=match).aggregate(
                            total=Sum("price")
                        )["total"]
                    ),
                    "ticketsSold": TicketType.objects.filter(match=match).aggregate(
                        total=Sum("quantity_sold")
                    )["total"] or 0,
                    "ticketsAvailable": TicketType.objects.filter(match=match).aggregate(
                        total=Sum("quantity_available")
                    )["total"] or 0,
                }
                for match in upcoming_matches
            ],
            "payments": [
                {
                    "id": str(order.id),
                    "buyerName": _full_name(order.buyer),
                    "matchLabel": _match_label(_ticket_order_match(order)) if _ticket_order_match(order) else "Multiple matches",
                    "ticketsCount": _ticket_order_quantity(order),
                    "amount": _money(order.total_amount),
                    "method": order.get_provider_display(),
                    "status": _ticket_status(order.status),
                    "paidAt": _order_timestamp(order).isoformat(),
                }
                for order in orders
            ],
            "availableMatches": [
                {"id": match.id, "label": _match_label(match)}
                for match in available_matches
            ],
            "availablePaymentMethods": [choice[1] for choice in TicketOrder.PaymentProvider.choices],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def ticketing_payments_export_view(request, club_id):
    club, error_response = _get_club_or_response(request, club_id)
    if error_response:
        return error_response

    rows = []
    for order in _ticket_orders_queryset(club.id, request):
        match = _ticket_order_match(order)
        rows.append(
            [
                order.id,
                _full_name(order.buyer),
                order.buyer.email,
                _match_label(match) if match else "",
                _ticket_order_quantity(order),
                _money(order.total_amount),
                order.get_provider_display(),
                order.payment_reference,
                _ticket_status(order.status),
                _order_timestamp(order).isoformat(),
            ]
        )
    return _write_csv(
        f"ticketing-payments-{club.id}.csv",
        ["ID", "Buyer", "Email", "Match", "Tickets", "Amount", "Method", "Reference", "Status", "Paid At"],
        rows,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def income_expense_view(request, club_id):
    club, error_response = _get_club_or_response(request, club_id)
    if error_response:
        return error_response

    memberships = list(_membership_payments_queryset(club.id, request).filter(status=MembershipPayment.Status.CONFIRMED))
    tickets = list(_ticket_orders_queryset(club.id, request).filter(status=TicketOrder.Status.PAID))
    membership_total = sum(_money(payment.amount_paid) for payment in memberships)
    ticket_total = sum(_money(order.total_amount) for order in tickets)
    total_income = membership_total + ticket_total
    total_expenses = Decimal("0")

    month_data = defaultdict(lambda: {"income": 0.0, "expense": 0.0})
    for payment in memberships:
        month_data[_month_key(_payment_timestamp(payment))]["income"] += _money(payment.amount_paid)
    for order in tickets:
        month_data[_month_key(_order_timestamp(order))]["income"] += _money(order.total_amount)

    trend = [
        {"month": month, "income": values["income"], "expense": values["expense"]}
        for month, values in month_data.items()
    ]
    income_sources = [
        {
            "source": "Memberships",
            "amount": membership_total,
            "share": membership_total / total_income if total_income else 0,
            "color": SLICE_COLORS[0],
        },
        {
            "source": "Ticket Sales",
            "amount": ticket_total,
            "share": ticket_total / total_income if total_income else 0,
            "color": SLICE_COLORS[1],
        },
    ]

    return Response(
        {
            "stats": {
                "totalIncome": _stat("totalIncome", "Total Income", _format_ugx(total_income), 0),
                "totalExpenses": _stat("totalExpenses", "Total Expenses", _format_ugx(total_expenses), 1),
                "netProfit": _stat("netProfit", "Net Profit", _format_ugx(total_income - _money(total_expenses)), 2),
                "operatingCosts": _stat("operatingCosts", "Operating Costs", _format_ugx(0), 3),
                "sponsorshipIncome": _stat("sponsorshipIncome", "Sponsorship Income", _format_ugx(0), 4),
                "membershipIncome": _stat("membershipIncome", "Membership Income", _format_ugx(membership_total), 5),
            },
            "incomeVsExpenseTrend": trend,
            "incomeSources": income_sources,
            "totalIncomeSources": total_income,
            "monthlyCashFlow": [
                {
                    "month": row["month"],
                    "cashIn": row["income"],
                    "cashOut": row["expense"],
                    "netCashFlow": row["income"] - row["expense"],
                }
                for row in trend
            ],
            "expenseBreakdown": [],
            "financialSummary": [
                {
                    "month": row["month"],
                    "income": row["income"],
                    "expenses": row["expense"],
                    "netProfit": row["income"] - row["expense"],
                }
                for row in trend
            ],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def invoices_view(request, club_id):
    club, error_response = _get_club_or_response(request, club_id)
    if error_response:
        return error_response

    invoices = []
    for payment in _membership_payments_queryset(club.id, request):
        invoices.append(
            {
                "id": f"membership-{payment.id}",
                "invoiceNumber": payment.transaction_reference or f"MEM-{payment.id}",
                "billedTo": _full_name(payment.subscription.user),
                "amount": _money(payment.amount_paid),
                "status": "PAID" if payment.status == MembershipPayment.Status.CONFIRMED else "OUTSTANDING",
                "issuedAt": payment.created_at.isoformat(),
                "dueAt": (payment.created_at + timedelta(days=30)).isoformat(),
                "receiptUrl": None,
            }
        )

    for order in _ticket_orders_queryset(club.id, request):
        invoices.append(
            {
                "id": f"ticket-{order.id}",
                "invoiceNumber": order.payment_reference or f"TKT-{order.id}",
                "billedTo": _full_name(order.buyer),
                "amount": _money(order.total_amount),
                "status": "PAID" if order.status == TicketOrder.Status.PAID else "OUTSTANDING",
                "issuedAt": order.created_at.isoformat(),
                "dueAt": (order.created_at + timedelta(days=7)).isoformat(),
                "receiptUrl": None,
            }
        )

    status_filter = request.query_params.get("status")
    if status_filter and status_filter != "ALL":
        invoices = [invoice for invoice in invoices if invoice["status"] == status_filter]

    search = request.query_params.get("search", "").strip().lower()
    if search:
        invoices = [
            invoice
            for invoice in invoices
            if search in invoice["invoiceNumber"].lower()
            or search in invoice["billedTo"].lower()
        ]

    outstanding = [invoice for invoice in invoices if invoice["status"] == "OUTSTANDING"]
    return Response(
        {
            "summary": {
                "outstandingTotal": sum(invoice["amount"] for invoice in outstanding),
                "outstandingCount": len(outstanding),
            },
            "invoices": invoices,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedAudit])
def send_invoice_receipt_view(request, club_id, invoice_id):
    club, error_response = _get_club_or_response(request, club_id)
    if error_response:
        return error_response

    return Response({"sent": False, "detail": "Receipt email delivery is not configured for generated finance records yet."})


@api_view(["GET"])
@permission_classes([IsAuthenticatedAudit])
def audit_trail_view(request, club_id):
    club, error_response = _get_club_or_response(request, club_id)
    if error_response:
        return error_response

    queryset = AuditLog.objects.select_related("actor", "target_user").all()
    queryset = _apply_date_filters(queryset, request, "created_at")

    category_filter = request.query_params.get("category")
    if category_filter and category_filter != "ALL":
        queryset = queryset.filter(category=category_filter)

    search = request.query_params.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(actor__email__icontains=search)
            | Q(target_user__email__icontains=search)
            | Q(action__icontains=search)
            | Q(path__icontains=search)
            | Q(ip_address__icontains=search)
        )

    count = queryset.count()
    limit = int(request.query_params.get("limit") or request.query_params.get("page_size") or 10)
    offset = int(request.query_params.get("offset") or 0)
    entries = queryset[offset : offset + limit]

    return Response(
        {
            "count": count,
            "limit": limit,
            "offset": offset,
            "results": [
                {
                    "id": str(entry.id),
                    "actor": {
                        "email": entry.actor.email,
                        "full_name": entry.actor.full_name,
                    }
                    if entry.actor
                    else None,
                    "actor_email": entry.actor.email if entry.actor else "",
                    "action": entry.action,
                    "category": entry.category,
                    "category_display": entry.get_category_display(),
                    "target_user": {
                        "email": entry.target_user.email,
                        "full_name": entry.target_user.full_name,
                    }
                    if entry.target_user
                    else None,
                    "target_user_email": entry.target_user.email if entry.target_user else "",
                    "created_at": entry.created_at.isoformat(),
                    "path": entry.path,
                    "method": entry.method,
                    "status_code": entry.status_code,
                    "ip_address": entry.ip_address,
                    "details": entry.details,
                }
                for entry in entries
            ],
        }
    )
