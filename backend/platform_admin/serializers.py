from rest_framework import serializers
from .models import ApprovalLog, ChargebackRefund


class ApprovalLogSerializer(serializers.ModelSerializer):
    actor = serializers.StringRelatedField()
    content_object_str = serializers.StringRelatedField(
        source="content_object", read_only=True
    )

    class Meta:
        model = ApprovalLog
        fields = [
            "id",
            "actor",
            "action",
            "category",
            "notes",
            "created_at",
            "content_type",
            "object_id",
            "content_object_str",
        ]
        read_only_fields = ["id", "created_at", "actor", "content_object_str"]


class ChargebackRefundSerializer(serializers.ModelSerializer):
    opened_by = serializers.StringRelatedField()
    handled_by = serializers.StringRelatedField()
    payment_object_str = serializers.StringRelatedField(
        source="payment_object", read_only=True
    )

    class Meta:
        model = ChargebackRefund
        fields = "__all__"
        read_only_fields = [
            "id",
            "opened_at",
            "resolved_at",
            "opened_by",
            "handled_by",
            "payment_object_str",
        ]