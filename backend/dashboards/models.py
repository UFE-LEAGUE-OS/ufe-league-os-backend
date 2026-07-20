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


class CompetitionIdentity(models.Model):
    """The permanent identity shared by every historical season edition."""

    class CompetitionType(models.TextChoices):
        LEAGUE = "LEAGUE", "League"
        KNOCKOUT = "KNOCKOUT", "Knockout"
        GROUP_AND_KNOCKOUT = "GROUP_AND_KNOCKOUT", "Group and knockout"
        TOURNAMENT = "TOURNAMENT", "Tournament"
        SERIES = "SERIES", "Short-format series"
        COMMUNITY = "COMMUNITY", "Community competition"

    union = models.ForeignKey(
        Union,
        on_delete=models.PROTECT,
        related_name="competition_identities",
    )
    primary_league = models.ForeignKey(
        League,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="competition_identities",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    sport = models.CharField(max_length=80, blank=True)
    competition_type = models.CharField(
        max_length=30,
        choices=CompetitionType.choices,
        default=CompetitionType.LEAGUE,
    )
    description = models.TextField(blank=True)
    branding = models.JSONField(default=dict, blank=True)
    default_format = models.JSONField(default=dict, blank=True)
    default_eligibility_rules = models.JSONField(default=dict, blank=True)
    tier = models.PositiveSmallIntegerField(null=True, blank=True)
    higher_competition = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lower_competitions",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["union__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["union", "slug"],
                name="unique_union_competition_identity_slug",
            )
        ]
        indexes = [
            models.Index(fields=["union", "is_active"]),
            models.Index(fields=["primary_league", "is_active"]),
        ]

    def clean(self):
        super().clean()
        if self.primary_league_id and self.primary_league.union_id != self.union_id:
            raise ValidationError(
                {"primary_league": "League must belong to the Union."}
            )
        if (
            self.higher_competition_id
            and self.higher_competition.union_id != self.union_id
        ):
            raise ValidationError(
                {"higher_competition": "Competition must belong to the Union."}
            )
        if self.higher_competition_id == self.id:
            raise ValidationError(
                {"higher_competition": "A competition cannot be its own parent."}
            )
        ancestor = self.higher_competition
        seen = {self.id}
        while ancestor is not None:
            if ancestor.id in seen:
                raise ValidationError(
                    {
                        "higher_competition": "Competition hierarchy cannot contain a cycle."
                    }
                )
            seen.add(ancestor.id)
            ancestor = ancestor.higher_competition

    def __str__(self):
        return self.name


