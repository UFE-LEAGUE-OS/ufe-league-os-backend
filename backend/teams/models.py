from django.db import models

from accounts.models import User, Club
from dashboards.models import Competition


class Team(models.Model):
    """Represents a team within a club (e.g., First Team, Youth Team, U-17)."""

    class TeamType(models.TextChoices):
        FIRST_TEAM = "FIRST_TEAM", "First Team"
        RESERVE = "RESERVE", "Reserve Team"
        YOUTH = "YOUTH", "Youth Team"
        U20 = "U20", "U-20"
        U17 = "U17", "U-17"
        U15 = "U15", "U-15"
        WOMEN = "WOMEN", "Women's Team"
        OTHER = "OTHER", "Other"

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name="teams",
    )
    name = models.CharField(max_length=150)
    short_name = models.CharField(max_length=50, blank=True)
    team_type = models.CharField(
        max_length=20,
        choices=TeamType.choices,
        default=TeamType.FIRST_TEAM,
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    logo = models.ImageField(upload_to="teams/logos/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["club__name", "team_type", "name"]
        unique_together = ["club", "name"]
        indexes = [
            models.Index(fields=["club", "is_active"]),
            models.Index(fields=["team_type"]),
        ]

    def __str__(self):
        return f"{self.club.name} - {self.name}"


class Squad(models.Model):
    """
    Represents a squad for a specific competition/season.
    A team can have multiple squads for different competitions.
    """

    class SquadStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="squads",
    )
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name="squads",
    )
    name = models.CharField(max_length=150)
    season = models.CharField(max_length=50, help_text="e.g., 2025/26")
    member_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=SquadStatus.choices,
        default=SquadStatus.DRAFT,
    )
    submitted_at = models.DateTimeField(blank=True, null=True)
    submitted_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submitted_squads",
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_squads",
    )
    rejection_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["team", "competition", "season"]
        indexes = [
            models.Index(fields=["team", "competition", "season"]),
            models.Index(fields=["status", "-submitted_at"]),
        ]

    def __str__(self):
        return f"{self.team.name} - {self.competition.name} ({self.season})"


