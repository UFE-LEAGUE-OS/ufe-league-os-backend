from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AuditLog, EmailOTP, Notification, User
from .rbac import log_role_change


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

    def save_model(self, request, obj, form, change):
        previous_role = None

        if change and obj.pk:
            existing = User.objects.filter(pk=obj.pk).first()
            if existing:
                previous_role = existing.role

        super().save_model(request, obj, form, change)

        if change and previous_role is not None and previous_role != obj.role:
            log_role_change(
                target_user=obj,
                previous_role=previous_role,
                new_role=obj.role,
                actor=request.user,
                reason="admin_role_update",
            )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Django admin configuration for RBAC audit events."""

    list_display = (
        "category",
        "action",
        "actor",
        "target_user",
        "status_code",
        "path",
        "created_at",
    )
    list_filter = ("category", "action", "created_at")
    search_fields = ("actor__email", "target_user__email", "action", "path")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Django admin configuration for in-app notifications."""

    list_display = (
        "user",
        "category",
        "title",
        "is_read",
        "created_at",
    )
    list_filter = ("category", "is_read", "created_at")
    search_fields = ("user__email", "title", "message")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    """Django admin configuration for email OTP records"""

    list_display = ("user", "code", "purpose", "expires_at")
    list_filter = ("purpose", "created_at", "expires_at")
    search_fields = ("user__email", "user__phone_number", "code")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)