from django.contrib import admin

from .models import (
    Ticket,
    TicketOrder,
    TicketOrderItem,
    TicketType,
    TicketValidationLog,
)


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "match",
        "price",
        "currency",
        "quantity_available",
        "quantity_sold",
        "status",
    )
    list_filter = ("status", "currency")
    search_fields = ("name", "match__home_club__name", "match__away_club__name")


class TicketOrderItemInline(admin.TabularInline):
    model = TicketOrderItem
    extra = 0
    readonly_fields = ("ticket_type", "quantity", "unit_price", "total_price")
    can_delete = False


@admin.register(TicketOrder)
class TicketOrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "buyer",
        "total_amount",
        "currency",
        "status",
        "provider",
        "provider_status",
        "created_at",
        "paid_at",
    )
    list_filter = ("status", "currency", "provider")
    search_fields = ("buyer__email", "payment_reference", "provider_transaction_id")
    readonly_fields = (
        "payment_reference",
        "provider_transaction_id",
        "provider_status",
        "provider_response",
        "checkout_url",
        "checkout_initialized_at",
        "created_at",
        "paid_at",
        "updated_at",
    )
    inlines = [TicketOrderItemInline]


@admin.register(TicketOrderItem)
class TicketOrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "ticket_type",
        "quantity",
        "unit_price",
        "total_price",
        "created_at",
    )
    search_fields = ("order__payment_reference", "ticket_type__name")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_code",
        "owner",
        "ticket_type",
        "match",
        "status",
        "issued_at",
        "used_at",
    )
    list_filter = ("status",)
    search_fields = ("=ticket_code", "owner__email", "ticket_type__name")


@admin.register(TicketValidationLog)
class TicketValidationLogAdmin(admin.ModelAdmin):
    list_display = (
        "scanned_code",
        "ticket",
        "match",
        "scanned_by",
        "result",
        "created_at",
    )
    list_filter = ("result",)
    search_fields = ("scanned_code", "=ticket__ticket_code", "scanned_by__email")