class PlayerRegistration(models.Model):
    """
    Represents a player's registration with a club.
    This is the primary record for player eligibility.
    """

    class RegistrationStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        SUSPENDED = "SUSPENDED", "Suspended"
        EXPIRED = "EXPIRED", "Expired"

    class PlayerType(models.TextChoices):
        PROFESSIONAL = "PROFESSIONAL", "Professional"
        SEMI_PRO = "SEMI_PRO", "Semi-Professional"
        AMATEUR = "AMATEUR", "Amateur"
        YOUTH = "YOUTH", "Youth"
        LOAN = "LOAN", "Loan Player"

    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="player_registrations",
        help_text="Link to user account if player has one",
    )
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name="player_registrations",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="player_registrations",
    )
    registration_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique registration number assigned by club",
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=100)
    position = models.CharField(
        max_length=50,
        help_text="Primary playing position",
    )
    secondary_positions = models.JSONField(default=list, blank=True)
    player_type = models.CharField(
        max_length=20,
        choices=PlayerType.choices,
        default=PlayerType.PROFESSIONAL,
    )
    jersey_number = models.PositiveIntegerField(blank=True, null=True)
    height_cm = models.PositiveIntegerField(blank=True, null=True)
    weight_kg = models.PositiveIntegerField(blank=True, null=True)
    preferred_foot = models.CharField(
        max_length=20,
        choices=[("LEFT", "Left"), ("RIGHT", "Right"), ("BOTH", "Both")],
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=RegistrationStatus.choices,
        default=RegistrationStatus.ACTIVE,
    )
    registered_date = models.DateField()
    expiry_date = models.DateField(blank=True, null=True)
    transfer_window = models.CharField(
        max_length=50,
        blank=True,
        help_text="e.g., Summer 2025, Winter 2025",
    )
    previous_club = models.CharField(max_length=200, blank=True)
    contract_until = models.DateField(blank=True, null=True)
    is_captain = models.BooleanField(default=False)
    is_vice_captain = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["club__name", "team__name", "registration_number"]
        indexes = [
            models.Index(fields=["club", "status"]),
            models.Index(fields=["team", "status"]),
            models.Index(fields=["registration_number"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.registration_number})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class SquadMember(models.Model):
    """
    Links a player to a squad with squad-specific details.
    """

    squad = models.ForeignKey(
        Squad,
        on_delete=models.CASCADE,
        related_name="members",
    )
    player = models.ForeignKey(
        PlayerRegistration,
        on_delete=models.CASCADE,
        related_name="squad_memberships",
    )
    jersey_number = models.PositiveIntegerField(blank=True, null=True)
    position = models.CharField(max_length=50)
    is_captain = models.BooleanField(default=False)
    is_vice_captain = models.BooleanField(default=False)
    joined_date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["jersey_number", "player__last_name"]
        unique_together = ["squad", "player"]
        indexes = [
            models.Index(fields=["squad", "player"]),
        ]

    def __str__(self):
        return f"{self.player.full_name} - {self.squad.name}"


class StaffMember(models.Model):
    """
    Represents club staff (coaches, medical staff, officials).
    """

    class StaffRole(models.TextChoices):
        HEAD_COACH = "HEAD_COACH", "Head Coach"
        ASSISTANT_COACH = "ASSISTANT_COACH", "Assistant Coach"
        GOALKEEPING_COACH = "GOALKEEPING_COACH", "Goalkeeping Coach"
        FITNESS_COACH = "FITNESS_COACH", "Fitness Coach"
        MEDICAL_OFFICER = "MEDICAL_OFFICER", "Medical Officer"
        PHYSIOTHERAPIST = "PHYSIOTHERAPIST", "Physiotherapist"
        TEAM_MANAGER = "TEAM_MANAGER", "Team Manager"
        CHAIRMAN = "CHAIRMAN", "Chairman"
        DIRECTOR_OF_FOOTBALL = "DIRECTOR_OF_FOOTBALL", "Director of Football"
        SCOUT = "SCOUT", "Scout"
        ANALYST = "ANALYST", "Performance Analyst"
        OTHER = "OTHER", "Other"

    class EmploymentType(models.TextChoices):
        FULL_TIME = "FULL_TIME", "Full-Time"
        PART_TIME = "PART_TIME", "Part-Time"
        CONTRACT = "CONTRACT", "Contract"
        VOLUNTEER = "VOLUNTEER", "Volunteer"

    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="staff_profiles",
    )
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name="staff_members",
    )
    team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="staff_members",
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(
        max_length=30,
        choices=StaffRole.choices,
    )
    custom_role = models.CharField(
        max_length=100,
        blank=True,
        help_text="Use if role is OTHER",
    )
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME,
    )
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    qualification = models.TextField(blank=True)
    experience_years = models.PositiveIntegerField(blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["club__name", "team__name", "role", "last_name"]
        indexes = [
            models.Index(fields=["club", "role"]),
            models.Index(fields=["team", "role"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.get_role_display()}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class PlayerTransfer(models.Model):
    """
    Tracks player transfers between clubs.
    """

    class TransferStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class TransferType(models.TextChoices):
        PERMANENT = "PERMANENT", "Permanent Transfer"
        LOAN = "LOAN", "Loan"
        FREE_TRANSFER = "FREE_TRANSFER", "Free Transfer"
        END_OF_LOAN = "END_OF_LOAN", "End of Loan"

    transfer_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique transfer reference number",
    )
    player = models.ForeignKey(
        PlayerRegistration,
        on_delete=models.CASCADE,
        related_name="transfers",
    )
    from_club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name="outgoing_transfers",
    )
    to_club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name="incoming_transfers",
    )
    transfer_type = models.CharField(
        max_length=20,
        choices=TransferType.choices,
    )
    transfer_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Transfer fee in case of permanent transfer",
    )
    currency = models.CharField(max_length=3, default="USD")
    transfer_date = models.DateField()
    contract_until = models.DateField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=TransferStatus.choices,
        default=TransferStatus.PENDING,
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="requested_transfers",
    )
    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_transfers",
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True)
    documents = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-transfer_date", "-created_at"]
        indexes = [
            models.Index(fields=["player", "status"]),
            models.Index(fields=["from_club", "to_club"]),
            models.Index(fields=["transfer_date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Transfer: {self.player.full_name} ({self.from_club} → {self.to_club})"


class SquadSubmission(models.Model):
    """
    Submission of a squad to the union/league for approval.
    This is the official squad sheet submitted for a competition.
    """

    class SubmissionStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        AMENDED = "AMENDED", "Amended"

    squad = models.ForeignKey(
        Squad,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    submission_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique submission reference",
    )
    status = models.CharField(
        max_length=20,
        choices=SubmissionStatus.choices,
        default=SubmissionStatus.DRAFT,
    )
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="squad_submissions",
    )
    submitted_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_squad_submissions",
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True)
    iteration = models.PositiveIntegerField(default=1, help_text="Version number")
    previous_submission = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="amendments",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["squad", "status"]),
            models.Index(fields=["status", "-submitted_at"]),
            models.Index(fields=["submission_number"]),
        ]

    def __str__(self):
        return f"{self.submission_number} - {self.get_status_display()}"
