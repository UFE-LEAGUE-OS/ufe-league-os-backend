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
        "payment-webhook/",
        views.membership_payment_webhook_view,
        name="membership-payment-webhook",
    ),
]
