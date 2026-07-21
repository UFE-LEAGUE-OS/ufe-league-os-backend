from decimal import Decimal
from datetime import datetime

from django.db.models import Sum, Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import Club
from memberships.models import MembershipPayment
from ticketing.models import TicketOrder, TicketOrderItem

from .filters import InvoiceFilter, FinanceAuditLogFilter
from .models import Invoice, Receipt, FinanceAuditLog
from .permissions import CanAccessClubFinance, IsFinanceAuditor
from .serializers import (
    InvoiceSerializer,
    InvoiceListSerializer,
    ReceiptSerializer,
    ReceiptListSerializer,
    FinanceAuditLogSerializer,
    MembershipPaymentReportSerializer,
    MembershipPaymentSummarySerializer,
    TicketingPaymentReportSerializer,
    TicketingPaymentSummarySerializer,
    FinancialSummarySerializer,
)
from .services import (
    log_finance_action,
    get_financial_summary,
)


def _get_user_club_id(user):
    """Get the club ID the user belongs to, or None for super admins."""
    if user.role == "SUPER_ADMIN":
        return None

    club = getattr(user, "club", None)
    if club:
        return club.id

    # Check via club admin scopes
    scope = user.club_admin_scopes.filter(is_active=True).first()
    if scope:
        return scope.club_id

    return None


def _get_club_ids_for_user(user):
    """
    Return all club IDs the user has access to.
    For SUPER_ADMIN: all clubs.
    For CLUB_ADMIN / scope: their assigned clubs.
    """
    if user.role == "SUPER_ADMIN":
        return list(Club.objects.values_list("id", flat=True))

    club_ids = set()

    club = getattr(user, "club", None)
    if club:
        club_ids.add(club.id)

    scope_clubs = user.club_admin_scopes.filter(is_active=True).values_list(
        "club_id", flat=True
    )
    club_ids.update(scope_clubs)

    return list(club_ids)


class MembershipPaymentReportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/finances/membership-payments/
    Returns membership payments report for a club.

    Supports:
    - Pagination
    - Search by member name
    - Filter by payment status
    - Filter by membership type (plan tier)
    - Filter by date range (date_from, date_to)
    - Ordering by payment date and amount
    - Summary statistics via /summary/ endpoint
    """

    serializer_class = MembershipPaymentReportSerializer
    permission_classes = [IsAuthenticated, CanAccessClubFinance]
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        user = self.request.user
        club_id = self.request.query_params.get("club")

        # Resolve club
        if club_id:
            resolved_club_id = club_id
        elif user.role == "SUPER_ADMIN":
            resolved_club_id = None
        else:
            resolved_club_id = _get_user_club_id(user)

        queryset = MembershipPayment.objects.select_related(
            "subscription__user",
            "subscription__plan",
            "subscription__club",
            "subscription_plan",
        )

        if resolved_club_id:
            queryset = queryset.filter(subscription__club_id=resolved_club_id)
        elif user.role != "SUPER_ADMIN":
            club_ids = _get_club_ids_for_user(user)
            queryset = queryset.filter(subscription__club_id__in=club_ids)

        # Filters
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        tier_filter = self.request.query_params.get("tier")
        if tier_filter:
            queryset = queryset.filter(subscription_plan__tier=tier_filter)

        membership_type = self.request.query_params.get("membership_type")
        if membership_type:
            queryset = queryset.filter(
                subscription_plan__name__icontains=membership_type
            )

        date_from = self.request.query_params.get("date_from")
        if date_from:
            try:
                dt = datetime.fromisoformat(date_from)
                queryset = queryset.filter(paid_at__gte=dt)
            except (ValueError, TypeError):
                pass

        date_to = self.request.query_params.get("date_to")
        if date_to:
            try:
                dt = datetime.fromisoformat(date_to)
                queryset = queryset.filter(paid_at__lte=dt)
            except (ValueError, TypeError):
                pass

        # Search
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(subscription__user__first_name__icontains=search)
                | Q(subscription__user__last_name__icontains=search)
                | Q(subscription__user__email__icontains=search)
            )

        # Ordering
        ordering = self.request.query_params.get("ordering", "-created_at")
        allowed_orderings = [
            "paid_at",
            "-paid_at",
            "amount_paid",
            "-amount_paid",
            "created_at",
            "-created_at",
        ]
        if ordering in allowed_orderings:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by("-created_at")

        return queryset

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Return summary statistics for membership payments."""
        queryset = self.get_queryset()

        agg = queryset.aggregate(
            total_payments=Count("id"),
            total_revenue=Sum("amount_paid"),
            paid_count=Count("id", filter=Q(status=MembershipPayment.Status.CONFIRMED)),
            pending_count=Count(
                "id", filter=Q(status=MembershipPayment.Status.PENDING)
            ),
            failed_count=Count("id", filter=Q(status=MembershipPayment.Status.FAILED)),
        )

        summary_data = {
            "total_payments": agg["total_payments"] or 0,
            "total_revenue": agg["total_revenue"] or Decimal("0"),
            "paid_count": agg["paid_count"] or 0,
            "pending_count": agg["pending_count"] or 0,
            "failed_count": agg["failed_count"] or 0,
        }

        # Log audit
        user = request.user
        club_id = request.query_params.get("club") or _get_user_club_id(user)
        if club_id:
            try:
                club = Club.objects.get(id=club_id)
                log_finance_action(
                    club=club,
                    actor=request.user,
                    action=FinanceAuditLog.Action.REPORT_VIEWED,
                    target_type="MembershipPaymentReport",
                    target_repr=f"Membership payments summary for club {club.name}",
                    description="Membership payment summary report viewed",
                    ip_address=self._get_client_ip(request),
                )
            except Club.DoesNotExist:
                pass

        serializer = MembershipPaymentSummarySerializer(summary_data)
        return Response(serializer.data)

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")


class TicketingPaymentReportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/finances/ticketing-payments/
    Returns ticket sales and payment reports for a club.

    Supports:
    - Pagination
    - Match filtering
    - Ticket category filtering
    - Date range filtering
    - Payment status filtering
    - Summary statistics via /summary/ endpoint
    """

    serializer_class = TicketingPaymentReportSerializer
    permission_classes = [IsAuthenticated, CanAccessClubFinance]
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        user = self.request.user
        club_id = self.request.query_params.get("club")

        queryset = TicketOrder.objects.select_related(
            "buyer",
        ).prefetch_related(
            "items__ticket_type__match__home_club",
            "items__ticket_type__match__away_club",
        )

        # For non-super-admin, restrict by club through matches
        if club_id:
            queryset = queryset.filter(
                items__ticket_type__match__home_club_id=club_id
            ).distinct()
        elif user.role != "SUPER_ADMIN":
            club_ids = _get_club_ids_for_user(user)
            queryset = queryset.filter(
                items__ticket_type__match__home_club_id__in=club_ids
            ).distinct()
        else:
            queryset = queryset.distinct()

        # Filters
        match_id = self.request.query_params.get("match")
        if match_id:
            queryset = queryset.filter(items__ticket_type__match_id=match_id)

        ticket_category = self.request.query_params.get("ticket_category")
        if ticket_category:
            queryset = queryset.filter(
                items__ticket_type__name__icontains=ticket_category
            )

        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        date_from = self.request.query_params.get("date_from")
        if date_from:
            try:
                dt = datetime.fromisoformat(date_from)
                queryset = queryset.filter(paid_at__gte=dt)
            except (ValueError, TypeError):
                pass

        date_to = self.request.query_params.get("date_to")
        if date_to:
            try:
                dt = datetime.fromisoformat(date_to)
                queryset = queryset.filter(paid_at__lte=dt)
            except (ValueError, TypeError):
                pass

        return queryset.order_by("-created_at")

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Return summary statistics for ticketing payments."""
        queryset = self.get_queryset()

        # Aggregate
        agg = queryset.aggregate(
            total_amount=Sum("total_amount"),
            count=Count("id"),
        )
        total_revenue = agg["total_amount"] or Decimal("0")

        # Tickets sold across items
        items_qs = TicketOrderItem.objects.filter(
            order__in=queryset.values("id")
        ).aggregate(
            total_tickets=Sum("quantity"),
        )
        tickets_sold = items_qs["total_tickets"] or 0

        # Successful/failed payments
        successful = queryset.filter(status=TicketOrder.Status.PAID).count()
        failed = queryset.filter(
            status__in=[TicketOrder.Status.FAILED, TicketOrder.Status.CANCELLED]
        ).count()

        avg_value = (
            (total_revenue / tickets_sold).quantize(Decimal("0.01"))
            if tickets_sold > 0
            else Decimal("0")
        )

        summary_data = {
            "tickets_sold": tickets_sold,
            "gross_revenue": total_revenue,
            "average_ticket_value": avg_value,
            "successful_payments": successful,
            "failed_payments": failed,
        }

        # Log audit
        user = request.user
        club_id = request.query_params.get("club") or _get_user_club_id(user)
        if club_id:
            try:
                club = Club.objects.get(id=club_id)
                log_finance_action(
                    club=club,
                    actor=request.user,
                    action=FinanceAuditLog.Action.REPORT_VIEWED,
                    target_type="TicketingPaymentReport",
                    target_repr=f"Ticketing payments summary for club {club.name}",
                    description="Ticketing payment summary report viewed",
                    ip_address=self._get_client_ip(request),
                )
            except Club.DoesNotExist:
                pass

        serializer = TicketingPaymentSummarySerializer(summary_data)
        return Response(serializer.data)

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")


