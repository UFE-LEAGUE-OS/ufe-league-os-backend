from django.urls import path

from . import views

urlpatterns = [
    # Anomaly investigation
    path("anomalies/", views.anomaly_list_create_view, name="anomaly-list-create"),
    path("anomalies/<int:pk>/", views.anomaly_detail_view, name="anomaly-detail"),
    path(
        "anomalies/<int:pk>/resolve/",
        views.anomaly_resolve_view,
        name="anomaly-resolve",
    ),
    # Payments audit
    path("payments/", views.payment_audit_list_view, name="payment-audit-list"),
    path(
        "payments/<int:pk>/",
        views.payment_audit_detail_view,
        name="payment-audit-detail",
    ),
    # Transaction reconciliation
    path(
        "transactions/",
        views.transaction_reconciliation_list_create_view,
        name="transaction-reconciliation-list-create",
    ),
    path(
        "transactions/<int:pk>/",
        views.transaction_reconciliation_detail_view,
        name="transaction-reconciliation-detail",
    ),
    path(
        "transactions/<int:pk>/verify/",
        views.transaction_reconciliation_verify_view,
        name="transaction-reconciliation-verify",
    ),
    # System logs
    path("system-logs/", views.system_log_list_view, name="system-log-list"),
    path(
        "system-logs/<int:pk>/", views.system_log_detail_view, name="system-log-detail"
    ),
    # Compliance trails
    path(
        "compliance/",
        views.compliance_trail_list_create_view,
        name="compliance-trail-list-create",
    ),
    path(
        "compliance/<int:pk>/",
        views.compliance_trail_detail_view,
        name="compliance-trail-detail",
    ),
    # Data access audit
    path(
        "data-access/", views.data_access_audit_list_view, name="data-access-audit-list"
    ),
    path(
        "data-access/<int:pk>/",
        views.data_access_audit_detail_view,
        name="data-access-audit-detail",
    ),
    # Security events
    path(
        "security-events/",
        views.security_event_list_create_view,
        name="security-event-list-create",
    ),
    path(
        "security-events/<int:pk>/",
        views.security_event_detail_view,
        name="security-event-detail",
    ),
    path(
        "security-events/<int:pk>/resolve/",
        views.security_event_resolve_view,
        name="security-event-resolve",
    ),
]
