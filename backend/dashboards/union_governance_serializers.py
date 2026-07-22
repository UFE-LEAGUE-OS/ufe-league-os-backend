"""Serializers for reusable Union workspace governance records."""

from rest_framework import serializers

from .models import (
    UnionApproval,
    UnionAuditEvent,
    UnionDocumentReference,
    UnionReviewComment,
)


class UnionApprovalSerializer(serializers.ModelSerializer):
    requested_by_email = serializers.EmailField(
        source="requested_by.email", read_only=True
    )
    reviewed_by_email = serializers.EmailField(
        source="reviewed_by.email", read_only=True
    )

    class Meta:
        model = UnionApproval
        fields = [
            "id",
            "workspace",
            "subject_type",
            "subject_id",
            "action",
            "status",
            "requested_by",
            "requested_by_email",
            "reviewed_by",
            "reviewed_by_email",
            "reason",
            "decision_reason",
            "metadata",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "workspace",
            "status",
            "requested_by",
            "requested_by_email",
            "reviewed_by",
            "reviewed_by_email",
            "decision_reason",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]


class UnionAuditEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True)

    class Meta:
        model = UnionAuditEvent
        fields = [
            "id",
            "workspace",
            "actor",
            "actor_email",
            "action",
            "target_type",
            "target_id",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields


class UnionReviewCommentSerializer(serializers.ModelSerializer):
    author_email = serializers.EmailField(source="author.email", read_only=True)

    class Meta:
        model = UnionReviewComment
        fields = [
            "id",
            "workspace",
            "subject_type",
            "subject_id",
            "author",
            "author_email",
            "body",
            "is_internal",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "workspace",
            "author",
            "author_email",
            "created_at",
            "updated_at",
        ]


class UnionDocumentReferenceSerializer(serializers.ModelSerializer):
    uploaded_by_email = serializers.EmailField(
        source="uploaded_by.email", read_only=True
    )

    class Meta:
        model = UnionDocumentReference
        fields = [
            "id",
            "workspace",
            "subject_type",
            "subject_id",
            "document_type",
            "title",
            "file_url",
            "uploaded_by",
            "uploaded_by_email",
            "metadata",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "workspace",
            "uploaded_by",
            "uploaded_by_email",
            "created_at",
        ]
