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
