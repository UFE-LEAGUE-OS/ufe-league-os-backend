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

    username = None

    email = models.EmailField(unique=True)

    phone_number = models.CharField(max_length=20, unique=True, blank=True, null=True)

    role = models.CharField(max_length=30, choices=Role.choices, default=Role.FAN)

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
