from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Announcement, ClubDocument, ComplianceChecklist, CommunicationLog

User = get_user_model()


def upload_document(club, uploaded_by, **validated_data):
    validated_data.setdefault("uploaded_by", uploaded_by)
    validated_data.setdefault("club", club)
    validated_data.setdefault("status", ClubDocument.Status.ACTIVE)
    return ClubDocument.objects.create(**validated_data)


def replace_document(document, new_file, uploaded_by, notes=None):
    if document.status == ClubDocument.Status.ARCHIVED:
        raise ValueError("Archived documents cannot be replaced.")
    document.is_deleted = True
    document.deleted_at = timezone.now()
    document.save(update_fields=["is_deleted", "deleted_at"])
    return ClubDocument.objects.create(
        club=document.club,
        title=document.title,
        description=document.description,
        category=document.category,
        file=new_file,
        uploaded_by=uploaded_by,
        expiry_date=document.expiry_date,
        status=document.status,
        notes=notes or f"Replaced document {document.id}",
    )


def archive_document(document):
    if document.status == ClubDocument.Status.ARCHIVED:
        raise ValueError("Document is already archived.")
    document.status = ClubDocument.Status.ARCHIVED
    document.save(update_fields=["status", "updated_at"])


def mark_compliance_completed(compliance_item, user):
    if compliance_item.completed:
        raise ValueError("Compliance task is already completed.")
    if compliance_item.status == ComplianceChecklist.Status.OVERDUE:
        compliance_item.status = ComplianceChecklist.Status.COMPLETED
    elif compliance_item.status in (
        ComplianceChecklist.Status.PENDING,
        ComplianceChecklist.Status.IN_PROGRESS,
        ComplianceChecklist.Status.OVERDUE,
    ):
        compliance_item.status = ComplianceChecklist.Status.COMPLETED
    else:
        raise ValueError("Cannot complete a task in its current status.")
    compliance_item.completed = True
    compliance_item.completed_by = user
    compliance_item.completed_at = timezone.now()
    compliance_item.save(
        update_fields=[
            "status",
            "completed",
            "completed_by",
            "completed_at",
            "updated_at",
        ]
    )


def reopen_compliance_task(compliance_item):
    if not compliance_item.completed:
        raise ValueError("Only completed tasks can be reopened.")
    compliance_item.completed = False
    compliance_item.completed_by = None
    compliance_item.completed_at = None
    compliance_item.status = ComplianceChecklist.Status.IN_PROGRESS
    compliance_item.save(
        update_fields=[
            "status",
            "completed",
            "completed_by",
            "completed_at",
            "updated_at",
        ]
    )


def publish_announcement(announcement):
    if announcement.is_published:
        raise ValueError("Announcement is already published.")
    if announcement.expires_at and announcement.expires_at <= timezone.now():
        raise ValueError("Cannot publish an announcement that has already expired.")
    announcement.is_published = True
    announcement.published_at = timezone.now()
    announcement.save(update_fields=["is_published", "published_at", "updated_at"])
    CommunicationLog.objects.create(
        club=announcement.club,
        communication_type=CommunicationLog.CommunicationType.ANNOUNCEMENT,
        title=announcement.title,
        audience=announcement.audience,
        sender=announcement.created_by,
        status=CommunicationLog.Status.SENT,
        metadata={"announcement_id": announcement.id},
        related_announcement=announcement,
    )


def unpublish_announcement(announcement):
    if not announcement.is_published:
        raise ValueError("Announcement is not published.")
    announcement.is_published = False
    announcement.save(update_fields=["is_published", "updated_at"])


def expire_announcements():
    now = timezone.now()
    Announcement.objects.filter(
        is_published=True,
        expires_at__lte=now,
        is_deleted=False,
    ).update(is_published=False)


def update_overdue_compliance_tasks():
    today = timezone.now().date()
    ComplianceChecklist.objects.filter(
        completed=False,
        due_date__lt=today,
        status__in=[
            ComplianceChecklist.Status.PENDING,
            ComplianceChecklist.Status.IN_PROGRESS,
        ],
    ).update(status=ComplianceChecklist.Status.OVERDUE)


def mark_expired_documents():
    today = timezone.now().date()
    ClubDocument.objects.filter(
        expiry_date__lt=today,
        status=ClubDocument.Status.ACTIVE,
        is_deleted=False,
    ).update(status=ClubDocument.Status.EXPIRED)
