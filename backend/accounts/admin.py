from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


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
