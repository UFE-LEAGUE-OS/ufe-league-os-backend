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

    class Gender(models.TextChoices):
        MALE = "Male", "Male"
        FEMALE = "Female", "Female"
        PREFER_NOT_TO_SAY = "Prefer not to say", "Prefer not to say"

    username = None

    email = models.EmailField(unique=True)

    phone_number = models.CharField(max_length=20, unique=True, blank=True, null=True)

    public_handle = models.SlugField(max_length=80, blank=True)
    location = models.CharField(max_length=150, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(
        max_length=30,
        choices=Gender.choices,
        default=Gender.PREFER_NOT_TO_SAY,
    )
    favourite_sport = models.CharField(max_length=50, blank=True)
    bio = models.TextField(blank=True)

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

        league_scopes = getattr(self, "league_admin_scopes", None)

        if self.pk and league_scopes is not None:
            if league_scopes.filter(is_active=True).exclude(role="VIEWER").exists():
                roles.add(self.Role.LEAGUE_ADMIN)

        union_memberships = getattr(self, "union_workspace_memberships", None)

        if self.pk and union_memberships is not None:
            active_union_memberships = union_memberships.filter(
                is_active=True,
                workspace__status="ACTIVE",
            )

            management_union_roles = (
                "OWNER",
                "UNION_ADMIN",
                "COMPETITIONS_MANAGER",
                "REGISTRAR",
                "REFEREE_MANAGER",
                "FINANCE_OFFICER",
                "COMMUNICATIONS_OFFICER",
                "TICKETING_OFFICER",
                "TECHNICAL_OFFICER",
            )

            if active_union_memberships.filter(
                role__in=management_union_roles,
            ).exists():
                roles.add(self.Role.UNION_ADMIN)

            if active_union_memberships.filter(
                role="MATCH_OFFICIAL",
            ).exists():
                roles.add(self.Role.REFEREE)

        return roles

    def has_role(self, role):
        return role in self.roles


class RoleApproval(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="role_approvals",
    )
    requested_role = models.CharField(max_length=50, default="")
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    approved_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="approvals"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        user_email = self.user.email if self.user else "unknown"
        return f"{user_email} - {self.requested_role} - {self.status}"


class ClubAdminScope(models.Model):
    """
    Defines a user's administrative scope and sub-role within a specific club.

    This allows for granular permissions beyond the base CLUB_ADMIN role,
    enabling roles like Chairman, Treasurer, Team Manager, etc.
    """

    class Role(models.TextChoices):
        CLUB_ADMIN = "CLUB_ADMIN", "Club Administrator"
        CHAIRMAN = "CHAIRMAN", "Chairman"
        TREASURER = "TREASURER", "Treasurer"
        TEAM_MANAGER = "TEAM_MANAGER", "Team Manager"
        TICKETING_OFFICER = "TICKETING_OFFICER", "Ticketing Officer"
        CUSTOM = "CUSTOM", "Custom"

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="club_admin_scopes",
    )
    club = models.ForeignKey("accounts.Club", on_delete=models.CASCADE)
    role = models.CharField(
        max_length=50, choices=Role.choices, default=Role.CLUB_ADMIN
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "club")
        ordering = ["club__name", "user__email"]


class Club(models.Model):
    class Sport(models.TextChoices):
        RUGBY = "RUGBY", "Rugby"
        FOOTBALL = "FOOTBALL", "Football"
        BASKETBALL = "BASKETBALL", "Basketball"
        MULTI_SPORT = "MULTI_SPORT", "Multi-Sport"
        OTHER = "OTHER", "Other"

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=150, unique=True)
    short_name = models.CharField(max_length=80, blank=True)
    sport = models.CharField(
        max_length=30,
        choices=Sport.choices,
        default=Sport.OTHER,
    )
    logo = models.ImageField(upload_to="clubs/logos/", blank=True, null=True)
    banner = models.ImageField(upload_to="clubs/banners/", blank=True, null=True)
    primary_color = models.CharField(max_length=20, blank=True)
    secondary_color = models.CharField(max_length=20, blank=True)
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


class Venue(models.Model):
    """Club-managed venue for matchday and scheduling."""

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="venues")
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True)
    pitch_count = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("club", "name")
        ordering = ["club__name", "name"]

    def __str__(self):
        return f"{self.club.name} - {self.name}"


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="notification_preferences"
    )
    email_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    membership_updates = models.BooleanField(default=True)
    ticket_updates = models.BooleanField(default=True)
    sponsorship_updates = models.BooleanField(default=True)
    governance_updates = models.BooleanField(default=True)

    class Meta:
        ordering = ["user__email"]

    def __str__(self):
        return f"{self.user.email} notification preferences"


class InterestPreference(models.Model):
    class Visibility(models.TextChoices):
        PUBLIC = "PUBLIC", "Public"
        FOLLOWERS_ONLY = "FOLLOWERS_ONLY", "Followers Only"
        PRIVATE = "PRIVATE", "Private"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="interest_preferences"
    )
    interested_in_clubs = models.BooleanField(default=True)
    interested_in_leagues = models.BooleanField(default=True)
    interested_in_unions = models.BooleanField(default=True)
    interested_in_national_teams = models.BooleanField(default=False)
    interested_in_transfers = models.BooleanField(default=False)
    interested_in_highlights = models.BooleanField(default=True)
    interested_in_tickets = models.BooleanField(default=True)
    interested_in_merchandise = models.BooleanField(default=False)
    profile_visibility = models.CharField(
        max_length=20, choices=Visibility.choices, default=Visibility.PUBLIC
    )
    show_followed_teams = models.BooleanField(default=True)
    show_attended_matches = models.BooleanField(default=True)
    activity_visibility = models.CharField(
        max_length=20, choices=Visibility.choices, default=Visibility.FOLLOWERS_ONLY
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__email"]

    def __str__(self):
        return f"{self.user.email} interests"


class Follow(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="follows")
    content_type = models.CharField(max_length=50, default="")
    object_id = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "content_type", "object_id")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} follows {self.content_type}:{self.object_id}"


class FeedItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="feed_items")
    content_type = models.CharField(max_length=50, default="")
    object_id = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="feed/", blank=True, null=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return f"{self.user.email} feed item: {self.title}"


class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="UGX")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__email"]

    def __str__(self):
        return f"{self.user.email} wallet"


class PaymentHistory(models.Model):
    wallet = models.ForeignKey(
        Wallet,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default="UGX")
    status = models.CharField(max_length=30, default="PENDING")
    reference = models.CharField(max_length=100, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        user_email = self.wallet.user.email if self.wallet else "unknown"
        return f"{user_email} payment {self.reference}"


class Notification(models.Model):
    """In-app notification for users."""

    class Category(models.TextChoices):
        SYSTEM = "SYSTEM", "System"
        MEMBERSHIP = "MEMBERSHIP", "Membership"
        TICKETING = "TICKETING", "Ticketing"
        SPONSORSHIP = "SPONSORSHIP", "Sponsorship"
        GOVERNANCE = "GOVERNANCE", "Governance"
        CLUB = "CLUB", "Club"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        NORMAL = "NORMAL", "Normal"
        HIGH = "HIGH", "High"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    category = models.CharField(
        max_length=30, choices=Category.choices, default=Category.SYSTEM
    )
    title = models.CharField(max_length=150)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.title}"


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
    purpose = models.CharField(max_length=30, choices=Purpose.choices)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.purpose} - {self.code}"

    @property
    def is_expired(self):
        """Check if the OTP has expired."""
        from django.utils import timezone
        return timezone.now() > self.expires_at
