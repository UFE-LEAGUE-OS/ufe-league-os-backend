from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


# Create your models here.
class User(AbstractUser):
    """Custom League OS user model. Uses email as the main internal login field"""

    class Role(models.TextChoices):
        FAN = "FAN", "Fan / Member"
        CLUB_ADMIN = "CLUB_ADMIN", "Club Admin"
        LEAGUE_ADMIN = "LEAGUE_ADMIN", "League Admin"
        UNION_ADMIN = "UNION_ADMIN", "Union / Federation Admin"
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
        REFEREE = "REFEREE", "Referee / Match Official"
        TICKETING_OFFICER = "TICKETING_OFFICER", "Ticketing Officer"
        SPONSOR = "SPONSOR", "Sponsor"

    class SponsorType(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Individual Sponsor"
        CORPORATE = "CORPORATE", "Corporate Sponsor"

    username = None

    email = models.EmailField(unique=True)

    phone_number = models.CharField(max_length=20, unique=True, blank=True, null=True)

    role = models.CharField(max_length=30, choices=Role.choices, default=Role.FAN)

    club = models.ForeignKey(
        "Club",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
    )

    is_sponsor = models.BooleanField(default=False)
    sponsor_type = models.CharField(
        max_length=20,
        choices=SponsorType.choices,
        blank=True,
        null=True,
    )

    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)

    is_email_verified = models.BooleanField(default=False)

    is_phone_verified = models.BooleanField(default=False)

    USERNAME_FIELD = "email"

    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def roles(self):
        roles = {self.role}

        if self.is_sponsor:
            roles.add(self.Role.SPONSOR)

        sponsor_memberships = getattr(self, "sponsor_memberships", None)

        if self.pk and sponsor_memberships is not None:
            if sponsor_memberships.filter(is_active=True).exists():
                roles.add(self.Role.SPONSOR)

        return roles

    def has_role(self, role):
        return role in self.roles


class Club(models.Model):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=150, unique=True)
    admin = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="administered_clubs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    """Store audit events for RBAC actions and access violations."""

    class Category(models.TextChoices):
        ACCESS_VIOLATION = "ACCESS_VIOLATION", "Access Violation"
        ROLE_CHANGE = "ROLE_CHANGE", "Role Change"
        GOVERNANCE = "GOVERNANCE", "Governance & Compliance"

    category = models.CharField(max_length=50, choices=Category.choices)
    actor = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        related_name="audit_logs",
        on_delete=models.SET_NULL,
    )
    target_user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        related_name="target_audit_logs",
        on_delete=models.SET_NULL,
    )
    action = models.CharField(max_length=100)
    path = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=10, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    ip_address = models.CharField(max_length=45, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        subject = self.target_user or self.actor
        return f"{self.category} {self.action} ({subject})"


class EmailOTP(models.Model):
    """Stores one-time password codes used for email verification"""

    class Purpose(models.TextChoices):
        EMAIL_VERIFICATION = "EMAIL_VERIFICATION", "Email Verification"
        PASSWORD_RESET = "PASSWORD_RESET", "Password Reset"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_otps")
    code = models.CharField(max_length=6)
    purpose = models.CharField(
        max_length=50, choices=Purpose.choices, default=Purpose.EMAIL_VERIFICATION
    )
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "purpose", "is_used"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.purpose} - {self.code}"

    @property
    def is_expired(self):
        from django.utils import timezone

        return timezone.now() >= self.expires_at


class Follow(models.Model):
    """
    Polymorphic follow model. A user can follow:
    - Club
    - League
    - Union
    - Competition (from dashboards)
    """

    class ContentType(models.TextChoices):
        CLUB = "CLUB", "Club"
        LEAGUE = "LEAGUE", "League"
        UNION = "UNION", "Union"
        COMPETITION = "COMPETITION", "Competition"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="follows")
    content_type = models.CharField(max_length=20, choices=ContentType.choices)
    object_id = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["user", "content_type", "object_id"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["user", "content_type"]),
        ]

    def __str__(self):
        return f"{self.user.email} follows {self.content_type}#{self.object_id}"

    @property
    def followed_object(self):
        """Return the actual followed object (Club, League, Union, or Competition)."""
        if self.content_type == self.ContentType.CLUB:
            from .models import Club

            return Club.objects.filter(id=self.object_id).first()
        elif self.content_type == self.ContentType.LEAGUE:
            from dashboards.models import League

            return League.objects.filter(id=self.object_id).first()
        elif self.content_type == self.ContentType.UNION:
            from dashboards.models import Union

            return Union.objects.filter(id=self.object_id).first()
        elif self.content_type == self.ContentType.COMPETITION:
            from dashboards.models import Competition

            return Competition.objects.filter(id=self.object_id).first()
        return None


class NotificationPreference(models.Model):
    """Per-user notification settings for different event types."""

    class EventType(models.TextChoices):
        MATCH_REMINDER = "MATCH_REMINDER", "Match Reminder"
        SCORE_UPDATE = "SCORE_UPDATE", "Score Update"
        FOLLOWED_TEAM_NEWS = "FOLLOWED_TEAM_NEWS", "Followed Team News"
        STANDINGS_CHANGE = "STANDINGS_CHANGE", "Standings Change"
        TICKET_OFFER = "TICKET_OFFER", "Ticket Offer"
        GENERAL_NEWS = "GENERAL_NEWS", "General News"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notification_preferences"
    )
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    email_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event_type"]
        unique_together = ["user", "event_type"]

    def __str__(self):
        return f"{self.user.email} - {self.event_type}"


class InterestPreference(models.Model):
    """
    Stores a fan's interest and privacy preferences.
    Allows fans to customize their League OS experience.
    """

    class PrivacyLevel(models.TextChoices):
        PUBLIC = "PUBLIC", "Public"
        FOLLOWERS_ONLY = "FOLLOWERS_ONLY", "Followers Only"
        PRIVATE = "PRIVATE", "Private"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="interest_preferences"
    )
    # Interests (fan chooses what content they care about)
    interested_in_clubs = models.BooleanField(default=True)
    interested_in_leagues = models.BooleanField(default=True)
    interested_in_unions = models.BooleanField(default=True)
    interested_in_national_teams = models.BooleanField(default=False)
    interested_in_transfers = models.BooleanField(default=False)
    interested_in_highlights = models.BooleanField(default=True)
    interested_in_tickets = models.BooleanField(default=True)
    interested_in_merchandise = models.BooleanField(default=False)

    # Privacy
    profile_visibility = models.CharField(
        max_length=20,
        choices=PrivacyLevel.choices,
        default=PrivacyLevel.PUBLIC,
    )
    show_followed_teams = models.BooleanField(default=True)
    show_attended_matches = models.BooleanField(default=True)
    activity_visibility = models.CharField(
        max_length=20,
        choices=PrivacyLevel.choices,
        default=PrivacyLevel.FOLLOWERS_ONLY,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} interests & privacy"


class Wallet(models.Model):
    """
    Fan wallet for tracking balance, virtual currency, and payment methods.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3, default="UGX")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} wallet ({self.currency} {self.balance})"


