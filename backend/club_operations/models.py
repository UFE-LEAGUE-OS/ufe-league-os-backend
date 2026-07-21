from django.conf import settings
from django.core.exceptions import ValidationError
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


class SponsorCampaign(models.Model):
    class CampaignType(models.TextChoices):
        MATCHDAY = "MATCHDAY", "Matchday Activation"
        DIGITAL = "DIGITAL", "Digital Campaign"
        COMMUNITY = "COMMUNITY", "Community Activation"
        HOSPITALITY = "HOSPITALITY", "Hospitality Event"
        MEDIA = "MEDIA", "Media Campaign"
        MERCHANDISING = "MERCHANDISING", "Merchandising"
        OTHER = "OTHER", "Other"

    class CampaignStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        SCHEDULED = "SCHEDULED", "Scheduled"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        ARCHIVED = "ARCHIVED", "Archived"

    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="sponsor_campaigns",
    )
    sponsor = models.ForeignKey(
        "sponsorships.SponsorAccount",
        on_delete=models.CASCADE,
        related_name="club_campaigns",
    )
    sponsor_package = models.ForeignKey(
        "sponsorships.SponsorPackage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="club_campaigns",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    objective = models.TextField(blank=True)
    campaign_type = models.CharField(
        max_length=20, choices=CampaignType.choices, default=CampaignType.MATCHDAY
    )
    status = models.CharField(
        max_length=20, choices=CampaignStatus.choices, default=CampaignStatus.DRAFT
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    budget = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expected_reach = models.PositiveIntegerField(default=0)
    branding_requirements = models.TextField(blank=True)
    deliverables = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_sponsor_campaigns",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        indexes = [
            models.Index(fields=["club", "status"]),
            models.Index(fields=["sponsor", "status"]),
            models.Index(fields=["start_date", "end_date"]),
            models.Index(fields=["campaign_type"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.sponsor.name}"


class CampaignAssignment(models.Model):
    class ActivationStatus(models.TextChoices):
        PLANNED = "PLANNED", "Planned"
        ACTIVE = "ACTIVE", "Active"
        EXECUTED = "EXECUTED", "Executed"
        PENDING = "PENDING", "Pending Review"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    campaign = models.ForeignKey(
        SponsorCampaign,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    match = models.ForeignKey(
        "dashboards.Match",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="campaign_assignments",
    )
    sponsor_package = models.ForeignKey(
        "sponsorships.SponsorPackage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaign_assignments",
    )
    activation_notes = models.TextField(blank=True)
    branding_locations = models.TextField(
        blank=True, help_text="e.g., perimeter boards, LED boards"
    )
    booth_requirements = models.TextField(blank=True)
    banner_locations = models.TextField(blank=True)
    led_board_allocation = models.CharField(max_length=255, blank=True)
    vip_allocation = models.PositiveIntegerField(default=0)
    activation_status = models.CharField(
        max_length=20,
        choices=ActivationStatus.choices,
        default=ActivationStatus.PLANNED,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_campaign_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["campaign", "match"]),
            models.Index(fields=["activation_status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "match"],
                condition=models.Q(match__isnull=False),
                name="unique_campaign_match_assignment",
            )
        ]

    def clean(self):
        if self.match_id and self.campaign.club_id not in [
            self.match.home_club_id,
            self.match.away_club_id,
        ]:
            raise ValidationError(
                {"match": "Match does not belong to the campaign's club."}
            )
        if (
            self.match_id
            and self.match.match_date < self.campaign.start_date
            or self.match.match_date > self.campaign.end_date
        ):
            raise ValidationError(
                {"match": "Match date is outside the campaign date range."}
            )

    def __str__(self):
        target = self.match or "No match"
        return f"{self.campaign.name} -> {target}"


class MatchdayOperationTask(models.Model):
    class TaskCategory(models.TextChoices):
        TICKETING = "TICKETING", "Ticketing"
        SECURITY = "SECURITY", "Security"
        MEDICAL = "MEDICAL", "Medical"
        MARKETING = "MARKETING", "Marketing"
        SPONSORSHIP = "SPONSORSHIP", "Sponsorship"
        HOSPITALITY = "HOSPITALITY", "Hospitality"
        STADIUM_PREP = "STADIUM_PREP", "Stadium Preparation"
        ACCREDITATION = "ACCREDITATION", "Accreditation"
        VOLUNTEERS = "VOLUNTEERS", "Volunteers"
        MEDIA = "MEDIA", "Media"
        TRANSPORT = "TRANSPORT", "Transport"
        CATERING = "CATERING", "Catering"
        OTHER = "OTHER", "Other"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class TaskStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        OVERDUE = "OVERDUE", "Overdue"

    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="matchday_tasks",
    )
    match = models.ForeignKey(
        "dashboards.Match",
        on_delete=models.CASCADE,
        related_name="matchday_tasks",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=30, choices=TaskCategory.choices, default=TaskCategory.STADIUM_PREP
    )
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.MEDIUM
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matchday_tasks_assigned",
    )
    due_date = models.DateField(null=True, blank=True)
    due_time = models.TimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=TaskStatus.choices, default=TaskStatus.PENDING
    )
    completion_notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_matchday_tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_matchday_tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_date", "priority", "-created_at"]
        indexes = [
            models.Index(fields=["club", "status"]),
            models.Index(fields=["match", "status"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["category", "status"]),
            models.Index(fields=["due_date"]),
        ]

    def __str__(self):
        return f"{self.club.name} - {self.title} ({self.get_status_display()})"


class TicketingOfficerAssignment(models.Model):
    class AssignmentRole(models.TextChoices):
        GATE_CONTROLLER = "GATE_CONTROLLER", "Gate Controller"
        TICKET_SCANNER = "TICKET_SCANNER", "Ticket Scanner"
        TICKET_SELLER = "TICKET_SELLER", "Ticket Seller"
        CUSTOMER_SERVICE = "CUSTOMER_SERVICE", "Customer Service"
        SUPERVISOR = "SUPERVISOR", "Ticketing Supervisor"

    class AssignmentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CHECKED_IN = "CHECKED_IN", "Checked In"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        NO_SHOW = "NO_SHOW", "No Show"

    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="ticketing_officer_assignments",
    )
    match = models.ForeignKey(
        "dashboards.Match",
        on_delete=models.CASCADE,
        related_name="ticketing_officer_assignments",
    )
    officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ticketing_assignments",
    )
    assignment_role = models.CharField(
        max_length=30,
        choices=AssignmentRole.choices,
        default=AssignmentRole.TICKET_SCANNER,
    )
    gate_allocation = models.CharField(max_length=100, blank=True)
    shift_start = models.DateTimeField()
    shift_end = models.DateTimeField()
    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.PENDING,
    )
    notes = models.TextField(blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="assigned_officer_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["match__match_date", "shift_start", "officer__email"]
        indexes = [
            models.Index(fields=["club", "match"]),
            models.Index(fields=["officer", "status"]),
            models.Index(fields=["match", "status"]),
            models.Index(fields=["assignment_role"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["match", "officer", "assignment_role"],
                name="unique_officer_match_role_assignment",
            )
        ]

    def clean(self):
        if self.shift_end <= self.shift_start:
            raise ValidationError({"shift_end": "Shift end must be after shift start."})
        overlapping = TicketingOfficerAssignment.objects.filter(
            officer=self.officer,
            status__in=[
                TicketingOfficerAssignment.AssignmentStatus.PENDING,
                TicketingOfficerAssignment.AssignmentStatus.CONFIRMED,
                TicketingOfficerAssignment.AssignmentStatus.CHECKED_IN,
            ],
            shift_start__lt=self.shift_end,
            shift_end__gt=self.shift_start,
        ).exclude(id=self.id)
        if overlapping.exists():
            raise ValidationError(
                {"officer": "Officer has an overlapping shift assignment."}
            )
        if self.officer_id and self.club_id:
            if not self.officer.club_id == self.club_id:
                raise ValidationError(
                    {"officer": "Officer must belong to the same club."}
                )

    def __str__(self):
        return f"{self.officer.get_full_name()} - {self.match} ({self.get_assignment_role_display()})"


class MatchdayReport(models.Model):
    class ReportStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        REVIEWED = "REVIEWED", "Reviewed"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    match = models.ForeignKey(
        "dashboards.Match",
        on_delete=models.CASCADE,
        related_name="matchday_reports",
    )
    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="matchday_reports",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="submitted_matchday_reports",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_matchday_reports",
    )
    status = models.CharField(
        max_length=20, choices=ReportStatus.choices, default=ReportStatus.DRAFT
    )
    review_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    attendance_tickets_sold = models.PositiveIntegerField(default=0)
    attendance_complimentary_tickets = models.PositiveIntegerField(default=0)
    attendance_estimated = models.PositiveIntegerField(default=0)

    revenue_ticket = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    revenue_merchandise = models.DecimalField(
        max_digits=14, decimal_places=2, default=0
    )
    revenue_other = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    sponsor_campaigns_executed = models.TextField(blank=True)
    sponsor_visibility = models.TextField(blank=True)
    deliverables_completed = models.TextField(blank=True)

    incidents = models.TextField(blank=True)
    medical_incidents = models.TextField(blank=True)
    security_incidents = models.TextField(blank=True)
    delays = models.TextField(blank=True)

    stadium_issues = models.TextField(blank=True)
    equipment_issues = models.TextField(blank=True)

    photos_metadata = models.JSONField(default=list, blank=True)
    documents = models.JSONField(default=list, blank=True)

    successes = models.TextField(blank=True)
    challenges = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["club", "status"]),
            models.Index(fields=["match", "status"]),
            models.Index(fields=["submitted_by", "status"]),
            models.Index(fields=["submitted_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["match", "club"],
                condition=models.Q(is_deleted=False),
                name="unique_matchday_report_per_club_match",
            )
        ]

    def __str__(self):
        return f"{self.club.name} - {self.match} ({self.get_status_display()})"


