from django.conf import settings
from django.db import models
from django.db.models import Q

# Create your models here.


class SponsorAccount(models.Model):
    """
    Represents a sponsorship account.

    A sponsor account can be:
    - Individual: one person sponsoring using their personal account.
    - Corporate: a company or brand such as Nile Special, KCB, MTN, etc.

    BRN and TIN are used as unique identifiers for corporate sponsors.
    They are unique per registration country to support future expansion
    outside Uganda.
    """

    class SponsorType(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Individual"
        CORPORATE = "CORPORATE", "Corporate"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_sponsor_accounts",
    )

    sponsor_type = models.CharField(
        max_length=20,
        choices=SponsorType.choices,
    )

    name = models.CharField(max_length=255)

    registration_country = models.CharField(
        max_length=2,
        default="UG",
        help_text="ISO 3166-1 alpha-2 country code where the sponsor is registered.",
    )

    brn = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Business Registration Number for corporate sponsors.",
    )

    tin = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Tax Identification Number for corporate sponsors.",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["sponsor_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["owner"]),
            models.Index(fields=["registration_country"]),
            models.Index(fields=["registration_country", "brn"]),
            models.Index(fields=["registration_country", "tin"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["registration_country", "brn"],
                condition=(
                    Q(sponsor_type="CORPORATE") & Q(brn__isnull=False) & ~Q(brn="")
                ),
                name="unique_corporate_sponsor_brn_per_country",
            ),
            models.UniqueConstraint(
                fields=["registration_country", "tin"],
                condition=(
                    Q(sponsor_type="CORPORATE") & Q(tin__isnull=False) & ~Q(tin="")
                ),
                name="unique_corporate_sponsor_tin_per_country",
            ),
            models.CheckConstraint(
                condition=(
                    Q(sponsor_type="INDIVIDUAL")
                    | (Q(brn__isnull=False) & ~Q(brn=""))
                    | (Q(tin__isnull=False) & ~Q(tin=""))
                ),
                name="corporate_sponsor_requires_brn_or_tin",
            ),
        ]

    def save(self, *args, **kwargs):
        if isinstance(self.registration_country, str):
            self.registration_country = (
                self.registration_country.strip().upper() or "UG"
            )

        if isinstance(self.brn, str):
            self.brn = self.brn.strip().upper() or None

        if isinstance(self.tin, str):
            self.tin = self.tin.strip().upper() or None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_sponsor_type_display()})"

    @property
    def is_individual(self):
        return self.sponsor_type == self.SponsorType.INDIVIDUAL

    @property
    def is_corporate(self):
        return self.sponsor_type == self.SponsorType.CORPORATE


class SponsorAccountMember(models.Model):
    """
    Links users to sponsor accounts.

    This allows a normal fan/user account to also manage sponsorship.
    """

    class MemberRole(models.TextChoices):
        OWNER = "OWNER", "Owner"
        ADMIN = "ADMIN", "Admin"
        FINANCE = "FINANCE", "Finance"
        VIEWER = "VIEWER", "Viewer"

    sponsor_account = models.ForeignKey(
        SponsorAccount,
        on_delete=models.CASCADE,
        related_name="members",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sponsor_memberships",
    )

    member_role = models.CharField(
        max_length=20,
        choices=MemberRole.choices,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sponsor_account", "user__email"]
        constraints = [
            models.UniqueConstraint(
                fields=["sponsor_account", "user"],
                name="unique_sponsor_account_member",
            )
        ]
        indexes = [
            models.Index(fields=["sponsor_account", "member_role"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.sponsor_account.name} - {self.member_role}"
