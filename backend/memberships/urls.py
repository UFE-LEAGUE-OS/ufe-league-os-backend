from django.urls import path

from . import views

urlpatterns = [
    path("plans/", views.membership_plans_view, name="membership-plans"),
    path(
        "plans/<int:plan_id>/",
        views.membership_plan_detail_view,
        name="membership-plan-detail",
    ),
    path(
        "subscriptions/",
        views.membership_subscriptions_view,
        name="membership-subscriptions",
    ),
    path("my-membership/", views.my_membership_view, name="my-membership"),
    path("card/", views.membership_card_view, name="membership-card"),
    path("payments/", views.membership_payments_view, name="membership-payments"),
    path(
        "initiate-payment/",
        views.membership_initiate_payment_view,
        name="membership-initiate-payment",
    ),
    path(
        "flutterwave/verify/",
        views.membership_flutterwave_verify_view,
        name="membership-flutterwave-verify",
    ),
    path(
        "payment-webhook/",
        views.membership_payment_webhook_view,
        name="membership-payment-webhook",
    ),
    path(
        "club-admin/members/directory/",
        views.club_members_directory_view,
        name="club-members-directory",
    ),
    path(
        "club-admin/requests/",
        views.membership_requests_view,
        name="membership-requests",
    ),
    path(
        "club-admin/categories/",
        views.membership_categories_view,
        name="membership-categories",
    ),
    path(
        "club-admin/categories/<int:plan_id>/",
        views.membership_category_detail_view,
        name="membership-category-detail",
    ),
    path(
        "club-admin/reports/export/",
        views.membership_reports_export_view,
        name="membership-reports-export",
    ),
    path(
        "subscriptions/renew/",
        views.membership_renew_view,
        name="membership-renew",
    ),
]
