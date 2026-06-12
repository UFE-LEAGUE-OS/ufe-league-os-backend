from django.contrib import admin

from .models import SponsorAccount, SponsorAccountMember

# Register your models here.


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
