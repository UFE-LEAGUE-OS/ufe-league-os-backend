from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class Announcement(models.Model):
    class Audience(models.TextChoices):
        ALL = "ALL", "All"
        FANS = "FANS", "Fans"
        CLUBS = "CLUBS", "Clubs"
        LEAGUES = "LEAGUES", "Leagues"
        SPONSORS = "SPONSORS", "Sponsors"

    title = models.CharField(max_length=255)
    body = models.TextField()
    audience = models.CharField(
        max_length=20, choices=Audience.choices, default=Audience.ALL
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="announcements"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "platform_admin"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class FeatureFlag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    key = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="feature_flags"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "platform_admin"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Banner(models.Model):
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True)
    cta_text = models.CharField(max_length=100, blank=True)
    cta_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="banners"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "platform_admin"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class SystemMessage(models.Model):
    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    title = models.CharField(max_length=255)
    body = models.TextField()
    severity = models.CharField(
        max_length=20, choices=Severity.choices, default=Severity.INFO
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="system_messages"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "platform_admin"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