class CompetitionEdition(models.Model):
    """A season-specific edition backed by a legacy-compatible Competition row."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        REGISTRATION_OPEN = "REGISTRATION_OPEN", "Registration open"
        REGISTRATION_CLOSED = "REGISTRATION_CLOSED", "Registration closed"
        ENTRIES_UNDER_REVIEW = "ENTRIES_UNDER_REVIEW", "Entries under review"
        SCHEDULING = "SCHEDULING", "Scheduling"
        READY_FOR_PUBLICATION = "READY_FOR_PUBLICATION", "Ready for publication"
        PUBLISHED = "PUBLISHED", "Published"
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        ARCHIVED = "ARCHIVED", "Archived"
        CANCELLED = "CANCELLED", "Cancelled"

    identity = models.ForeignKey(
        CompetitionIdentity,
        on_delete=models.PROTECT,
        related_name="editions",
    )
    competition = models.OneToOneField(
        Competition,
        on_delete=models.PROTECT,
        related_name="competition_edition",
    )
    season = models.ForeignKey(
        "Season",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="competition_editions",
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    registration_opens_at = models.DateTimeField(null=True, blank=True)
    registration_closes_at = models.DateTimeField(null=True, blank=True)
    entry_fee = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default="UGX")
    rules = models.JSONField(default=dict, blank=True)
    structure = models.JSONField(default=dict, blank=True)
    eligibility_rules = models.JSONField(default=dict, blank=True)
    copied_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="copied_editions",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="published_competition_editions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-season__start_date", "-created_at", "identity__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["identity", "season"],
                condition=models.Q(season__isnull=False),
                name="unique_identity_competition_edition_season",
            )
        ]
        indexes = [
            models.Index(fields=["identity", "status"]),
            models.Index(fields=["season", "status"]),
        ]

    def clean(self):
        super().clean()
        if (
            self.competition_id
            and self.competition.league.union_id != self.identity.union_id
        ):
            raise ValidationError(
                {"competition": "Competition must belong to the identity Union."}
            )
        if self.season_id and self.season.league.union_id != self.identity.union_id:
            raise ValidationError(
                {"season": "Season must belong to the identity Union."}
            )
        if (
            self.registration_opens_at
            and self.registration_closes_at
            and self.registration_closes_at < self.registration_opens_at
        ):
            raise ValidationError(
                {"registration_closes_at": "Registration cannot close before it opens."}
            )

    def __str__(self):
        return f"{self.identity.name} - {self.competition.season}"


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
        "union.teams.manage",
        "union.competitions.view",
        "union.competitions.manage",
        "union.competitions.publish",
        "union.clubs.view",
        "union.clubs.manage",
        "union.registrations.view",
        "union.registrations.manage",
        "union.players.approve",
        "union.players.view",
        "union.transfers.view",
        "union.transfers.approve",
        "union.referees.manage",
        "union.statistics.view",
        "union.statistics.manage",
        "union.finance.view",
        "union.finance.manage",
        "union.reports.view",
        "union.communications.manage",
        "union.sponsors.view",
        "union.sponsors.manage",
        "union.users.manage",
        "union.audit.view",
        "union.approvals.manage",
        "union.official.appointments.view",
        "union.official.reports.manage",
        "union.official.availability.manage",
        "union.official.documents.view",
        "union.official.payments.view",
    },
    "UNION_ADMIN": {
        "union.dashboard.view",
        "union.teams.manage",
        "union.competitions.view",
        "union.competitions.manage",
        "union.competitions.publish",
        "union.clubs.view",
        "union.clubs.manage",
        "union.registrations.view",
        "union.registrations.manage",
        "union.players.approve",
        "union.players.view",
        "union.transfers.view",
        "union.transfers.approve",
        "union.referees.manage",
        "union.statistics.view",
        "union.statistics.manage",
        "union.finance.view",
        "union.reports.view",
        "union.communications.manage",
        "union.sponsors.view",
        "union.sponsors.manage",
        "union.users.manage",
        "union.audit.view",
        "union.approvals.manage",
        "union.official.appointments.view",
        "union.official.reports.manage",
        "union.official.availability.manage",
        "union.official.documents.view",
        "union.official.payments.view",
    },
    "COMPETITIONS_MANAGER": {
        "union.dashboard.view",
        "union.teams.manage",
        "union.competitions.view",
        "union.competitions.manage",
        "union.competitions.publish",
        "union.clubs.view",
        "union.registrations.view",
        "union.registrations.manage",
        "union.players.view",
        "union.transfers.view",
        "union.statistics.view",
        "union.statistics.manage",
        "union.reports.view",
    },
    "REGISTRAR": {
        "union.dashboard.view",
        "union.clubs.view",
        "union.players.approve",
        "union.players.view",
        "union.registrations.view",
        "union.registrations.manage",
        "union.transfers.view",
        "union.transfers.approve",
        "union.clubs.manage",
        "union.reports.view",
    },
    "REFEREE_MANAGER": {
        "union.dashboard.view",
        "union.referees.manage",
        "union.statistics.view",
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
        "union.finance.manage",
        "union.reports.view",
    },
    "COMMUNICATIONS_OFFICER": {
        "union.dashboard.view",
        "union.communications.manage",
        "union.reports.view",
    },
    "SPONSORSHIP_OFFICER": {
        "union.dashboard.view",
        "union.sponsors.view",
        "union.sponsors.manage",
        "union.reports.view",
    },
    "NATIONAL_TEAM_MANAGER": {
        "union.dashboard.view",
        "union.teams.manage",
        "union.players.view",
        "union.registrations.view",
        "union.reports.view",
    },
    "TECHNICAL_ADMINISTRATOR": {
        "union.dashboard.view",
        "union.competitions.view",
        "union.competitions.manage",
        "union.clubs.view",
        "union.players.view",
        "union.statistics.view",
        "union.statistics.manage",
        "union.reports.view",
    },
    "CUSTOM_USER": {
        "union.dashboard.view",
    },
    "TICKETING_OFFICER": {
        "union.dashboard.view",
        "union.ticketing.manage",
        "union.ticketing.scan",
        "union.reports.view",
    },
    "VIEWER": {
        "union.dashboard.view",
        "union.competitions.view",
        "union.clubs.view",
        "union.registrations.view",
        "union.players.view",
        "union.transfers.view",
        "union.statistics.view",
        "union.sponsors.view",
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
        SPONSORSHIP_OFFICER = "SPONSORSHIP_OFFICER", "Sponsorship Officer"
        NATIONAL_TEAM_MANAGER = "NATIONAL_TEAM_MANAGER", "National Team Manager"
        TECHNICAL_ADMINISTRATOR = "TECHNICAL_ADMINISTRATOR", "Technical Administrator"
        CUSTOM_USER = "CUSTOM_USER", "Custom User"
        TICKETING_OFFICER = "TICKETING_OFFICER", "Ticketing Officer"
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
    scope_restrictions = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Optional resource scope restrictions, keyed by resource type. "
            "An empty object grants the workspace-wide role template."
        ),
    )
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


class NationalTeam(models.Model):
    """A maintained representative team owned by one Union workspace."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        CAMP = "CAMP", "In Camp"
        SELECTION = "SELECTION", "Selection"
        INACTIVE = "INACTIVE", "Inactive"

    workspace = models.ForeignKey(
        UnionWorkspace,
        on_delete=models.CASCADE,
        related_name="national_teams",
    )
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200)
    category = models.CharField(
        max_length=120,
        help_text="Examples: Senior Men, Senior Women, U20, Sevens.",
    )
    gender = models.CharField(max_length=40, blank=True)
    age_group = models.CharField(max_length=40, blank=True)
    head_coach = models.CharField(max_length=160, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_national_teams",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = ["workspace", "slug"]
        indexes = [
            models.Index(
                fields=["workspace", "status"],
                name="dash_natteam_ws_status_idx",
            ),
            models.Index(
                fields=["workspace", "is_active"],
                name="dash_natteam_ws_active_idx",
            ),
        ]

    def __str__(self):
        return f"{self.workspace.acronym} - {self.name}"


class NationalTeamMember(models.Model):
    """A maintained player or staff member attached to a representative team."""

    class MemberType(models.TextChoices):
        PLAYER = "PLAYER", "Player"
        STAFF = "STAFF", "Staff"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INJURED = "INJURED", "Injured"
        UNAVAILABLE = "UNAVAILABLE", "Unavailable"
        RELEASED = "RELEASED", "Released"

    team = models.ForeignKey(
        NationalTeam,
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="national_team_memberships",
    )
    player = models.ForeignKey(
        "UnionPlayer",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="national_team_assignments",
        help_text="Required for player selections from the approved Union player pool.",
    )
    club = models.ForeignKey(
        "accounts.Club",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="national_team_members",
    )
    full_name = models.CharField(max_length=160)
    member_type = models.CharField(
        max_length=20,
        choices=MemberType.choices,
        default=MemberType.PLAYER,
    )
    role = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["member_type", "full_name"]
        indexes = [
            models.Index(
                fields=["team", "member_type", "status"],
                name="dash_natmem_team_type_idx",
            ),
            models.Index(
                fields=["club", "status"],
                name="dash_natmem_club_status_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "user", "member_type"],
                condition=models.Q(user__isnull=False),
                name="unique_team_user_member_type",
            )
        ]

    def __str__(self):
        return f"{self.full_name} - {self.team.name}"


class UnionRegistrationApplication(models.Model):
    """A workspace-scoped registration or eligibility application."""

    class ApplicationType(models.TextChoices):
        NEW_PLAYER = "NEW_PLAYER", "New Player"
        TRANSFER = "TRANSFER", "Transfer"
        RENEWAL = "RENEWAL", "Renewal"
        SQUAD = "SQUAD", "Squad Registration"
        STAFF = "STAFF", "Staff Registration"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
        DOCUMENTS_REQUIRED = "DOCUMENTS_REQUIRED", "Documents Required"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"

    workspace = models.ForeignKey(
        UnionWorkspace,
        on_delete=models.CASCADE,
        related_name="registration_applications",
    )
    application_type = models.CharField(
        max_length=30,
        choices=ApplicationType.choices,
        default=ApplicationType.NEW_PLAYER,
    )
    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="union_registration_applications",
    )
    team = models.ForeignKey(
        "teams.Team",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="union_registration_applications",
    )
    competition = models.ForeignKey(
        Competition,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="registration_applications",
    )
    player_registration = models.ForeignKey(
        "teams.PlayerRegistration",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="union_review_applications",
    )
    applicant_name = models.CharField(max_length=180)
    registration_number = models.CharField(max_length=80, blank=True)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
    )
    documents_complete = models.BooleanField(default=False)
    submitted_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submitted_union_registration_applications",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_union_registration_applications",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_at", "applicant_name"]
        indexes = [
            models.Index(
                fields=["workspace", "status", "submitted_at"],
                name="dash_regapp_ws_status_idx",
            ),
            models.Index(
                fields=["workspace", "club", "status"],
                name="dash_regapp_ws_club_idx",
            ),
            models.Index(
                fields=["registration_number"],
                name="dash_regapp_regnum_idx",
            ),
        ]

    def __str__(self):
        return f"{self.applicant_name} - {self.get_application_type_display()}"


