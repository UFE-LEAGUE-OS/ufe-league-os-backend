from django.contrib import admin
from .models import (
    RoleTemplate,
    PermissionBundle,
    Permission,
    RoleTemplatePermission,
    UserRoleAssignment,
    UserPermissionOverride,
    Session,
    ImpersonationLog,
)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("codename", "name", "category", "bundle", "is_active")
    list_filter = ("category", "bundle", "is_active")
    search_fields = ("codename", "name", "description")
    ordering = ["category", "codename"]


@admin.register(PermissionBundle)
class PermissionBundleAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_system", "is_active")
    list_filter = ("is_system", "is_active")
    search_fields = ("name", "slug", "description")


@admin.register(RoleTemplate)
class RoleTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_system", "is_active")
    list_filter = ("is_system", "is_active")
    search_fields = ("name", "slug", "description")


@admin.register(RoleTemplatePermission)
class RoleTemplatePermissionAdmin(admin.ModelAdmin):
    list_display = ("role_template", "permission")
    list_filter = ("role_template", "permission__category")
    search_fields = ("role_template__name", "permission__codename")


@admin.register(UserRoleAssignment)
class UserRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "role_template", "assigned_by", "is_active", "created_at")
    list_filter = ("is_active", "role_template")
    search_fields = ("user__email", "role_template__name", "notes")
    date_hierarchy = "created_at"


@admin.register(UserPermissionOverride)
class UserPermissionOverrideAdmin(admin.ModelAdmin):
    list_display = ("user", "permission", "effect", "is_active")
    list_filter = ("effect", "is_active", "permission__category")
    search_fields = ("user__email", "permission__codename")


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "session_key",
        "ip_address",
        "is_active",
        "last_accessed",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("user__email", "session_key", "ip_address", "user_agent")
    date_hierarchy = "created_at"


@admin.register(ImpersonationLog)
class ImpersonationLogAdmin(admin.ModelAdmin):
    list_display = ("admin", "target_user", "is_active", "started_at", "ended_at")
    list_filter = ("is_active",)
    search_fields = ("admin__email", "target_user__email", "reason")
    date_hierarchy = "started_at"
