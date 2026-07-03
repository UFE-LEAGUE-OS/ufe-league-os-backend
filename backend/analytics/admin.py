from django.contrib import admin
from .models import ReportAccessLog, CachedAnalytics


@admin.register(ReportAccessLog)
class ReportAccessLogAdmin(admin.ModelAdmin):
    list_display = ("user", "report_type", "action", "ip_address", "created_at")
    list_filter = ("report_type", "action", "created_at")
    search_fields = ("user__email", "ip_address", "user_agent")
    date_hierarchy = "created_at"


@admin.register(CachedAnalytics)
class CachedAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        "metric_type",
        "period",
        "start_date",
        "end_date",
        "value",
        "computed_at",
    )
    list_filter = ("metric_type", "period", "start_date")
    search_fields = ("metric_type",)
    date_hierarchy = "start_date"
