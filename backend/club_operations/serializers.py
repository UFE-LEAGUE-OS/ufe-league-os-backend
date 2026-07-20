from rest_framework import serializers

from accounts.serializers import UserSummarySerializer
from .models import Announcement, ClubDocument, ComplianceChecklist, CommunicationLog


class ClubDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = UserSummarySerializer(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ClubDocument
        fields = [
            "id",
            "club",
            "title",
            "description",
            "category",
            "file",
            "file_url",
            "uploaded_by",
            "uploaded_at",
            "expiry_date",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "uploaded_by",
            "uploaded_at",
            "created_at",
            "updated_at",
        ]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None


class ClubDocumentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClubDocument
        fields = [
            "club",
            "title",
            "description",
            "category",
            "file",
            "expiry_date",
            "notes",
        ]


class ComplianceChecklistSerializer(serializers.ModelSerializer):
    completed_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = ComplianceChecklist
        fields = [
            "id",
            "club",
            "title",
            "description",
            "category",
            "due_date",
            "priority",
            "status",
            "completed",
            "completed_by",
            "completed_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "completed_by",
            "completed_at",
            "created_at",
            "updated_at",
        ]


class ComplianceChecklistCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceChecklist
        fields = [
            "club",
            "title",
            "description",
            "category",
            "due_date",
            "priority",
            "notes",
        ]


class AnnouncementSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "club",
            "title",
            "message",
            "audience",
            "priority",
            "created_by",
            "created_at",
            "expires_at",
            "published_at",
            "is_published",
            "attachment",
            "is_deleted",
            "deleted_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "created_at",
            "published_at",
            "is_deleted",
            "deleted_at",
        ]


class AnnouncementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = [
            "club",
            "title",
            "message",
            "audience",
            "priority",
            "expires_at",
            "attachment",
        ]


class CommunicationLogSerializer(serializers.ModelSerializer):
    sender = UserSummarySerializer(read_only=True)

    class Meta:
        model = CommunicationLog
        fields = [
            "id",
            "club",
            "communication_type",
            "title",
            "audience",
            "sender",
            "status",
            "sent_at",
            "metadata",
            "related_announcement",
        ]
        read_only_fields = fields
