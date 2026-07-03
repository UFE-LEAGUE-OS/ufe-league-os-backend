from rest_framework import serializers
from .models import ReportAccessLog, CachedAnalytics


class ReportAccessLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    report_type_display = serializers.CharField(
        source="get_report_type_display", read_only=True
    )
    action_display = serializers.CharField(
        source="get_action_type_display", read_only=True
    )

    class Meta:
        model = ReportAccessLog
        fields = [
            "id",
            "user",
            "user_email",
            "report_type",
            "report_type_display",
            "action",
            "action_display",
            "filters_applied",
            "ip_address",
            "user_agent",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class CachedAnalyticsSerializer(serializers.ModelSerializer):
    metric_type_display = serializers.CharField(
        source="get_metric_type_display", read_only=True
    )
    computed_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = CachedAnalytics
        fields = [
            "id",
            "metric_type",
            "metric_type_display",
            "period",
            "start_date",
            "end_date",
            "value",
            "metadata",
            "computed_at",
        ]
        read_only_fields = ["id", "computed_at"]


class AnalyticsSummarySerializer(serializers.Serializer):
    """Summary response for platform analytics."""

    user_growth = serializers.DictField()
    engagement = serializers.DictField()
    membership = serializers.DictField()
    ticketing = serializers.DictField()
    sponsorship = serializers.DictField()
    system_health = serializers.DictField()
    revenue = serializers.DictField()
    generated_at = serializers.DateTimeField()
