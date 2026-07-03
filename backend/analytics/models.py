from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ReportAccessLog(models.Model):
    """Audit trail for analytics report access and exports."""

    class ReportType(models.TextChoices):
        USER_GROWTH = "USER_GROWTH", "User Growth"
        ENGAGEMENT = "ENGAGEMENT", "Engagement"
        MEMBERSHIP = "MEMBERSHIP", "Membership"
        TICKETING = "TICKETING", "Ticketing"
        SPONSORSHIP = "SPONSORSHIP", "Sponsorship"
        SYSTEM_HEALTH = "SYSTEM_HEALTH", "System Health"
        REVENUE = "REVENUE", "Revenue"
        PLATFORM_SUMMARY = "PLATFORM_SUMMARY", "Platform Summary"

    class ActionType(models.TextChoices):
        VIEW = "VIEW", "View"
        EXPORT = "EXPORT", "Export"
        PRINT = "PRINT", "Print"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="analytics_access_logs"
    )
    report_type = models.CharField(max_length=30, choices=ReportType.choices)
    action = models.CharField(max_length=20, choices=ActionType.choices)
    filters_applied = models.JSONField(default=dict, blank=True)
    ip_address = models.CharField(max_length=45, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["report_type", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} {self.action} {self.report_type}"


class CachedAnalytics(models.Model):
    """Cached analytics aggregations for performance."""

    class MetricType(models.TextChoices):
        USER_GROWTH = "USER_GROWTH", "User Growth"
        ENGAGEMENT = "ENGAGEMENT", "Engagement"
        MEMBERSHIP = "MEMBERSHIP", "Membership"
        TICKETING = "TICKETING", "Ticketing"
        SPONSORSHIP = "SPONSORSHIP", "Sponsorship"
        SYSTEM_HEALTH = "SYSTEM_HEALTH", "System Health"
        REVENUE = "REVENUE", "Revenue"
        PLATFORM_SUMMARY = "PLATFORM_SUMMARY", "Platform Summary"

    metric_type = models.CharField(max_length=30, choices=MetricType.choices)
    period = models.CharField(max_length=20, help_text="e.g., daily, weekly, monthly")
    start_date = models.DateField()
    end_date = models.DateField()
    value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["metric_type", "period", "start_date", "end_date"]
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["metric_type", "period", "-start_date"]),
            models.Index(fields=["-computed_at"]),
        ]

    def __str__(self):
        return f"{self.metric_type} {self.period} {self.start_date}-{self.end_date}"
