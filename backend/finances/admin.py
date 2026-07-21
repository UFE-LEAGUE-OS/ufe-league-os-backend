from django.contrib import admin

from .models import Invoice, Receipt, FinanceAuditLog


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "invoice_number",
        "club",
        "payment_type",
        "amount",
        "currency",
        "status",
        "issue_date",
        "created_at",
    ]
    list_filter = ["status", "payment_type", "club"]
    search_fields = ["invoice_number", "buyer_name", "buyer_email"]
    readonly_fields = ["invoice_number", "created_at", "updated_at"]


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = [
        "receipt_number",
        "club",
        "payment_type",
        "amount",
        "currency",
        "issue_date",
        "payment_date",
        "created_at",
    ]
    list_filter = ["payment_type", "club"]
    search_fields = ["receipt_number", "buyer_name", "buyer_email"]
    readonly_fields = ["receipt_number", "created_at", "updated_at"]


@admin.register(FinanceAuditLog)
class FinanceAuditLogAdmin(admin.ModelAdmin):
    list_display = [
        "action",
        "actor",
        "club",
        "target_repr",
        "created_at",
    ]
    list_filter = ["action", "club", "created_at"]
    search_fields = ["target_repr", "description", "actor__email"]
    readonly_fields = ["created_at"]