class UnionApproval(models.Model):
    """A workspace-scoped, reviewable decision for a sensitive Union action."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    workspace = models.ForeignKey(
        UnionWorkspace,
        on_delete=models.PROTECT,
        related_name="approvals",
    )
    subject_type = models.CharField(max_length=80)
    subject_id = models.PositiveBigIntegerField()
    action = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="union_approvals_requested",
    )
    reviewed_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="union_approvals_reviewed",
    )
    reason = models.TextField(blank=True)
    decision_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["workspace", "status", "created_at"],
                name="dash_approval_ws_status_idx",
            ),
            models.Index(
                fields=["workspace", "subject_type", "subject_id"],
                name="dash_approval_subject_idx",
            ),
        ]

    def __str__(self):
        return f"{self.workspace.acronym}: {self.action} ({self.status})"


class UnionAuditEvent(models.Model):
    """Append-only audit event for a material Union workspace action."""

    workspace = models.ForeignKey(
        UnionWorkspace,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    actor = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="union_audit_events",
    )
    action = models.CharField(max_length=120)
    target_type = models.CharField(max_length=80, blank=True)
    target_id = models.PositiveBigIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["workspace", "created_at"],
                name="dash_audit_ws_created_idx",
            ),
            models.Index(
                fields=["workspace", "action"],
                name="dash_audit_ws_action_idx",
            ),
            models.Index(
                fields=["target_type", "target_id"],
                name="dash_audit_target_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Union audit events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Union audit events cannot be deleted.")

    def __str__(self):
        return f"{self.workspace.acronym}: {self.action}"


class UnionReviewComment(models.Model):
    """A workspace-scoped review comment attached to an operational record."""

    workspace = models.ForeignKey(
        UnionWorkspace,
        on_delete=models.PROTECT,
        related_name="review_comments",
    )
    subject_type = models.CharField(max_length=80)
    subject_id = models.PositiveBigIntegerField()
    author = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="union_review_comments",
    )
    body = models.TextField()
    is_internal = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["workspace", "subject_type", "subject_id"],
                name="dash_comment_subject_idx",
            ),
        ]


class UnionDocumentReference(models.Model):
    """A reference to a document held by a workspace-owned operational record."""

    workspace = models.ForeignKey(
        UnionWorkspace,
        on_delete=models.PROTECT,
        related_name="document_references",
    )
    subject_type = models.CharField(max_length=80)
    subject_id = models.PositiveBigIntegerField()
    document_type = models.CharField(max_length=80)
    title = models.CharField(max_length=200)
    file_url = models.URLField(max_length=1000)
    uploaded_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_union_documents",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["workspace", "subject_type", "subject_id"],
                name="dash_document_subject_idx",
            ),
        ]


class ClubAffiliation(models.Model):
    """A Union's affiliation and compliance record for a Club."""

    class Status(models.TextChoices):
        APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED", "Application submitted"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        CHANGES_REQUESTED = "CHANGES_REQUESTED", "Changes requested"
        PROVISIONAL = "PROVISIONAL", "Provisional"
        ACTIVE = "ACTIVE", "Active"
        RENEWAL_DUE = "RENEWAL_DUE", "Renewal due"
        SUSPENDED = "SUSPENDED", "Suspended"
        EXPIRED = "EXPIRED", "Expired"
        REJECTED = "REJECTED", "Rejected"

    workspace = models.ForeignKey(
        UnionWorkspace,
        on_delete=models.PROTECT,
        related_name="club_affiliations",
    )
    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.PROTECT,
        related_name="union_affiliations",
    )
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.APPLICATION_SUBMITTED
    )
    expires_on = models.DateField(null=True, blank=True)
    compliance_status = models.CharField(max_length=50, default="PENDING")
    compliance_notes = models.TextField(blank=True)
    liaison = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="club_affiliations_as_liaison",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["club__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "club"],
                name="unique_workspace_club_affiliation",
            )
        ]
        indexes = [models.Index(fields=["workspace", "status"])]


