from django.contrib import admin

from .models import (
    MembershipCard,
    MembershipPayment,
    MembershipPlan,
    MembershipSubscription,
)


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = (
        "club",
        "name",
        "tier",
        "billing_cycle",
        "price_amount",
        "is_active",
    )
    list_filter = ("tier", "billing_cycle", "is_active")
    search_fields = ("club__name", "name")


@admin.register(MembershipSubscription)
class MembershipSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "club", "status", "starts_at", "ends_at")
    list_filter = ("status",)
    search_fields = ("user__email", "plan__name", "club__name")


@admin.register(MembershipPayment)
class MembershipPaymentAdmin(admin.ModelAdmin):
    list_display = ("subscription", "amount_paid", "payment_method", "status")
    list_filter = ("payment_method", "status")
    search_fields = ("transaction_reference", "provider_transaction_id")


@admin.register(MembershipCard)
class MembershipCardAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "club",
        "card_number",
        "tier",
        "valid_from",
        "valid_until",
        "status",
    )
    list_filter = ("status", "tier")
    search_fields = ("user__email", "club__name", "card_number")
