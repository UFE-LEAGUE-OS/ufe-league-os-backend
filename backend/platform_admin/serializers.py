from rest_framework import serializers

from .models import (
    Announcement,
    Banner,
    Broadcast,
    FeatureFlag,
    HelpCenterArticle,
    NotificationTemplate,
    PublicContent,
    SystemMessage,
)


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "body",
            "audience",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = [
            "id",
            "name",
            "key",
            "description",
            "enabled",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class BannerSerializer(serializers.ModelSerializer):
    cta_url = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Banner
        fields = [
            "id",
            "title",
            "subtitle",
            "cta_text",
            "cta_url",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class SystemMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemMessage
        fields = [
            "id",
            "title",
            "body",
            "severity",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class PublicContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicContent
        fields = [
            "id",
            "slug",
            "title",
            "body",
            "content_type",
            "is_published",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class HelpCenterArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = HelpCenterArticle
        fields = [
            "id",
            "slug",
            "title",
            "summary",
            "body",
            "category",
            "is_published",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class BroadcastSerializer(serializers.ModelSerializer):
    class Meta:
        model = Broadcast
        fields = [
            "id",
            "title",
            "body",
            "audience",
            "channel",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = [
            "id",
            "name",
            "subject",
            "body",
            "template_type",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]