class UnionPlayer(models.Model):
    """One permanent player identity within a Union, independent of Club or season."""

    class Status(models.TextChoices):
        PROVISIONAL = "PROVISIONAL", "Provisional"
        PENDING_VERIFICATION = "PENDING_VERIFICATION", "Pending verification"
        APPROVED = "APPROVED", "Approved"
        SUSPENDED = "SUSPENDED", "Suspended"
        REJECTED = "REJECTED", "Rejected"
        ARCHIVED = "ARCHIVED", "Archived"

    union = models.ForeignKey(Union, on_delete=models.PROTECT, related_name="players")
    user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="union_player_identities",
    )
    union_player_number = models.CharField(max_length=80)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=100)
    identity_reference = models.CharField(max_length=160, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PROVISIONAL
    )
    identity_verified_at = models.DateTimeField(null=True, blank=True)
    identity_verified_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_union_players",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["union", "union_player_number"],
                name="unique_union_player_number",
            ),
            models.UniqueConstraint(
                fields=["union", "identity_reference"],
                condition=~models.Q(identity_reference=""),
                name="unique_union_player_identity_reference",
            ),
        ]
        indexes = [
            models.Index(fields=["union", "status"]),
            models.Index(fields=["union", "last_name", "first_name"]),
        ]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class UnionPlayerNumberSequence(models.Model):
    """Locked per-Union allocator for permanent player numbers."""

    union = models.OneToOneField(
        Union,
        on_delete=models.PROTECT,
        related_name="player_number_sequence",
    )
    next_value = models.PositiveBigIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)


