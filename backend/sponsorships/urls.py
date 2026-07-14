from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from .governance_views import (
    SponsorFrameworkViewSet,
    CampaignVisibilitySettingsViewSet,
    SystemPlacementViewSet,
    BenefitSharingPolicyViewSet,
    SponsorshipInventoryViewSet,
    CampaignPerformanceViewSet,
    SponsorshipApprovalWorkflowViewSet,
    ComplianceAuditViewSet,
)

# Governance router
governance_router = DefaultRouter()
governance_router.register(
    r"frameworks", SponsorFrameworkViewSet, basename="sponsor-framework"
)
governance_router.register(
    r"visibility-settings",
    CampaignVisibilitySettingsViewSet,
    basename="campaign-visibility",
)
governance_router.register(
    r"placements", SystemPlacementViewSet, basename="system-placement"
)
governance_router.register(
    r"benefit-policies", BenefitSharingPolicyViewSet, basename="benefit-policy"
)
governance_router.register(
    r"inventory", SponsorshipInventoryViewSet, basename="sponsorship-inventory"
)
governance_router.register(
    r"performance", CampaignPerformanceViewSet, basename="campaign-performance"
)
governance_router.register(
    r"approval-workflows",
    SponsorshipApprovalWorkflowViewSet,
    basename="approval-workflow",
)
governance_router.register(
    r"compliance-audits", ComplianceAuditViewSet, basename="compliance-audit"
)

urlpatterns = [
    path("register/", views.sponsor_register_view, name="sponsor-register"),
    path("accounts/", views.sponsor_accounts_view, name="sponsor-accounts"),
    path(
        "accounts/<int:account_id>/",
        views.sponsor_account_detail_view,
        name="sponsor-account-detail",
    ),
    path(
        "accounts/<int:account_id>/members/",
        views.sponsor_account_members_view,
        name="sponsor-account-members",
    ),
    path(
        "packages/",
        views.sponsor_packages_view,
        name="sponsor-packages",
    ),
    path(
        "packages/<int:package_id>/",
        views.sponsor_package_detail_view,
        name="sponsor-package-detail",
    ),
    path(
        "packages/<int:package_id>/approve/",
        views.sponsor_package_approve_view,
        name="sponsor-package-approve",
    ),
    path(
        "packages/<int:package_id>/reject/",
        views.sponsor_package_reject_view,
        name="sponsor-package-reject",
    ),
    path(
        "packages/<int:package_id>/benefits/",
        views.sponsor_package_benefits_view,
        name="sponsor-package-benefits",
    ),
    path(
        "packages/<int:package_id>/opportunities/",
        views.sponsor_package_opportunities_view,
        name="sponsor-package-opportunities",
    ),
    path(
        "packages/<int:package_id>/revenue-share-rules/",
        views.sponsor_package_revenue_share_rules_view,
        name="sponsor-package-revenue-share-rules",
    ),
    path(
        "agreements/",
        views.sponsor_agreements_view,
        name="sponsor-agreements",
    ),
    path(
        "agreements/<int:agreement_id>/",
        views.sponsor_agreement_detail_view,
        name="sponsor-agreement-detail",
    ),
    path(
        "agreements/<int:agreement_id>/approve/",
        views.sponsor_agreement_approve_view,
        name="sponsor-agreement-approve",
    ),
    path(
        "agreements/<int:agreement_id>/reject/",
        views.sponsor_agreement_reject_view,
        name="sponsor-agreement-reject",
    ),
    path(
        "agreements/<int:agreement_id>/activate/",
        views.sponsor_agreement_activate_view,
        name="sponsor-agreement-activate",
    ),
    path(
        "agreements/<int:agreement_id>/payment-schedules/",
        views.sponsor_agreement_payment_schedules_view,
        name="sponsor-agreement-payment-schedules",
    ),
    path(
        "agreements/<int:agreement_id>/payments/",
        views.sponsor_agreement_payments_view,
        name="sponsor-agreement-payments",
    ),
    path(
        "agreements/<int:agreement_id>/revenue-share-rules/",
        views.sponsor_agreement_revenue_share_rules_view,
        name="sponsor-agreement-revenue-share-rules",
    ),
    path(
        "agreements/<int:agreement_id>/revenue-distributions/",
        views.sponsor_agreement_revenue_distributions_view,
        name="sponsor-agreement-revenue-distributions",
    ),
    path(
        "payments/<int:payment_id>/confirm/",
        views.sponsor_payment_confirm_view,
        name="sponsor-payment-confirm",
    ),
    path(
        "payments/<int:payment_id>/reject/",
        views.sponsor_payment_reject_view,
        name="sponsor-payment-reject",
    ),
    path(
        "payments/<int:payment_id>/revenue-distributions/",
        views.sponsor_payment_revenue_distributions_view,
        name="sponsor-payment-revenue-distributions",
    ),
    path(
        "agreements/<int:agreement_id>/flutterwave/initialize/",
        views.sponsor_agreement_flutterwave_initialize_view,
        name="sponsor-agreement-flutterwave-initialize",
    ),
    path(
        "flutterwave/verify/",
        views.flutterwave_verify_view,
        name="flutterwave-verify",
    ),
    path(
        "flutterwave/webhook/",
        views.flutterwave_webhook_view,
        name="flutterwave-webhook",
    ),
    # Governance endpoints
    path("governance/", include(governance_router.urls)),
]