class FinancialSummaryViewSet(viewsets.ViewSet):
    """
    GET /api/finances/summary/
    Returns financial summary for a club.

    Supports:
    - Monthly (period=monthly)
    - Quarterly (period=quarterly)
    - Yearly (period=yearly)
    - Custom date range (date_from, date_to)
    """

    permission_classes = [IsAuthenticated, CanAccessClubFinance]

    def list(self, request):
        user = request.user
        club_id = request.query_params.get("club")

        if not club_id:
            club_id = _get_user_club_id(user)

        if not club_id:
            return Response(
                {"detail": "club query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Determine date range
        period = request.query_params.get("period", "all")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        now = timezone.now()

        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from)
            except (ValueError, TypeError):
                dt_from = None
        else:
            dt_from = None

        if date_to:
            try:
                dt_to = datetime.fromisoformat(date_to)
            except (ValueError, TypeError):
                dt_to = None
        else:
            dt_to = None

        if not dt_from and not dt_to:
            if period == "monthly":
                dt_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                dt_to = now
            elif period == "quarterly":
                quarter_month = ((now.month - 1) // 3) * 3 + 1
                dt_from = now.replace(
                    month=quarter_month,
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                dt_to = now
            elif period == "yearly":
                dt_from = now.replace(
                    month=1, day=1, hour=0, minute=0, second=0, microsecond=0
                )
                dt_to = now

        summary = get_financial_summary(
            club_id=club_id,
            start_date=dt_from,
            end_date=dt_to,
        )

        # Log audit
        try:
            club = Club.objects.get(id=club_id)
            log_finance_action(
                club=club,
                actor=request.user,
                action=FinanceAuditLog.Action.REPORT_VIEWED,
                target_type="FinancialSummary",
                target_repr=f"Financial summary for {club.name} ({period})",
                description=f"Financial summary report viewed for period: {period}",
                ip_address=self._get_client_ip(request),
            )
        except Club.DoesNotExist:
            pass

        serializer = FinancialSummarySerializer(summary)
        return Response(serializer.data)

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")


class InvoiceViewSet(viewsets.ModelViewSet):
    """
    CRUD API for invoices.

    GET /api/finances/invoices/ - List invoices
    GET /api/finances/invoices/{id}/ - Retrieve invoice
    POST /api/finances/invoices/ - Create invoice
    PATCH /api/finances/invoices/{id}/ - Update invoice
    DELETE /api/finances/invoices/{id}/ - Delete invoice
    """

    permission_classes = [IsAuthenticated, CanAccessClubFinance]
    filter_backends = [DjangoFilterBackend]
    filterset_class = InvoiceFilter

    def get_serializer_class(self):
        if self.action == "list":
            return InvoiceListSerializer
        return InvoiceSerializer

    def get_queryset(self):
        user = self.request.user
        club_id = self.request.query_params.get("club")

        queryset = Invoice.objects.select_related("club", "member", "created_by")

        if club_id:
            return queryset.filter(club_id=club_id)
        elif user.role == "SUPER_ADMIN":
            return queryset
        else:
            club_ids = _get_club_ids_for_user(user)
            return queryset.filter(club_id__in=club_ids)

    def perform_create(self, serializer):
        invoice = serializer.save(created_by=self.request.user)
        log_finance_action(
            club=invoice.club,
            actor=self.request.user,
            action=FinanceAuditLog.Action.INVOICE_CREATED,
            target_type="Invoice",
            target_id=invoice.id,
            target_repr=str(invoice),
            description=f"Invoice {invoice.invoice_number} created via API",
            ip_address=self._get_client_ip(self.request),
        )

    def perform_update(self, serializer):
        invoice = serializer.save()
        log_finance_action(
            club=invoice.club,
            actor=self.request.user,
            action=FinanceAuditLog.Action.INVOICE_UPDATED,
            target_type="Invoice",
            target_id=invoice.id,
            target_repr=str(invoice),
            description=f"Invoice {invoice.invoice_number} updated via API",
            ip_address=self._get_client_ip(self.request),
        )

    @action(detail=True, methods=["post"])
    def generate_receipt(self, request, pk=None):
        """Generate a receipt for an invoice."""
        invoice = self.get_object()

        if invoice.status not in (Invoice.Status.PAID, Invoice.Status.ISSUED):
            return Response(
                {
                    "detail": "Receipt can only be generated for paid or issued invoices."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if receipt already exists
        if invoice.receipts.exists():
            receipt = invoice.receipts.first()
            return Response(
                {
                    "message": "Receipt already exists.",
                    "receipt": ReceiptSerializer(
                        receipt, context={"request": request}
                    ).data,
                },
                status=status.HTTP_200_OK,
            )

        from .services import generate_receipt as gen_receipt

        receipt = gen_receipt(
            invoice,
            created_by=request.user,
            ip_address=self._get_client_ip(request),
        )

        return Response(
            {
                "message": "Receipt generated successfully.",
                "receipt": ReceiptSerializer(
                    receipt, context={"request": request}
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")


class ReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for receipts.

    GET /api/finances/receipts/ - List receipts
    GET /api/finances/receipts/{id}/ - Retrieve receipt
    """

    permission_classes = [IsAuthenticated, CanAccessClubFinance]

    def get_serializer_class(self):
        if self.action == "list":
            return ReceiptListSerializer
        return ReceiptSerializer

    def get_queryset(self):
        user = self.request.user
        club_id = self.request.query_params.get("club")

        queryset = Receipt.objects.select_related(
            "club", "member", "invoice", "created_by"
        )

        if club_id:
            return queryset.filter(club_id=club_id)
        elif user.role == "SUPER_ADMIN":
            return queryset
        else:
            club_ids = _get_club_ids_for_user(user)
            return queryset.filter(club_id__in=club_ids)


class FinanceAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for finance audit logs.

    GET /api/finances/audit-logs/ - List audit logs
    GET /api/finances/audit-logs/{id}/ - Retrieve audit log

    Supports:
    - Pagination
    - Search
    - Filter by user (actor_id)
    - Filter by action
    - Filter by date (date_from, date_to)
    """

    serializer_class = FinanceAuditLogSerializer
    permission_classes = [IsAuthenticated, IsFinanceAuditor]
    filter_backends = [DjangoFilterBackend]
    filterset_class = FinanceAuditLogFilter

    def get_queryset(self):
        user = self.request.user
        club_id = self.request.query_params.get("club")

        queryset = FinanceAuditLog.objects.select_related("club", "actor")

        if club_id:
            return queryset.filter(club_id=club_id)
        elif user.role == "SUPER_ADMIN":
            return queryset
        else:
            club_ids = _get_club_ids_for_user(user)
            return queryset.filter(club_id__in=club_ids)
