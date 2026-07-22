"""
URL configuration for the League OS backend API.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from accounts import finance_audit_views
from config.views import (
    api_landing_view,
    landing_page_view,
    global_flutterwave_webhook_view,
)


def health_check_view(request):
    return JsonResponse(
        {
            "status": "OK",
            "service": "League OS Backend API",
            "version": "sprint-1-foundation",
        }
    )


urlpatterns = [
    path("", landing_page_view, name="landing-page"),
    path("admin/", admin.site.urls),
    path("api/", api_landing_view, name="api-landing"),
    path("api/health/", health_check_view, name="health-check"),
    path(
        "webhook/flutterwave",
        global_flutterwave_webhook_view,
        name="global-flutterwave-webhook-no-slash",
    ),
    path(
        "webhook/flutterwave/",
        global_flutterwave_webhook_view,
        name="global-flutterwave-webhook",
    ),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/accounts/", include("accounts.urls")),
    path("api/dashboards/", include("dashboards.urls")),
    path("api/governance/", include("governance.urls")),
    path("api/sponsorships/", include("sponsorships.urls")),
    path("api/memberships/", include("memberships.urls")),
    path("api/teams/", include("teams.urls")),
    path("api/ticketing/", include("ticketing.urls")),
    path("api/fantasy/", include("fantasy.urls")),
    path(
        "api/clubs/<int:club_id>/finance/overview/",
        finance_audit_views.finance_overview_view,
        name="club-finance-overview",
    ),
    path(
        "api/clubs/<int:club_id>/finance/membership-payments/",
        finance_audit_views.membership_payments_overview_view,
        name="club-finance-membership-payments",
    ),
    path(
        "api/clubs/<int:club_id>/finance/membership-payments/export/",
        finance_audit_views.membership_payments_export_view,
        name="club-finance-membership-payments-export",
    ),
    path(
        "api/clubs/<int:club_id>/finance/ticketing-payments/",
        finance_audit_views.ticketing_payments_overview_view,
        name="club-finance-ticketing-payments",
    ),
    path(
        "api/clubs/<int:club_id>/finance/ticketing-payments/export/",
        finance_audit_views.ticketing_payments_export_view,
        name="club-finance-ticketing-payments-export",
    ),
    path(
        "api/clubs/<int:club_id>/finance/income-expense/",
        finance_audit_views.income_expense_view,
        name="club-finance-income-expense",
    ),
    path(
        "api/clubs/<int:club_id>/finance/invoices/",
        finance_audit_views.invoices_view,
        name="club-finance-invoices",
    ),
    path(
        "api/clubs/<int:club_id>/finance/invoices/<str:invoice_id>/send-receipt/",
        finance_audit_views.send_invoice_receipt_view,
        name="club-finance-send-receipt",
    ),
    path(
        "api/clubs/<int:club_id>/finance/audit-trail/",
        finance_audit_views.audit_trail_view,
        name="club-finance-audit-trail",
    ),
    path("api/engagements/", include("engagements.urls")),
    path("api/monitoring/", include("monitoring.urls")),
    path("api/platform-admin/", include("platform_admin.urls")),
    path("api/rbac/", include("rbac.urls")),
    path("api/analytics/", include("analytics.urls")),
    path("api/club/", include("club_operations.urls")),
    path("api/finances/", include("finances.urls")),
]

if settings.DEBUG and not getattr(settings, "USE_S3_MEDIA", False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)