class PaymentHistory(models.Model):
    """
    Records deposits, withdrawals, purchases, and refunds.
    """

    class PaymentType(models.TextChoices):
        DEPOSIT = "DEPOSIT", "Deposit"
        WITHDRAWAL = "WITHDRAWAL", "Withdrawal"
        TICKET_PURCHASE = "TICKET_PURCHASE", "Ticket Purchase"
        MEMBERSHIP_FEE = "MEMBERSHIP_FEE", "Membership Fee"
        MERCHANDISE = "MERCHANDISE", "Merchandise"
        SPONSORSHIP = "SPONSORSHIP", "Sponsorship"
        REFUND = "REFUND", "Refund"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="payment_history"
    )
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="UGX")
    status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    reference = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "payment histories"
        indexes = [
            models.Index(fields=["user", "payment_type"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return (
            f"{self.user.email} - {self.payment_type} - {self.amount} {self.currency}"
        )


class FeedItem(models.Model):
    """
    Aggregated feed items for a user's personalized feed.
    Generated by the feed aggregation service based on follows and interests.
    """

    class ItemType(models.TextChoices):
        MATCH_RESULT = "MATCH_RESULT", "Match Result"
        UPCOMING_FIXTURE = "UPCOMING_FIXTURE", "Upcoming Fixture"
        STANDINGS_CHANGE = "STANDINGS_CHANGE", "Standings Change"
        NEWS = "NEWS", "News"
        TICKET_AVAILABLE = "TICKET_AVAILABLE", "Ticket Available"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="feed_items")
    item_type = models.CharField(max_length=30, choices=ItemType.choices)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    source_content_type = models.CharField(
        max_length=20, blank=True, help_text="e.g. CLUB, LEAGUE, COMPETITION, MATCH"
    )
    source_object_id = models.PositiveIntegerField(null=True, blank=True)
    source_name = models.CharField(max_length=200, blank=True)
    relevance_score = models.FloatField(default=0.0)
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-relevance_score", "-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["user", "item_type"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.item_type} - {self.title}"


class RoleApproval(models.Model):
    """
    Tracks pending approval requests for sensitive role assignments.

    When a SUPER_ADMIN assigns a sensitive role (UNION_ADMIN, SUPER_ADMIN),
    the change is not applied immediately. Instead, a RoleApproval record is
    created in PENDING status. Another SUPER_ADMIN must approve it before
    the role change takes effect.

    Status lifecycle:
        PENDING  →  APPROVED  (role applied)
        PENDING  →  REJECTED  (role denied)
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    # The user whose role is being changed
    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="role_approval_requests",
    )
    # The role being requested for the target user
    requested_role = models.CharField(max_length=30, choices=User.Role.choices)
    # The admin who initiated the request
    requested_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="role_approval_requests_made",
    )
    # The admin who approved/rejected the request
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="role_approval_reviews",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reason = models.TextField(
        blank=True,
        help_text="Reason for the role change request",
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason provided by the reviewer for rejection",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Role Approval Request"
        verbose_name_plural = "Role Approval Requests"
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["target_user", "status"]),
        ]

    def __str__(self):
        return (
            f"RoleApproval({self.target_user.email} -> {self.requested_role}"
            f" [{self.status}])"
        )
