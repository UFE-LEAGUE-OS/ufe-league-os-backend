from django.core.exceptions import ValidationError
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
    season_record = models.ForeignKey(
        "Season",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="competitions",
    )
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


class LeagueAdminScope(models.Model):
    """Scopes league/competition administrators to the records they may manage."""

    class Role(models.TextChoices):
        LEAGUE_ADMIN = "LEAGUE_ADMIN", "League Administrator"
        COMPETITION_ADMIN = "COMPETITION_ADMIN", "Competition Administrator"
        OFFICIALS_COORDINATOR = "OFFICIALS_COORDINATOR", "Officials Coordinator"
        VIEWER = "VIEWER", "Viewer"

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="league_admin_scopes",
    )
    league = models.ForeignKey(
        League,
        on_delete=models.CASCADE,
        related_name="admin_scopes",
    )
    competition = models.ForeignKey(
        Competition,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="admin_scopes",
        help_text="Leave blank to grant access to the whole league.",
    )
    role = models.CharField(
        max_length=40,
        choices=Role.choices,
        default=Role.LEAGUE_ADMIN,
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_league_admin_scopes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["league__name", "competition__name", "user__email"]
        indexes = [
            models.Index(
                fields=["user", "is_active"],
                name="dashboards_user_id_482361_idx",
            ),
            models.Index(
                fields=["league", "is_active"],
                name="dashboards_league__6316d7_idx",
            ),
            models.Index(
                fields=["competition", "is_active"],
                name="dashboards_competi_c7b452_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "league"],
                condition=models.Q(competition__isnull=True),
                name="unique_user_full_league_admin_scope",
            ),
            models.UniqueConstraint(
                fields=["user", "competition"],
                condition=models.Q(competition__isnull=False),
                name="unique_user_competition_admin_scope",
            ),
        ]

    def clean(self):
        super().clean()
        if self.competition_id and self.competition.league_id != self.league_id:
            raise ValidationError(
                {"competition": "The competition must belong to the selected league."}
            )

    @property
    def can_manage_appointments(self):
        return self.role in {
            self.Role.LEAGUE_ADMIN,
            self.Role.COMPETITION_ADMIN,
            self.Role.OFFICIALS_COORDINATOR,
        }

    def __str__(self):
        target = self.competition.name if self.competition_id else self.league.name
        return f"{self.user.email} -> {target} ({self.get_role_display()})"


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
        "union.official.appointments.view",
        "union.official.reports.manage",
        "union.official.availability.manage",
        "union.official.documents.view",
        "union.official.payments.view",
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
        "union.official.appointments.view",
        "union.official.reports.manage",
        "union.official.availability.manage",
        "union.official.documents.view",
        "union.official.payments.view",
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
        "union.official.appointments.view",
        "union.official.reports.manage",
        "union.official.availability.manage",
        "union.official.documents.view",
    },
    "MATCH_OFFICIAL": {
        "union.dashboard.view",
        "union.official.appointments.view",
        "union.official.reports.manage",
        "union.official.availability.manage",
        "union.official.documents.view",
        "union.official.payments.view",
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
        MATCH_OFFICIAL = "MATCH_OFFICIAL", "Match Official"
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


class Season(models.Model):
    """A real season record under a league, e.g. 2026/27."""

    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name="seasons")
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=100)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "-created_at", "name"]
        unique_together = ["league", "slug"]
        indexes = [
            models.Index(fields=["league", "is_active"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return f"{self.league.name} - {self.name}"


class LeagueClubMembership(models.Model):
    """Season-aware club membership in a league, including promotions/relegations."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        PROMOTED = "PROMOTED", "Promoted"
        RELEGATED = "RELEGATED", "Relegated"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"
        INVITED = "INVITED", "Invited"
        SUSPENDED = "SUSPENDED", "Suspended"

    league = models.ForeignKey(
        League,
        on_delete=models.CASCADE,
        related_name="club_memberships",
    )
    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="league_memberships",
    )
    season = models.ForeignKey(
        Season,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="club_memberships",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    promoted_from_league = models.ForeignKey(
        League,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="promoted_club_entries",
    )
    relegated_to_league = models.ForeignKey(
        League,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="relegated_club_entries",
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_league_club_memberships",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["league__name", "season__name", "club__name"]
        unique_together = ["league", "club", "season"]
        indexes = [
            models.Index(fields=["league", "status"]),
            models.Index(fields=["season", "status"]),
            models.Index(fields=["club", "status"]),
        ]

    def __str__(self):
        season = self.season.name if self.season else "All seasons"
        return f"{self.club.name} in {self.league.name} ({season}) - {self.status}"

    @property
    def is_active_entry(self):
        return self.status in {self.Status.ACTIVE, self.Status.PROMOTED}


class UnionMatchOfficial(models.Model):
    """A referee or match official managed by a union workspace."""

    class SportType(models.TextChoices):
        RUGBY = "RUGBY", "Rugby"
        FOOTBALL = "FOOTBALL", "Football"
        BASKETBALL = "BASKETBALL", "Basketball"

    class RoleType(models.TextChoices):
        # Rugby and football referee roles
        CENTRE_REFEREE = "CENTRE_REFEREE", "Centre Referee"
        ASSISTANT_REFEREE = "ASSISTANT_REFEREE", "Assistant Referee"

        # Rugby roles
        TMO = "TMO", "Television Match Official"
        CITING_COMMISSIONER = "CITING_COMMISSIONER", "Citing Commissioner"
        SUBSTITUTION_CONTROLLER = (
            "SUBSTITUTION_CONTROLLER",
            "Substitution Controller",
        )
        TECHNICAL_ZONE_OFFICIAL = (
            "TECHNICAL_ZONE_OFFICIAL",
            "Technical Zone Official",
        )
        SCOREBOARD_OPERATOR = "SCOREBOARD_OPERATOR", "Scoreboard Operator"

        # Football roles
        FOURTH_OFFICIAL = "FOURTH_OFFICIAL", "Fourth Official"
        VAR = "VAR", "Video Assistant Referee"
        AVAR = "AVAR", "Assistant Video Assistant Referee"
        MATCH_COORDINATOR = "MATCH_COORDINATOR", "Match Coordinator"

        # Basketball roles
        CREW_CHIEF = "CREW_CHIEF", "Crew Chief"
        UMPIRE = "UMPIRE", "Umpire"
        TABLE_OFFICIAL = "TABLE_OFFICIAL", "Table Official"
        ASSISTANT_SCORER = "ASSISTANT_SCORER", "Assistant Scorer"
        TIMER = "TIMER", "Timer"
        SHOT_CLOCK_OPERATOR = "SHOT_CLOCK_OPERATOR", "Shot Clock Operator"

        # Shared match-official roles
        MATCH_COMMISSIONER = "MATCH_COMMISSIONER", "Match Commissioner"
        ASSESSOR = "ASSESSOR", "Referee Assessor"
        SCORER = "SCORER", "Scorer"
        TIMEKEEPER = "TIMEKEEPER", "Timekeeper"
        OTHER = "OTHER", "Other Match Official"

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        UNAVAILABLE = "UNAVAILABLE", "Unavailable"
        SUSPENDED = "SUSPENDED", "Suspended"
        RETIRED = "RETIRED", "Retired"

    union = models.ForeignKey(
        Union,
        on_delete=models.CASCADE,
        related_name="match_officials",
    )
    user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="match_official_profiles",
    )
    full_name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=30, blank=True)
    role_type = models.CharField(
        max_length=40,
        choices=RoleType.choices,
        default=RoleType.CENTRE_REFEREE,
    )
    certification_level = models.CharField(max_length=80, blank=True)
    primary_sport = models.CharField(
        max_length=20,
        choices=SportType.choices,
        blank=True,
    )
    competitions = models.TextField(blank=True)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_match_officials",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["union", "status"]),
            models.Index(fields=["union", "role_type"]),
            models.Index(fields=["email"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["union", "email"],
                condition=~models.Q(email=""),
                name="unique_union_match_official_email",
            )
        ]

    def __str__(self):
        return f"{self.full_name} - {self.get_role_type_display()}"


class FixtureOfficialAssignment(models.Model):
    """A referee or match official appointment to a fixture."""

    class Status(models.TextChoices):
        PROPOSED = "PROPOSED", "Proposed"
        ASSIGNED = "ASSIGNED", "Assigned"
        ACCEPTED = "ACCEPTED", "Accepted"
        DECLINED = "DECLINED", "Declined"
        CANCELLED = "CANCELLED", "Cancelled"

    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="official_assignments",
    )
    official = models.ForeignKey(
        UnionMatchOfficial,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    role_type = models.CharField(
        max_length=40,
        choices=UnionMatchOfficial.RoleType.choices,
        default=UnionMatchOfficial.RoleType.CENTRE_REFEREE,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ASSIGNED,
    )
    notes = models.TextField(blank=True)
    response_note = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    assigned_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fixture_official_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["match__match_date", "role_type", "official__full_name"]
        unique_together = ["match", "official", "role_type"]
        indexes = [
            models.Index(fields=["match", "status"]),
            models.Index(fields=["official", "status"]),
        ]

    def __str__(self):
        return (
            f"{self.official.full_name} - {self.match} ({self.get_role_type_display()})"
        )