class ClubOperationAuditLog(models.Model):
    class ActionType(models.TextChoices):
        CAMPAIGN_CREATED = "CAMPAIGN_CREATED", "Campaign Created"
        CAMPAIGN_UPDATED = "CAMPAIGN_UPDATED", "Campaign Updated"
        CAMPAIGN_ARCHIVED = "CAMPAIGN_ARCHIVED", "Campaign Archived"
        CAMPAIGN_DELETED = "CAMPAIGN_DELETED", "Campaign Deleted"
        CAMPAIGN_TAGGED = "CAMPAIGN_TAGGED", "Campaign Tagged"
        CAMPAIGN_REMOVED = "CAMPAIGN_REMOVED", "Campaign Removed"
        CAMPAIGN_ASSIGNMENT_UPDATED = (
            "CAMPAIGN_ASSIGNMENT_UPDATED",
            "Campaign Assignment Updated",
        )
        TASK_CREATED = "TASK_CREATED", "Task Created"
        TASK_UPDATED = "TASK_UPDATED", "Task Updated"
        TASK_COMPLETED = "TASK_COMPLETED", "Task Completed"
        OFFICER_ASSIGNED = "OFFICER_ASSIGNED", "Officer Assigned"
        OFFICER_ASSIGNMENT_UPDATED = (
            "OFFICER_ASSIGNMENT_UPDATED",
            "Officer Assignment Updated",
        )
        OFFICER_REMOVED = "OFFICER_REMOVED", "Officer Removed"
        REPORT_SUBMITTED = "REPORT_SUBMITTED", "Report Submitted"
        REPORT_UPDATED = "REPORT_UPDATED", "Report Updated"
        REPORT_APPROVED = "REPORT_APPROVED", "Report Approved"
        REPORT_REJECTED = "REPORT_REJECTED", "Report Rejected"

    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="club_operation_audit_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="club_operation_audit_logs",
    )
    action = models.CharField(max_length=50, choices=ActionType.choices)
    target_object_id = models.PositiveIntegerField(null=True, blank=True)
    target_content_type = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["club", "action"]),
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self):
        return f"{self.club.name} - {self.action} - {self.timestamp}"
