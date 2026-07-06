from django.db import models


class Union(models.Model):
    """Represents a football union or federation (e.g., FUFA, CAF, FIFA)."""

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    logo = models.ImageField(upload_to="unions/logos/", blank=True, null=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    founded_year = models.PositiveIntegerField(blank=True, null=True)
    country = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class League(models.Model):
    """Represents a league within a union (e.g., Uganda Premier League)."""

    union = models.ForeignKey(Union, on_delete=models.CASCADE, related_name="leagues")
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    logo = models.ImageField(upload_to="leagues/logos/", blank=True, null=True)
    description = models.TextField(blank=True)
    founded_year = models.PositiveIntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Competition(models.Model):
    """Represents a competition/season within a league (e.g., UPL 2025/26)."""

    league = models.ForeignKey(
        League, on_delete=models.CASCADE, related_name="competitions"
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    season = models.CharField(max_length=50, help_text="e.g. 2025/26")
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "name"]
        unique_together = ["league", "slug"]

    def __str__(self):
        return f"{self.name} ({self.season})"


class Match(models.Model):
    """Represents a single fixture/match between two clubs."""

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        LIVE = "LIVE", "Live"
        COMPLETED = "COMPLETED", "Completed"
        POSTPONED = "POSTPONED", "Postponed"
        CANCELLED = "CANCELLED", "Cancelled"
        ABANDONED = "ABANDONED", "Abandoned"

    competition = models.ForeignKey(
        Competition, on_delete=models.CASCADE, related_name="matches"
    )
    home_club = models.ForeignKey(
        "accounts.Club", on_delete=models.CASCADE, related_name="home_matches"
    )
    away_club = models.ForeignKey(
        "accounts.Club", on_delete=models.CASCADE, related_name="away_matches"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SCHEDULED
    )
    match_date = models.DateTimeField()
    venue = models.CharField(max_length=300, blank=True)
    round = models.CharField(
        max_length=100, blank=True, help_text="Matchweek, round, or group stage"
    )
    home_score = models.PositiveIntegerField(blank=True, null=True)
    away_score = models.PositiveIntegerField(blank=True, null=True)
    home_halftime_score = models.PositiveIntegerField(blank=True, null=True)
    away_halftime_score = models.PositiveIntegerField(blank=True, null=True)
    has_extra_time = models.BooleanField(default=False)
    has_penalties = models.BooleanField(default=False)
    home_penalty_score = models.PositiveIntegerField(blank=True, null=True)
    away_penalty_score = models.PositiveIntegerField(blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["match_date"]
        verbose_name_plural = "matches"
        indexes = [
            models.Index(fields=["status", "match_date"]),
            models.Index(fields=["competition", "match_date"]),
        ]

    def __str__(self):
        return f"{self.home_club} vs {self.away_club} - {self.match_date.date()}"

    @property
    def is_fixture(self):
        return self.status in (self.Status.SCHEDULED, self.Status.POSTPONED)

    @property
    def has_result(self):
        return self.status == self.Status.COMPLETED and self.home_score is not None


class Standing(models.Model):
    """Represents league standings/table entries for a competition."""

    competition = models.ForeignKey(
        Competition, on_delete=models.CASCADE, related_name="standings"
    )
    club = models.ForeignKey(
        "accounts.Club", on_delete=models.CASCADE, related_name="standings"
    )
    position = models.PositiveIntegerField()
    played = models.PositiveIntegerField(default=0)
    won = models.PositiveIntegerField(default=0)
    drawn = models.PositiveIntegerField(default=0)
    lost = models.PositiveIntegerField(default=0)
    goals_for = models.PositiveIntegerField(default=0)
    goals_against = models.PositiveIntegerField(default=0)
    goal_difference = models.IntegerField(default=0)
    points = models.PositiveIntegerField(default=0)
    form = models.CharField(max_length=50, blank=True, help_text="e.g. WWDLW")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position"]
        unique_together = ["competition", "club"]

    def __str__(self):
        return f"{self.club.name} - {self.competition.name} (Pos: {self.position})"


UNION_WORKSPACE_ROLE_PERMISSIONS = {
    "OWNER": {
        "union.dashboard.view",
        "union.competitions.manage",
        "union.clubs.manage",
        "union.players.approve",
        "union.referees.manage",
        "union.finance.view",
        "union.reports.view",
        "union.communications.manage",
        "union.users.manage",
    },
    "UNION_ADMIN": {
        "union.dashboard.view",
        "union.competitions.manage",
        "union.clubs.manage",
        "union.players.approve",
        "union.referees.manage",
        "union.reports.view",
        "union.communications.manage",
        "union.users.manage",
    },
    "COMPETITIONS_MANAGER": {
        "union.dashboard.view",
        "union.competitions.manage",
        "union.reports.view",
    },
    "REGISTRAR": {
        "union.dashboard.view",
        "union.players.approve",
        "union.clubs.manage",
        "union.reports.view",
    },
    "REFEREE_MANAGER": {
        "union.dashboard.view",
        "union.referees.manage",
        "union.reports.view",
    },
    "FINANCE_OFFICER": {
        "union.dashboard.view",
        "union.finance.view",
        "union.reports.view",
    },
    "COMMUNICATIONS_OFFICER": {
        "union.dashboard.view",
        "union.communications.manage",
    },
    "VIEWER": {
        "union.dashboard.view",
        "union.reports.view",
    },
}


class UnionWorkspace(models.Model):
    """Admin workspace for federations, unions and community leagues."""

    class WorkspaceType(models.TextChoices):
        FEDERATION = "FEDERATION", "Federation"
        UNION = "UNION", "Union"
        COMMUNITY_LEAGUE = "COMMUNITY_LEAGUE", "Community League"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    related_union = models.OneToOneField(
        Union,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="workspace",
    )
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    acronym = models.CharField(max_length=40)
    sport = models.CharField(max_length=80)
    workspace_type = models.CharField(
        max_length=40,
        choices=WorkspaceType.choices,
        default=WorkspaceType.FEDERATION,
    )
    description = models.TextField(blank=True)
    primary_color = models.CharField(max_length=20, default="#7b3ff2")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["workspace_type", "status"]),
        ]

    def __str__(self):
        return f"{self.acronym} - {self.name}"


class UnionWorkspaceMembership(models.Model):
    """Connects a normal user account to a union workspace with permissions."""

    class Role(models.TextChoices):
        OWNER = "OWNER", "Workspace Owner"
        UNION_ADMIN = "UNION_ADMIN", "Union Admin"
        COMPETITIONS_MANAGER = "COMPETITIONS_MANAGER", "Competitions Manager"
        REGISTRAR = "REGISTRAR", "Player Registrar"
        REFEREE_MANAGER = "REFEREE_MANAGER", "Referee Manager"
        FINANCE_OFFICER = "FINANCE_OFFICER", "Finance Officer"
        COMMUNICATIONS_OFFICER = "COMMUNICATIONS_OFFICER", "Communications Officer"
        VIEWER = "VIEWER", "Viewer"

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="union_workspace_memberships",
    )
    workspace = models.ForeignKey(
        UnionWorkspace,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=40, choices=Role.choices, default=Role.VIEWER)
    extra_permissions = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="union_workspace_invitations_sent",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["workspace__name", "user__email"]
        unique_together = ["user", "workspace"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["workspace", "role", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user.email} -> {self.workspace.acronym} ({self.role})"

    @property
    def effective_permissions(self):
        role_permissions = UNION_WORKSPACE_ROLE_PERMISSIONS.get(self.role, set())
        return sorted(set(role_permissions) | set(self.extra_permissions or []))
