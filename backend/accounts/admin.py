from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, EmailOTP


# Register your models here.
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Django admin configuration for the custom League OS User model.
    """

    model = User

    list_display = (
        "email",
        "phone_number",
        "first_name",
        "last_name",
        "role",
        "is_email_verified",
        "is_phone_verified",
        "is_staff",
        "is_active",
    )

    list_filter = (
        "role",
        "is_email_verified",
        "is_phone_verified",
        "is_staff",
        "is_active",
    )

    search_fields = (
        "email",
        "phone_number",
        "first_name",
        "last_name",
    )

    ordering = ("email",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal Information",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "phone_number",
                    "avatar",
                )
            },
        ),
        (
            "League OS Role and Verification",
            {
                "fields": (
                    "role",
                    "is_email_verified",
                    "is_phone_verified",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important Dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "phone_number",
                    "role",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    """Django admin configuration for email OTP records"""

    list_display = ("user", "code", "purpose", "is_used", "attempts", "expires_at")
    list_filter = ("purpose", "is_used", "created_at", "expires_at")
    search_fields = ("user__email", "user__phone_number", "code")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
