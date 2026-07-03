from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class RoleTemplate(models.Model):
    """Reusable role template defining a set of permissions."""

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active", "name"]),
        ]

    def __str__(self):
        return self.name


class PermissionBundle(models.Model):
    """Group of related permissions (e.g., 'ticketing_management')."""

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active", "name"]),
        ]

    def __str__(self):
        return self.name


class Permission(models.Model):
    """Individual permission codename (e.g., 'ticketing.orders.view')."""

    class Category(models.TextChoices):
        TICKETING = "TICKETING", "Ticketing"
        MEMBERSHIP = "MEMBERSHIP", "Membership"
        SPONSORSHIP = "SPONSORSHIP", "Sponsorship"
        DASHBOARDS = "DASHBOARDS", "Dashboards"
        GOVERNANCE = "GOVERNANCE", "Governance"
        MONITORING = "MONITORING", "Monitoring"
        ACCOUNTS = "ACCOUNTS", "Accounts"
        ENGAGEMENTS = "ENGAGEMENTS", "Engagements"
        FANTASY = "FANTASY", "Fantasy"
        SYSTEM = "SYSTEM", "System"

    bundle = models.ForeignKey(
        PermissionBundle,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="permissions",
    )
    codename = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=30, choices=Category.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "codename"]
        indexes = [
            models.Index(fields=["codename"]),
            models.Index(fields=["category", "is_active"]),
        ]

    def __str__(self):
        return f"{self.category}: {self.codename}"


class RoleTemplatePermission(models.Model):
    """Through model linking role templates to permissions."""

    role_template = models.ForeignKey(
        RoleTemplate,
        on_delete=models.CASCADE,
        related_name="template_permissions",
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name="role_template_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["role_template", "permission"]
        ordering = [
            "role_template__name",
            "permission__category",
            "permission__codename",
        ]
        indexes = [
            models.Index(fields=["role_template", "permission"]),
        ]

    def __str__(self):
        return f"{self.role_template.name} -> {self.permission.codename}"


class UserRoleAssignment(models.Model):
    """Assign a role template (and optional active role override) to a user."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="role_assignments",
    )
    role_template = models.ForeignKey(
        RoleTemplate,
        on_delete=models.PROTECT,
        related_name="user_assignments",
    )
    assigned_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_role_templates",
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "role_template"]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["role_template", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user.email} -> {self.role_template.name}"


class UserPermissionOverride(models.Model):
    """Direct permission grant/deny overrides for a user."""

    class Effect(models.TextChoices):
        ALLOW = "ALLOW", "Allow"
        DENY = "DENY", "Deny"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="permission_overrides",
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name="user_overrides",
    )
    effect = models.CharField(max_length=10, choices=Effect.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "permission"]
        ordering = ["user__email", "permission__codename"]
        indexes = [
            models.Index(fields=["user", "effect", "is_active"]),
            models.Index(fields=["permission", "effect"]),
        ]

    def __str__(self):
        return f"{self.user.email} {self.effect} {self.permission.codename}"


class Session(models.Model):
    """Track authenticated user sessions for management and revocation."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    session_key = models.CharField(max_length=128, unique=True)
    ip_address = models.CharField(max_length=45, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    last_accessed = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_accessed"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["session_key"]),
            models.Index(fields=["-last_accessed"]),
        ]

    def __str__(self):
        return f"{self.user.email} session {self.session_key[:12]}..."


class ImpersonationLog(models.Model):
    """Audit trail for admin user impersonation sessions."""

    admin = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="impersonation_sessions_started",
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="impersonation_sessions_received",
    )
    reason = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    ip_address = models.CharField(max_length=45, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["admin", "-started_at"]),
            models.Index(fields=["target_user", "-started_at"]),
            models.Index(fields=["is_active", "-started_at"]),
        ]

    def __str__(self):
        status = "ACTIVE" if self.is_active else "ENDED"
        return f"{self.admin.email} impersonating {self.target_user.email} ({status})"
