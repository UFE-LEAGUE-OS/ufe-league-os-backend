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
        max_length=20,
        choices=Audience.choices,
        default=Audience.ALL,
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="announcements",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class FeatureFlag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    key = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feature_flags",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
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
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="banners",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
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
        max_length=20,
        choices=Severity.choices,
        default=Severity.INFO,
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="system_messages",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Broadcast(models.Model):
    class Audience(models.TextChoices):
        ALL = "ALL", "All"
        FANS = "FANS", "Fans"
        CLUBS = "CLUBS", "Clubs"
        LEAGUES = "LEAGUES", "Leagues"
        SPONSORS = "SPONSORS", "Sponsors"

    title = models.CharField(max_length=255)
    body = models.TextField()
    audience = models.CharField(
        max_length=20,
        choices=Audience.choices,
        default=Audience.ALL,
    )
    channel = models.CharField(max_length=50, default="in_app")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="broadcasts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class HelpCenterArticle(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=255)
    summary = models.CharField(max_length=500, blank=True)
    body = models.TextField()
    category = models.CharField(max_length=100, blank=True)
    is_published = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="help_center_articles",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class NotificationTemplate(models.Model):
    class TemplateType(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        PUSH = "push", "Push"

    name = models.CharField(max_length=100, unique=True)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    template_type = models.CharField(
        max_length=20,
        choices=TemplateType.choices,
        default=TemplateType.EMAIL,
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PublicContent(models.Model):
    class ContentType(models.TextChoices):
        PAGE = "page", "Page"
        SECTION = "section", "Section"

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    content_type = models.CharField(
        max_length=20,
        choices=ContentType.choices,
        default=ContentType.PAGE,
    )
    is_published = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="public_content_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title
