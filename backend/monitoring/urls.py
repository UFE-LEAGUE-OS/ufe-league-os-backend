from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"approvals", views.ApprovalLogViewSet, basename="approval-log")
router.register(
    r"chargebacks", views.ChargebackRefundViewSet, basename="chargeback-refund"
)
router.register(r"anomalies", views.AnomalyViewSet, basename="anomaly")
router.register(r"payments", views.PaymentAuditViewSet, basename="payment-audit")
router.register(
    r"transactions",
    views.TransactionReconciliationViewSet,
    basename="transaction-reconciliation",
)
router.register(r"system-logs", views.SystemLogViewSet, basename="system-log")
router.register(
    r"compliance", views.ComplianceTrailViewSet, basename="compliance-trail"
)
router.register(
    r"data-access", views.DataAccessAuditViewSet, basename="data-access-audit"
)
router.register(
    r"security-events", views.SecurityEventViewSet, basename="security-event"
)

urlpatterns = [
    path("", include(router.urls)),
]
