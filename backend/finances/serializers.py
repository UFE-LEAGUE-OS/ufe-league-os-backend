
from django.db.models import Sum
from rest_framework import serializers

from memberships.models import MembershipPayment
from ticketing.models import TicketOrder

from .models import Invoice, Receipt, FinanceAuditLog


class InvoiceSerializer(serializers.ModelSerializer):
    member_name = serializers.SerializerMethodField()
    member_email = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id",
            "club",
            "invoice_number",
            "payment_type",
            "member",
            "member_name",
            "member_email",
            "buyer_name",
            "buyer_email",
            "amount",
            "tax_amount",
            "currency",
            "status",
            "issue_date",
            "due_date",
            "paid_date",
            "notes",
            "download_url",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "invoice_number",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_member_name(self, obj):
        if obj.member:
            return obj.member.full_name or obj.member.email
        return obj.buyer_name or ""

    def get_member_email(self, obj):
        if obj.member:
            return obj.member.email
        return obj.buyer_email or ""


class InvoiceListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    member_name = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "payment_type",
            "member_name",
            "amount",
            "currency",
            "status",
            "issue_date",
            "paid_date",
        ]

    def get_member_name(self, obj):
        if obj.member:
            return obj.member.full_name or obj.member.email
        return obj.buyer_name or ""


class ReceiptSerializer(serializers.ModelSerializer):
    member_name = serializers.SerializerMethodField()

    class Meta:
        model = Receipt
        fields = [
            "id",
            "club",
            "receipt_number",
            "payment_type",
            "invoice",
            "member",
            "member_name",
            "buyer_name",
            "buyer_email",
            "amount",
            "tax_amount",
            "currency",
            "payment_method",
            "transaction_reference",
            "issue_date",
            "payment_date",
            "notes",
            "download_url",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "receipt_number",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_member_name(self, obj):
        if obj.member:
            return obj.member.full_name or obj.member.email
        return obj.buyer_name or ""


class ReceiptListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    member_name = serializers.SerializerMethodField()

    class Meta:
        model = Receipt
        fields = [
            "id",
            "receipt_number",
            "payment_type",
            "member_name",
            "amount",
            "currency",
            "issue_date",
            "payment_date",
        ]

    def get_member_name(self, obj):
        if obj.member:
            return obj.member.full_name or obj.member.email
        return obj.buyer_name or ""


class FinanceAuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = FinanceAuditLog
        fields = [
            "id",
            "club",
            "actor",
            "actor_name",
            "action",
            "target_type",
            "target_id",
            "target_repr",
            "description",
            "ip_address",
            "metadata",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]

    def get_actor_name(self, obj):
        if obj.actor:
            return obj.actor.full_name or obj.actor.email
        return "System"


class FinanceAuditLogCreateSerializer(serializers.Serializer):
    """Used internally for creating audit log entries."""

    club_id = serializers.IntegerField()
    actor_id = serializers.IntegerField(required=False, allow_null=True)
    action = serializers.ChoiceField(choices=FinanceAuditLog.Action.choices)
    target_type = serializers.CharField(required=False, allow_blank=True)
    target_id = serializers.IntegerField(required=False, allow_null=True)
    target_repr = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    ip_address = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False, default=dict)


# ---------------------------------------------------------------------------
# Membership Payments Report Serializers
# ---------------------------------------------------------------------------


class MembershipPaymentReportSerializer(serializers.ModelSerializer):
    member_name = serializers.SerializerMethodField()
    member_email = serializers.SerializerMethodField()
    membership_type = serializers.SerializerMethodField()
    payment_method_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = MembershipPayment
        fields = [
            "id",
            "member_name",
            "member_email",
            "membership_type",
            "amount_paid",
            "currency",
            "status",
            "status_display",
            "payment_method",
            "payment_method_display",
            "transaction_reference",
            "paid_at",
            "created_at",
        ]

    def get_member_name(self, obj):
        user = obj.subscription.user
        return user.full_name or user.email

    def get_member_email(self, obj):
        return obj.subscription.user.email

    def get_membership_type(self, obj):
        plan = obj.subscription_plan or obj.subscription.plan
        return plan.name if plan else "N/A"

    def get_payment_method_display(self, obj):
        return obj.get_payment_method_display()

    def get_status_display(self, obj):
        return obj.get_status_display()


class MembershipPaymentSummarySerializer(serializers.Serializer):
    total_payments = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    paid_count = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    failed_count = serializers.IntegerField()


# ---------------------------------------------------------------------------
# Ticketing Payments Report Serializers
# ---------------------------------------------------------------------------


class TicketingPaymentReportSerializer(serializers.ModelSerializer):
    match_event = serializers.SerializerMethodField()
    ticket_category = serializers.SerializerMethodField()
    buyer_name = serializers.SerializerMethodField()
    buyer_email = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    payment_method_display = serializers.SerializerMethodField()

    class Meta:
        model = TicketOrder
        fields = [
            "id",
            "match_event",
            "ticket_category",
            "buyer_name",
            "buyer_email",
            "quantity",
            "total_amount",
            "currency",
            "status",
            "payment_method_display",
            "payment_reference",
            "provider",
            "paid_at",
            "created_at",
        ]

    def get_match_event(self, obj):
        first_item = obj.items.select_related("ticket_type__match").first()
        if first_item and first_item.ticket_type:
            match = first_item.ticket_type.match
            return f"{match.home_club} vs {match.away_club}" if match else "N/A"
        return "N/A"

    def get_ticket_category(self, obj):
        categories = obj.items.values_list("ticket_type__name", flat=True).distinct()
        return ", ".join(categories) if categories else "N/A"

    def get_buyer_name(self, obj):
        return obj.buyer.full_name or obj.buyer.email

    def get_buyer_email(self, obj):
        return obj.buyer.email

    def get_quantity(self, obj):
        total = obj.items.aggregate(total=Sum("quantity"))["total"]
        return total or 0

    def get_payment_method_display(self, obj):
        return obj.get_provider_display()


class TicketingPaymentSummarySerializer(serializers.Serializer):
    tickets_sold = serializers.IntegerField()
    gross_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    average_ticket_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    successful_payments = serializers.IntegerField()
    failed_payments = serializers.IntegerField()


# ---------------------------------------------------------------------------
# Income & Expense Summary Serializer
# ---------------------------------------------------------------------------


class FinancialSummarySerializer(serializers.Serializer):
    membership_income = serializers.DecimalField(max_digits=14, decimal_places=2)
    ticketing_income = serializers.DecimalField(max_digits=14, decimal_places=2)
    sponsorship_income = serializers.DecimalField(max_digits=14, decimal_places=2)
    other_income = serializers.DecimalField(max_digits=14, decimal_places=2)
    club_expenses = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_income = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=14, decimal_places=2)
    net_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
