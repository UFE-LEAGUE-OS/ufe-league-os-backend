from django.db import models


class SportVariant(models.Model):
    """
    Configurable sport variants that can be used across leagues.
    Super admins define which sport variants are available (e.g.,
    Football 11-a-side, Futsal, Beach Soccer, 7-a-side, etc.).
    """

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    icon = models.ImageField(
        upload_to="governance/sport_variants/", blank=True, null=True
    )

    # Sport variant metadata
    players_per_team = models.PositiveIntegerField(
        default=11, help_text="Number of players per team on the field"
    )
    max_substitutes = models.PositiveIntegerField(
        default=5, help_text="Maximum number of substitutes allowed"
    )
    match_duration_minutes = models.PositiveIntegerField(
        default=90, help_text="Standard match duration in minutes"
    )
    has_halftime = models.BooleanField(default=True)
    halftime_duration_minutes = models.PositiveIntegerField(
        default=15, help_text="Halftime break duration in minutes"
    )
    has_extra_time = models.BooleanField(default=False)
    extra_time_duration_minutes = models.PositiveIntegerField(
        default=30, help_text="Extra time duration in minutes"
    )
    has_penalties = models.BooleanField(default=False)
    max_red_cards_default = models.PositiveIntegerField(
        default=1, help_text="Default red cards before forfeit"
    )
    points_win = models.PositiveIntegerField(default=3)
    points_draw = models.PositiveIntegerField(default=1)
    points_loss = models.PositiveIntegerField(default=0)

    # Governance
    is_active = models.BooleanField(
        default=True, help_text="Whether this variant is available for use"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Set to True once the variant has been verified by a super admin",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "governance"
        ordering = ["name"]
        verbose_name = "Sport Variant"
        verbose_name_plural = "Sport Variants"

    def __str__(self):
        return self.name


class CompetitionFormat(models.Model):
    """
    Configurable competition formats that super admins define.
    Examples: Round Robin, Double Round Robin, Knockout, Group Stage + Knockout,
    Swiss System, etc.
    """

    class StageType(models.TextChoices):
        SINGLE_STAGE = "SINGLE", "Single Stage"
        GROUP_KNOCKOUT = "GROUP_KO", "Group Stage + Knockout"
        MULTI_STAGE = "MULTI", "Multi Stage"
        SWISS = "SWISS", "Swiss System"
        CUSTOM = "CUSTOM", "Custom"

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    stage_type = models.CharField(
        max_length=20,
        choices=StageType.choices,
        default=StageType.SINGLE_STAGE,
        help_text="The structural type of the competition format",
    )

    # Round-robin specific
    has_home_and_away = models.BooleanField(
        default=True,
        help_text="Whether teams play both home and away (double round robin)",
    )
    max_teams_default = models.PositiveIntegerField(
        default=16, help_text="Default maximum number of teams"
    )
    min_teams_default = models.PositiveIntegerField(
        default=2, help_text="Default minimum number of teams"
    )

    # Group + Knockout specific
    groups_count = models.PositiveIntegerField(
        default=0, blank=True, help_text="Number of groups (if applicable)"
    )
    teams_per_group = models.PositiveIntegerField(
        default=0, blank=True, help_text="Teams per group (if applicable)"
    )
    teams_qualify_per_group = models.PositiveIntegerField(
        default=0, blank=True, help_text="Number of teams that qualify from each group"
    )

    # Knockout specific
    has_third_place_match = models.BooleanField(default=False)
    has_replays = models.BooleanField(default=False)
    has_aggregate = models.BooleanField(
        default=False, help_text="Two-legged aggregate ties"
    )
    away_goals_rule = models.BooleanField(default=False)

    # Tie-breaking
    tie_breakers = models.JSONField(
        default=list,
        blank=True,
        help_text="Ordered list of tie-breaking criteria (e.g. ['goal_difference', 'goals_scored', 'head_to_head'])",
    )

    # Governance
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "governance"
        ordering = ["name"]
        verbose_name = "Competition Format"
        verbose_name_plural = "Competition Formats"

    def __str__(self):
        return self.name


class Rule(models.Model):
    """
    Rules and standards for leagues to comply with.
    Super admins create and publish rules/standards to one or more leagues.
    """

    class Category(models.TextChoices):
        COMPLIANCE = "COMPLIANCE", "Compliance & Legal"
        COMPETITION = "COMPETITION", "Competition Rules"
        FINANCIAL = "FINANCIAL", "Financial Regulations"
        DISCIPLINARY = "DISCIPLINARY", "Disciplinary & Ethics"
        PLAYER_ELIGIBILITY = "PLAYER_ELIG", "Player Eligibility"
        REGISTRATION = "REGISTRATION", "Registration & Transfers"
        TECHNICAL = "TECHNICAL", "Technical Standards"
        SAFETY = "SAFETY", "Safety & Security"
        BROADCAST = "BROADCAST", "Broadcast & Media"
        MARKETING = "MARKETING", "Marketing & Branding"
        OTHER = "OTHER", "Other"

    class Priority(models.TextChoices):
        MANDATORY = "MANDATORY", "Mandatory"
        RECOMMENDED = "RECOMMENDED", "Recommended"
        ADVISORY = "ADVISORY", "Advisory"

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300)
    rule_number = models.CharField(
        max_length=50, blank=True, help_text="Official rule number/code if applicable"
    )
    category = models.CharField(
        max_length=30, choices=Category.choices, default=Category.COMPETITION
    )
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.MANDATORY
    )
    description = models.TextField(help_text="Detailed explanation of the rule")
    summary = models.CharField(
        max_length=500, blank=True, help_text="Short summary for quick reference"
    )

    # Versioning
    version = models.CharField(max_length=20, default="1.0")
    effective_date = models.DateField(blank=True, null=True)
    supersedes = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="superseded_by",
        help_text="Previous version of this rule that this one replaces",
    )

    # Enforcement
    enforcement_notes = models.TextField(
        blank=True,
        help_text="How this rule is enforced and penalties for non-compliance",
    )

    # Governance
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(
        default=False, help_text="Whether this rule is published to leagues"
    )
    published_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_rules",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "governance"
        ordering = ["category", "title"]
        unique_together = [["slug", "version"]]
        verbose_name = "Rule & Standard"
        verbose_name_plural = "Rules & Standards"

    def __str__(self):
        label = f"[{self.rule_number}] " if self.rule_number else ""
        return f"{label}{self.title} v{self.version}"


class LeagueStandard(models.Model):
    """
    Tracks which rules/standards have been published to which leagues.
    This is the "publish standards to leagues" API.
    """

    rule = models.ForeignKey(
        Rule, on_delete=models.CASCADE, related_name="league_assignments"
    )
    league = models.ForeignKey(
        "dashboards.League", on_delete=models.CASCADE, related_name="assigned_standards"
    )
    is_accepted = models.BooleanField(
        default=False, help_text="Whether the league has accepted the standard"
    )
    accepted_at = models.DateTimeField(blank=True, null=True)
    accepted_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accepted_standards",
    )
    rejection_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    assigned_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_standards",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "governance"
        ordering = ["-assigned_at"]
        unique_together = [["rule", "league"]]
        verbose_name = "League Standard Assignment"
        verbose_name_plural = "League Standard Assignments"

    def __str__(self):
        return f"{self.rule.title} \u2192 {self.league.name}"
