from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    MembershipPaymentReportViewSet,
    TicketingPaymentReportViewSet,
    FinancialSummaryViewSet,
    InvoiceViewSet,
    ReceiptViewSet,
    FinanceAuditLogViewSet,
)

router = DefaultRouter()
router.register(
    r"membership-payments",
    MembershipPaymentReportViewSet,
    basename="membership-payment-report",
)
router.register(
    r"ticketing-payments",
    TicketingPaymentReportViewSet,
    basename="ticketing-payment-report",
)
router.register(
    r"summary",
    FinancialSummaryViewSet,
    basename="financial-summary",
)
router.register(
    r"invoices",
    InvoiceViewSet,
    basename="invoice",
)
router.register(
    r"receipts",
    ReceiptViewSet,
    basename="receipt",
)
router.register(
    r"audit-logs",
    FinanceAuditLogViewSet,
    basename="finance-audit-log",
)

urlpatterns = [
    path("", include(router.urls)),
]
