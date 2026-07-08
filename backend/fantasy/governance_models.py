"""
Fantasy League Governance Models
These models allow superadmins to configure and govern fantasy competitions.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class FantasyScoringRule(models.Model):
    """
    Scoring rules for fantasy competitions.
    Controls how players earn points in different competitions.
    """

    class EventType(models.TextChoices):
        TRY = "TRY", "Try"
        CONVERSION = "CONVERSION", "Conversion"
        PENALTY_GOAL = "PENALTY_GOAL", "Penalty Goal"
        DROP_GOAL = "DROP_GOAL", "Drop Goal"
        TACKLE = "TACKLE", "Tackle"
        ASSIST = "ASSIST", "Assist"
        CLEAN_SHEET = "CLEAN_SHEET", "Clean Sheet"
        MAN_OF_THE_MATCH = "MAN_OF_THE_MATCH", "Man of the Match"
        YELLOW_CARD = "YELLOW_CARD", "Yellow Card"
        RED_CARD = "RED_CARD", "Red Card"
        OWN_GOAL = "OWN_GOAL", "Own Goal"
        PLAYED = "PLAYED", "Played (60+ mins)"
        GOAL = "GOAL", "Goal"
        SAVE = "SAVE", "Save (Goalkeeper)"
        CUSTOM = "CUSTOM", "Custom Event"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    points = models.DecimalField(max_digits=5, decimal_places=2)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    is_system_rule = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event_type", "name"]
        indexes = [
            models.Index(fields=["event_type", "is_active"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name}: {self.points} pts"


class FantasyTransferRule(models.Model):
    """
    Transfer rules governing player transfers between teams.
    """

    class RuleType(models.TextChoices):
        TRANSFER_LIMIT = "TRANSFER_LIMIT", "Transfer Limit per Gameweek"
        TRANSFER_COST = "TRANSFER_COST", "Transfer Cost"
        ROLLOVER_TRANSFERS = "ROLLOVER_TRANSFERS", "Rollover Unused Transfers"
        FREE_TRANSFERS = "FREE_TRANSFERS", "Free Transfers"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    rule_type = models.CharField(max_length=30, choices=RuleType.choices)
    value = models.IntegerField(help_text="Numeric value for the rule")
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["rule_type", "name"]
        indexes = [
            models.Index(fields=["rule_type", "is_active"]),
            models.Index(fields=["effective_from"]),
        ]

    def __str__(self):
        return f"{self.name}: {self.value}"


class FantasySquadRule(models.Model):
    """
    Squad composition and lineup rules.
    """

    class RuleType(models.TextChoices):
        MIN_SQUAD_SIZE = "MIN_SQUAD_SIZE", "Minimum Squad Size"
        MAX_SQUAD_SIZE = "MAX_SQUAD_SIZE", "Maximum Squad Size"
        MIN_LINEUP_SIZE = "MIN_LINEUP_SIZE", "Minimum Lineup Size"
        MAX_LINEUP_SIZE = "MAX_LINEUP_SIZE", "Maximum Lineup Size"
        MAX_PLAYERS_PER_CLUB = "MAX_PLAYERS_PER_CLUB", "Max Players per Club"
        MIN_PLAYERS_PER_POSITION = (
            "MIN_PLAYERS_PER_POSITION",
            "Min Players per Position",
        )
        MAX_PLAYERS_PER_POSITION = (
            "MAX_PLAYERS_PER_POSITION",
            "Max Players per Position",
        )
        CAPTAIN_ALLOWED = "CAPTAIN_ALLOWED", "Captain Allowed"
        VICE_CAPTAIN_ALLOWED = "VICE_CAPTAIN_ALLOWED", "Vice Captain Allowed"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    rule_type = models.CharField(max_length=30, choices=RuleType.choices)
    value = models.IntegerField()
    position = models.CharField(
        max_length=30, blank=True, help_text="Applicable position if any"
    )
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["rule_type", "name"]
        indexes = [
            models.Index(fields=["rule_type", "is_active"]),
            models.Index(fields=["position"]),
        ]

    def __str__(self):
        return f"{self.name}: {self.value}"


class FantasyPriceStructure(models.Model):
    """
    Price structure configuration for fantasy players.
    """

    class PriceType(models.TextChoices):
        MIN_PRICE = "MIN_PRICE", "Minimum Player Price"
        MAX_PRICE = "MAX_PRICE", "Maximum Player Price"
        DEFAULT_PRICE = "DEFAULT_PRICE", "Default Player Price"
        BUDGET = "BUDGET", "Team Budget"
        PRICE_CHANGE_THRESHOLD = "PRICE_CHANGE_THRESHOLD", "Price Change Threshold"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    price_type = models.CharField(max_length=30, choices=PriceType.choices)
    value = models.DecimalField(max_digits=8, decimal_places=2)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price_type", "name"]
        indexes = [
            models.Index(fields=["price_type", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name}: {self.value}"


class FantasyEligibilityRule(models.Model):
    """
    Eligibility rules for players in fantasy competitions.
    """

    class RuleType(models.TextChoices):
        AGE_MIN = "AGE_MIN", "Minimum Age"
        AGE_MAX = "AGE_MAX", "Maximum Age"
        NATIONALITY_RESTRICTION = "NATIONALITY_RESTRICTION", "Nationality Restriction"
        LEAGUE_RESTRICTION = "LEAGUE_RESTRICTION", "League Restriction"
        INJURY_EXCLUSION = "INJURY_EXCLUSION", "Injury Exclusion"
        SUSPENSION_EXCLUSION = "SUSPENSION_EXCLUSION", "Suspension Exclusion"
        INTERNATIONAL_DUTY = "INTERNATIONAL_DUTY", "International Duty Restriction"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    rule_type = models.CharField(max_length=30, choices=RuleType.choices)
    value = models.CharField(max_length=255, help_text="Value or criteria for the rule")
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["rule_type", "name"]
        indexes = [
            models.Index(fields=["rule_type", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name}: {self.value}"


class FantasyCompetitionMapping(models.Model):
    """
    Maps fantasy competitions to real competitions and sports.
    """

    fantasy_competition = models.ForeignKey(
        "fantasy.FantasyCompetition",
        on_delete=models.CASCADE,
        related_name="governance_mappings",
    )

    sport_variant = models.ForeignKey(
        "governance.SportVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fantasy_mappings",
    )

    competition_format = models.ForeignKey(
        "governance.CompetitionFormat",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fantasy_mappings",
    )

    is_active = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="published_fantasy_mappings",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["fantasy_competition"]

    def __str__(self):
        return f"{self.fantasy_competition.name} Mapping"

    def publish(self, user):
        self.is_active = True
        self.published_at = timezone.now()
        self.published_by = user
        self.save()


class FantasyFeatureFlag(models.Model):
    """
    Feature flags to enable/disable fantasy features.
    """

    class FeatureName(models.TextChoices):
        FANTASY_ENABLED = "FANTASY_ENABLED", "Enable Fantasy Module"
        TRANSFERS_ENABLED = "TRANSFERS_ENABLED", "Enable Transfers"
        LEAGUES_ENABLED = "LEAGUES_ENABLED", "Enable Fantasy Leagues"
        AUTO_SCORING = "AUTO_SCORING", "Enable Auto-Scoring"
        MANUAL_SCORING = "MANUAL_SCORING", "Enable Manual Scoring Override"
        PRICE_CHANGES = "PRICE_CHANGES", "Enable Dynamic Price Changes"
        PUBLIC_LEAGUES = "PUBLIC_LEAGUES", "Enable Public Leagues"
        PRIVATE_LEAGUES = "PRIVATE_LEAGUES", "Enable Private Leagues"
        CAPTAIN_MODE = "CAPTAIN_MODE", "Enable Captain Mode"
        VICE_CAPTAIN_MODE = "VICE_CAPTTAIN_MODE", "Enable Vice Captain Mode"

    feature_name = models.CharField(
        max_length=50, choices=FeatureName.choices, unique=True
    )
    is_enabled = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    enabled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="enabled_fantasy_features",
    )
    enabled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["feature_name"]
        indexes = [
            models.Index(fields=["is_enabled"]),
        ]

    def __str__(self):
        status = "Enabled" if self.is_enabled else "Disabled"
        return f"{self.feature_name}: {status}"

    def enable(self, user):
        self.is_enabled = True
        self.enabled_by = user
        self.enabled_at = timezone.now()
        self.save()

    def disable(self):
        self.is_enabled = False
        self.enabled_by = None
        self.enabled_at = None
        self.save()
