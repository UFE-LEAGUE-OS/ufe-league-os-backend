from django.urls import path

from . import views

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
        "packages/<int:package_id>/revenue-share-rules/",
        views.sponsor_package_revenue_share_rules_view,
        name="sponsor-package-revenue-share-rules",
    ),
]