class UnionPlayerRegistration(models.Model):
    """Immutable-period Club registration history for a permanent Union player."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CHANGES_REQUESTED = "CHANGES_REQUESTED", "Changes requested"
        APPROVED = "APPROVED", "Approved"
        ACTIVE = "ACTIVE", "Active"
        TRANSFERRED = "TRANSFERRED", "Transferred"
        EXPIRED = "EXPIRED", "Expired"
        SUSPENDED = "SUSPENDED", "Suspended"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    workspace = models.ForeignKey(
        UnionWorkspace,
        on_delete=models.PROTECT,
        related_name="player_registrations",
    )
    player = models.ForeignKey(
        UnionPlayer,
        on_delete=models.PROTECT,
        related_name="club_registration_history",
    )
    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.PROTECT,
        related_name="union_player_registration_history",
    )
    team = models.ForeignKey(
        "teams.Team",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="union_player_registrations",
    )
    season = models.ForeignKey(
        Season,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="union_player_registrations",
    )
    source_registration = models.ForeignKey(
        "teams.PlayerRegistration",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="union_registration_history",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    registration_type = models.CharField(max_length=40, default="FIRST_REGISTRATION")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_union_player_registrations",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    decision_reason = models.TextField(blank=True)
    change_request_reason = models.TextField(blank=True)
    predecessor = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="successor_registrations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_from", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "player"],
                condition=models.Q(status="ACTIVE"),
                name="unique_active_workspace_player_registration",
            )
        ]
        indexes = [
            models.Index(fields=["workspace", "club", "status"]),
            models.Index(fields=["player", "status"]),
        ]


class UnionPlayerTransfer(models.Model):
    """A Union-reviewed transfer that atomically preserves Club registration history."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        PLAYER_CONSENT_REQUIRED = "PLAYER_CONSENT_REQUIRED", "Player consent required"
        SOURCE_CLUB_RESPONSE_REQUIRED = (
            "SOURCE_CLUB_RESPONSE_REQUIRED",
            "Source Club response required",
        )
        UNDER_AUTOMATIC_REVIEW = "UNDER_AUTOMATIC_REVIEW", "Under automatic review"
        UNDER_UNION_REVIEW = "UNDER_UNION_REVIEW", "Under Union review"
        CHANGES_REQUESTED = "CHANGES_REQUESTED", "Changes requested"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"
        EXPIRED = "EXPIRED", "Expired"

    workspace = models.ForeignKey(
        UnionWorkspace,
        on_delete=models.PROTECT,
        related_name="player_transfers",
    )
    player = models.ForeignKey(
        UnionPlayer, on_delete=models.PROTECT, related_name="transfers"
    )
    source_registration = models.ForeignKey(
        UnionPlayerRegistration,
        on_delete=models.PROTECT,
        related_name="outgoing_transfers",
    )
    destination_club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.PROTECT,
        related_name="incoming_union_player_transfers",
    )
    destination_team = models.ForeignKey(
        "teams.Team",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incoming_union_player_transfers",
    )
    legacy_transfer = models.OneToOneField(
        "teams.PlayerTransfer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="union_transfer_workflow",
    )
    status = models.CharField(
        max_length=40, choices=Status.choices, default=Status.DRAFT
    )
    effective_on = models.DateField()
    transfer_type = models.CharField(max_length=30, default="PERMANENT")
    loan_end_on = models.DateField(null=True, blank=True)
    initiated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="initiated_union_player_transfers",
    )
    source_club_response_at = models.DateTimeField(null=True, blank=True)
    source_club_response = models.TextField(blank=True)
    player_consented_at = models.DateTimeField(null=True, blank=True)
    player_consent_method = models.CharField(max_length=80, blank=True)
    documents = models.JSONField(default=list, blank=True)
    fee_status = models.CharField(max_length=40, blank=True)
    reviewed_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_union_player_transfers",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    change_request_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["workspace", "status"]),
            models.Index(fields=["player", "status"]),
        ]


