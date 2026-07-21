import django_filters
from django.db.models import Q

from .models import Invoice, Receipt, FinanceAuditLog


class InvoiceFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    payment_type = django_filters.ChoiceFilter(choices=Invoice.PaymentType.choices)
    status = django_filters.ChoiceFilter(choices=Invoice.Status.choices)
    date_from = django_filters.DateTimeFilter(
        field_name="issue_date", lookup_expr="gte"
    )
    date_to = django_filters.DateTimeFilter(field_name="issue_date", lookup_expr="lte")
    amount_min = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")

    class Meta:
        model = Invoice
        fields = [
            "payment_type",
            "status",
        ]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(invoice_number__icontains=value)
            | Q(buyer_name__icontains=value)
            | Q(buyer_email__icontains=value)
            | Q(member__email__icontains=value)
            | Q(member__first_name__icontains=value)
            | Q(member__last_name__icontains=value)
        )


class ReceiptFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    payment_type = django_filters.ChoiceFilter(choices=Receipt.PaymentType.choices)
    date_from = django_filters.DateTimeFilter(
        field_name="issue_date", lookup_expr="gte"
    )
    date_to = django_filters.DateTimeFilter(field_name="issue_date", lookup_expr="lte")
    amount_min = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")

    class Meta:
        model = Receipt
        fields = [
            "payment_type",
        ]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(receipt_number__icontains=value)
            | Q(buyer_name__icontains=value)
            | Q(buyer_email__icontains=value)
            | Q(member__email__icontains=value)
            | Q(member__first_name__icontains=value)
            | Q(member__last_name__icontains=value)
        )


class FinanceAuditLogFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    action = django_filters.CharFilter(lookup_expr="exact")
    actor_id = django_filters.NumberFilter(field_name="actor__id")
    date_from = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    date_to = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = FinanceAuditLog
        fields = [
            "action",
            "actor_id",
        ]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(target_repr__icontains=value)
            | Q(description__icontains=value)
            | Q(target_type__icontains=value)
            | Q(actor__email__icontains=value)
            | Q(actor__first_name__icontains=value)
            | Q(actor__last_name__icontains=value)
        )
