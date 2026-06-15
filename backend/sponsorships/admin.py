from django.contrib import admin

from .models import (
    RevenueDistribution,
    RevenueShareRule,
    SponsorAccount,
    SponsorAccountMember,
    SponsorAgreement,
    SponsorBenefit,
    SponsorPackage,
    SponsorPayment,
    SponsorPaymentSchedule,
    SponsorWorkflowEvent,
)


class SponsorAccountMemberInline(admin.TabularInline):
    model = SponsorAccountMember
    extra = 0


@admin.register(SponsorAccount)
class SponsorAccountAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sponsor_type",
        "registration_country",
        "owner",
        "status",
        "brn",
        "tin",
        "created_at",
    )

    list_filter = (
        "sponsor_type",
        "registration_country",
        "status",
        "created_at",
    )

    search_fields = (
        "name",
        "owner__email",
        "brn",
        "tin",
    )

    inlines = [SponsorAccountMemberInline]


@admin.register(SponsorAccountMember)
class SponsorAccountMemberAdmin(admin.ModelAdmin):
    list_display = (
        "sponsor_account",
        "user",
        "member_role",
        "is_active",
        "created_at",
    )

    list_filter = (
        "member_role",
        "is_active",
        "created_at",
    )

    search_fields = (
        "sponsor_account__name",
        "user__email",
        "user__phone_number",
    )


class SponsorBenefitInline(admin.TabularInline):
    model = SponsorBenefit
    extra = 0


class RevenueShareRuleInline(admin.TabularInline):
    model = RevenueShareRule
    extra = 0


class SponsorPaymentScheduleInline(admin.TabularInline):
    model = SponsorPaymentSchedule
    extra = 0


class SponsorPaymentInline(admin.TabularInline):
    model = SponsorPayment
    extra = 0


class RevenueDistributionInline(admin.TabularInline):
    model = RevenueDistribution
    extra = 0


class SponsorWorkflowEventInline(admin.TabularInline):
    model = SponsorWorkflowEvent
    extra = 0
    readonly_fields = (
        "actor",
        "event_type",
        "from_status",
        "to_status",
        "note",
        "created_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SponsorPackage)
class SponsorPackageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner_type",
        "owner_name",
        "scope_type",
        "scope_name",
        "category",
        "price_amount",
        "currency",
        "is_exclusive",
        "status",
        "created_at",
    )

    list_filter = (
        "owner_type",
        "scope_type",
        "sponsor_type_allowed",
        "category",
        "is_exclusive",
        "requires_platform_fee",
        "status",
        "created_at",
    )

    search_fields = (
        "name",
        "owner_name",
        "scope_name",
        "owner_identifier",
        "scope_identifier",
    )

    inlines = [
        SponsorBenefitInline,
        RevenueShareRuleInline,
        SponsorWorkflowEventInline,
    ]


@admin.register(SponsorBenefit)
class SponsorBenefitAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sponsor_package",
        "benefit_type",
        "quantity",
        "discount_percentage",
        "is_platform_controlled",
        "requires_payment_confirmation",
        "created_at",
    )

    list_filter = (
        "benefit_type",
        "is_platform_controlled",
        "requires_payment_confirmation",
        "created_at",
    )

    search_fields = (
        "name",
        "sponsor_package__name",
        "sponsor_package__scope_name",
    )


@admin.register(SponsorAgreement)
class SponsorAgreementAdmin(admin.ModelAdmin):
    list_display = (
        "sponsor_account",
        "sponsor_package",
        "agreement_type",
        "payment_source",
        "payment_model",
        "total_value",
        "currency",
        "platform_fee_required",
        "platform_fee_status",
        "status",
        "created_at",
    )

    list_filter = (
        "agreement_type",
        "payment_source",
        "payment_model",
        "platform_fee_required",
        "platform_fee_status",
        "benefits_tier",
        "activation_rule",
        "status",
        "created_at",
    )

    search_fields = (
        "sponsor_account__name",
        "sponsor_package__name",
        "sponsor_package__scope_name",
        "reference",
        "proof_reference",
    )

    inlines = [
        SponsorPaymentScheduleInline,
        SponsorPaymentInline,
        RevenueShareRuleInline,
        RevenueDistributionInline,
        SponsorWorkflowEventInline,
    ]


@admin.register(SponsorPaymentSchedule)
class SponsorPaymentScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "agreement",
        "schedule_type",
        "sequence_number",
        "due_date",
        "amount_due",
        "currency",
        "status",
    )

    list_filter = (
        "schedule_type",
        "status",
        "due_date",
        "created_at",
    )

    search_fields = (
        "agreement__sponsor_account__name",
        "agreement__sponsor_package__name",
    )


@admin.register(SponsorPayment)
class SponsorPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "agreement",
        "payment_schedule",
        "amount_paid",
        "currency",
        "payment_method",
        "status",
        "transaction_reference",
        "paid_at",
        "created_at",
    )

    list_filter = (
        "payment_method",
        "status",
        "paid_at",
        "created_at",
    )

    search_fields = (
        "agreement__sponsor_account__name",
        "agreement__sponsor_package__name",
        "transaction_reference",
    )

    inlines = [
        RevenueDistributionInline,
        SponsorWorkflowEventInline,
    ]


@admin.register(RevenueShareRule)
class RevenueShareRuleAdmin(admin.ModelAdmin):
    list_display = (
        "recipient_name",
        "recipient_type",
        "percentage",
        "fixed_amount",
        "is_platform_share",
        "sponsor_package",
        "agreement",
    )

    list_filter = (
        "recipient_type",
        "is_platform_share",
        "created_at",
    )

    search_fields = (
        "recipient_name",
        "sponsor_package__name",
        "agreement__sponsor_account__name",
    )


@admin.register(RevenueDistribution)
class RevenueDistributionAdmin(admin.ModelAdmin):
    list_display = (
        "agreement",
        "payment",
        "recipient_name",
        "recipient_type",
        "amount",
        "currency",
        "status",
        "created_at",
    )

    list_filter = (
        "recipient_type",
        "status",
        "created_at",
    )

    search_fields = (
        "recipient_name",
        "agreement__sponsor_account__name",
        "agreement__sponsor_package__name",
    )


@admin.register(SponsorWorkflowEvent)
class SponsorWorkflowEventAdmin(admin.ModelAdmin):
    list_display = (
        "event_type",
        "actor",
        "sponsor_package",
        "agreement",
        "payment",
        "from_status",
        "to_status",
        "created_at",
    )

    list_filter = (
        "event_type",
        "created_at",
    )

    search_fields = (
        "sponsor_package__name",
        "agreement__sponsor_account__name",
        "payment__transaction_reference",
        "actor__email",
    )

    readonly_fields = (
        "sponsor_package",
        "agreement",
        "payment",
        "actor",
        "event_type",
        "from_status",
        "to_status",
        "note",
        "created_at",
    )