class UnionPlayerCompetitionEligibility(models.Model):
    """Competition-specific eligibility, separate from Club registration history."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ELIGIBLE = "ELIGIBLE", "Eligible"
        INELIGIBLE = "INELIGIBLE", "Ineligible"
        SUSPENDED = "SUSPENDED", "Suspended"
        EXPIRED = "EXPIRED", "Expired"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    workspace = models.ForeignKey(
        UnionWorkspace,
        on_delete=models.PROTECT,
        related_name="competition_eligibilities",
    )
    player = models.ForeignKey(
        UnionPlayer, on_delete=models.PROTECT, related_name="competition_eligibilities"
    )
    registration = models.ForeignKey(
        UnionPlayerRegistration,
        on_delete=models.PROTECT,
        related_name="competition_eligibilities",
    )
    source_submission = models.ForeignKey(
        "teams.PlayerRegistration",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="competition_eligibility_history",
    )
    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.PROTECT,
        related_name="union_competition_eligibilities",
    )
    team = models.ForeignKey(
        "teams.Team",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="union_competition_eligibilities",
    )
    competition_identity = models.ForeignKey(
        CompetitionIdentity,
        on_delete=models.PROTECT,
        related_name="player_eligibilities",
    )
    competition_edition = models.ForeignKey(
        CompetitionEdition,
        on_delete=models.PROTECT,
        related_name="player_eligibilities",
    )
    season = models.ForeignKey(
        Season, on_delete=models.PROTECT, related_name="player_eligibilities"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    eligible_from = models.DateField(null=True, blank=True)
    eligible_until = models.DateField(null=True, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    restriction_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_competition_eligibilities",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["player", "competition_edition"],
                condition=models.Q(status="ELIGIBLE"),
                name="unique_eligible_player_edition",
            ),
            models.UniqueConstraint(
                fields=["source_submission", "competition_edition"],
                condition=models.Q(source_submission__isnull=False),
                name="unique_submission_competition_edition",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "status"]),
            models.Index(fields=["competition_edition", "status"]),
        ]
