from django.conf import settings
from django.db import models


class ClubDocument(models.Model):
    class Category(models.TextChoices):
        CONSTITUTION = "CONSTITUTION", "Constitution"
        REGISTRATION_CERTIFICATE = "REGISTRATION_CERT", "Registration Certificate"
        TAX_CERTIFICATE = "TAX_CERT", "Tax Certificate"
        INSURANCE = "INSURANCE", "Insurance"
        SAFEGUARDING_POLICY = "SAFEGUARDING", "Safeguarding Policy"
        COACH_CERTIFICATION = "COACH_CERT", "Coach Certification"
        PLAYER_REGISTRATION = "PLAYER_REG", "Player Registration"
        MEDICAL = "MEDICAL", "Medical"
        MATCHDAY = "MATCHDAY", "Matchday"
        FINANCIAL = "FINANCIAL", "Financial"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        PENDING_REVIEW = "PENDING_REVIEW", "Pending Review"
        EXPIRED = "EXPIRED", "Expired"
        ARCHIVED = "ARCHIVED", "Archived"

    ALLOWED_FILE_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "image/jpeg",
        "image/png",
    }
    MAX_FILE_SIZE_MB = 10

    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="club_documents",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=30, choices=Category.choices)
    file = models.FileField(upload_to="club/documents/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_club_documents",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.ACTIVE
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["club", "category"],
                condition=models.Q(status="ACTIVE", is_deleted=False),
                name="unique_active_document_per_club_category",
            )
        ]

    def __str__(self):
        return f"{self.club.name} - {self.category} - {self.title}"


class ComplianceChecklist(models.Model):
    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        OVERDUE = "OVERDUE", "Overdue"

    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="compliance_checklists",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100)
    due_date = models.DateField()
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.MEDIUM
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    completed = models.BooleanField(default=False)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_compliance_tasks",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_date", "priority"]

    def __str__(self):
        return f"{self.club.name} - {self.title}"


class Announcement(models.Model):
    class Audience(models.TextChoices):
        EVERYONE = "EVERYONE", "Everyone"
        PLAYERS = "PLAYERS", "Players"
        COACHES = "COACHES", "Coaches"
        TEAM_MANAGERS = "TEAM_MANAGERS", "Team Managers"
        CLUB_STAFF = "CLUB_STAFF", "Club Staff"
        PARENTS = "PARENTS", "Parents"
        MATCH_OFFICIALS = "MATCH_OFFICIALS", "Match Officials"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        NORMAL = "NORMAL", "Normal"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="announcements",
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    audience = models.CharField(
        max_length=30, choices=Audience.choices, default=Audience.EVERYONE
    )
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.NORMAL
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="club_announcements",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    attachment = models.FileField(
        upload_to="club/announcements/", blank=True, null=True
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.club.name} - {self.title}"


class CommunicationLog(models.Model):
    class CommunicationType(models.TextChoices):
        ANNOUNCEMENT = "ANNOUNCEMENT", "Announcement"
        EMAIL = "EMAIL", "Email"
        SMS = "SMS", "SMS"
        PUSH_NOTIFICATION = "PUSH_NOTIFICATION", "Push Notification"
        IN_APP_NOTIFICATION = "IN_APP_NOTIFICATION", "In-App Notification"

    class Status(models.TextChoices):
        SENT = "SENT", "Sent"
        DELIVERED = "DELIVERED", "Delivered"
        FAILED = "FAILED", "Failed"

    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="communication_logs",
    )
    communication_type = models.CharField(
        max_length=30, choices=CommunicationType.choices
    )
    title = models.CharField(max_length=255)
    audience = models.CharField(max_length=30)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_communications",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SENT
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    related_announcement = models.ForeignKey(
        Announcement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_logs",
    )

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.club.name} - {self.communication_type} - {self.title}"
