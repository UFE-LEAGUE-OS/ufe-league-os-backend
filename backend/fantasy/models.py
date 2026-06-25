from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class FantasyCompetition(models.Model):
    """
    A fantasy competition linked to a real League OS competition.

    Example:
    Real competition: Nile Special Rugby Premiership 2026
    Fantasy competition: Nile Special Rugby Fantasy 2026
    """

    class Sport(models.TextChoices):
        RUGBY = "RUGBY", "Rugby"
        FOOTBALL = "FOOTBALL", "Football"
        BASKETBALL = "BASKETBALL", "Basketball"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        OPEN = "OPEN", "Open"
        LOCKED = "LOCKED", "Locked"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)

    linked_competition = models.ForeignKey(
        "dashboards.Competition",
        on_delete=models.CASCADE,
        related_name="fantasy_competitions",
    )

    sport = models.CharField(
        max_length=30,
        choices=Sport.choices,
        default=Sport.RUGBY,
    )
    season = models.CharField(max_length=50, blank=True)

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    budget = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("100.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    squad_size = models.PositiveIntegerField(default=15)
    lineup_size = models.PositiveIntegerField(default=15)
    max_players_per_club = models.PositiveIntegerField(default=4)

    captain_multiplier = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("2.00"),
        validators=[
            MinValueValidator(Decimal("1.00")),
            MaxValueValidator(Decimal("5.00")),
        ],
    )

    min_player_price = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("4.00"),
    )
    max_player_price = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("15.00"),
    )
    default_player_price = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("5.00"),
    )

    rules_summary = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_fantasy_competitions",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "name"]
        indexes = [
            models.Index(fields=["status", "sport"]),
            models.Index(fields=["linked_competition", "status"]),
        ]

    def __str__(self):
        return self.name

    @property
    def is_open_for_team_creation(self):
        return self.status == self.Status.OPEN


class FantasyGameweek(models.Model):
    """
    A scoring round inside a fantasy competition.

    A gameweek has a lock time. Fans cannot edit lineups after lock_at.
    """

    class Status(models.TextChoices):
        UPCOMING = "UPCOMING", "Upcoming"
        OPEN = "OPEN", "Open"
        LOCKED = "LOCKED", "Locked"
        SCORING = "SCORING", "Scoring"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    fantasy_competition = models.ForeignKey(
        FantasyCompetition,
        on_delete=models.CASCADE,
        related_name="gameweeks",
    )
    name = models.CharField(max_length=120)
    number = models.PositiveIntegerField()

    matches = models.ManyToManyField(
        "dashboards.Match",
        blank=True,
        related_name="fantasy_gameweeks",
    )

    start_at = models.DateTimeField()
    lock_at = models.DateTimeField()
    end_at = models.DateTimeField()

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.UPCOMING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["fantasy_competition", "number"]
        unique_together = ["fantasy_competition", "number"]
        indexes = [
            models.Index(fields=["fantasy_competition", "status"]),
            models.Index(fields=["lock_at", "status"]),
        ]

    def __str__(self):
        return f"{self.fantasy_competition.name} - {self.name}"

    @property
    def is_locked(self):
        return timezone.now() >= self.lock_at or self.status in [
            self.Status.LOCKED,
            self.Status.SCORING,
            self.Status.COMPLETED,
        ]

    @property
    def can_submit_lineup(self):
        return (
            self.status in [self.Status.UPCOMING, self.Status.OPEN]
            and not self.is_locked
        )


class FantasyPlayer(models.Model):
    """
    Player available in a fantasy competition.

    This model exists because the current backend does not yet have a full
    official Player model. Later, this can be linked to the official player
    registration model.
    """

    class Position(models.TextChoices):
        PROP = "PROP", "Prop"
        HOOKER = "HOOKER", "Hooker"
        LOCK = "LOCK", "Lock"
        BACK_ROW = "BACK_ROW", "Back Row"
        SCRUM_HALF = "SCRUM_HALF", "Scrum Half"
        FLY_HALF = "FLY_HALF", "Fly Half"
        CENTRE = "CENTRE", "Centre"
        WING = "WING", "Wing"
        FULLBACK = "FULLBACK", "Fullback"

        GOALKEEPER = "GOALKEEPER", "Goalkeeper"
        DEFENDER = "DEFENDER", "Defender"
        MIDFIELDER = "MIDFIELDER", "Midfielder"
        FORWARD = "FORWARD", "Forward"

        GUARD = "GUARD", "Guard"
        FORWARD_BASKETBALL = "FORWARD_BASKETBALL", "Basketball Forward"
        CENTER_BASKETBALL = "CENTER_BASKETBALL", "Basketball Center"

        UTILITY = "UTILITY", "Utility"

    class PriceSource(models.TextChoices):
        AUTO = "AUTO", "Auto Calculated"
        MANUAL = "MANUAL", "Manual Override"

    fantasy_competition = models.ForeignKey(
        FantasyCompetition,
        on_delete=models.CASCADE,
        related_name="players",
    )
    club = models.ForeignKey(
        "accounts.Club",
        on_delete=models.CASCADE,
        related_name="fantasy_players",
    )

    display_name = models.CharField(max_length=160)
    position = models.CharField(
        max_length=40,
        choices=Position.choices,
        default=Position.UTILITY,
    )

    calculated_price = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("5.00"),
    )
    final_price = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("5.00"),
    )
    price_source = models.CharField(
        max_length=20,
        choices=PriceSource.choices,
        default=PriceSource.AUTO,
    )
    price_override_reason = models.TextField(blank=True)
    price_locked_at = models.DateTimeField(blank=True, null=True)

    previous_stats = models.JSONField(default=dict, blank=True)
    current_form = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    availability_note = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name"]
        unique_together = ["fantasy_competition", "display_name", "club"]
        indexes = [
            models.Index(fields=["fantasy_competition", "is_active"]),
            models.Index(fields=["club", "position"]),
            models.Index(fields=["final_price"]),
        ]

    def __str__(self):
        return f"{self.display_name} - {self.club.name}"


class FantasyTeam(models.Model):
    """
    A fan's fantasy team for one fantasy competition.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fantasy_teams",
    )
    fantasy_competition = models.ForeignKey(
        FantasyCompetition,
        on_delete=models.CASCADE,
        related_name="teams",
    )
    name = models.CharField(max_length=120)

    total_points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    current_rank = models.PositiveIntegerField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["fantasy_competition", "current_rank", "name"]
        unique_together = ["owner", "fantasy_competition"]
        indexes = [
            models.Index(fields=["owner", "fantasy_competition"]),
            models.Index(fields=["fantasy_competition", "-total_points"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.owner.email})"

    @property
    def active_squad_count(self):
        return self.squad_players.filter(is_active=True).count()

    @property
    def budget_used(self):
        total = Decimal("0.00")
        for squad_player in self.squad_players.filter(is_active=True):
            total += squad_player.price_at_selection
        return total

    @property
    def budget_remaining(self):
        return self.fantasy_competition.budget - self.budget_used


class FantasySquadPlayer(models.Model):
    """
    Player selected into a fan's fantasy squad.
    """

    fantasy_team = models.ForeignKey(
        FantasyTeam,
        on_delete=models.CASCADE,
        related_name="squad_players",
    )
    fantasy_player = models.ForeignKey(
        FantasyPlayer,
        on_delete=models.CASCADE,
        related_name="squad_selections",
    )
    price_at_selection = models.DecimalField(max_digits=6, decimal_places=2)

    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["fantasy_team", "fantasy_player"],
                condition=Q(is_active=True),
                name="unique_active_fantasy_squad_player",
            )
        ]

    def __str__(self):
        return f"{self.fantasy_team.name} - {self.fantasy_player.display_name}"


class FantasyLineup(models.Model):
    """
    A submitted lineup for a specific fantasy team and gameweek.
    """

    fantasy_team = models.ForeignKey(
        FantasyTeam,
        on_delete=models.CASCADE,
        related_name="lineups",
    )
    gameweek = models.ForeignKey(
        FantasyGameweek,
        on_delete=models.CASCADE,
        related_name="lineups",
    )

    captain = models.ForeignKey(
        FantasyPlayer,
        on_delete=models.PROTECT,
        related_name="captain_lineups",
    )
    vice_captain = models.ForeignKey(
        FantasyPlayer,
        on_delete=models.PROTECT,
        related_name="vice_captain_lineups",
        blank=True,
        null=True,
    )

    submitted_at = models.DateTimeField(auto_now=True)
    locked_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["gameweek", "fantasy_team"]
        unique_together = ["fantasy_team", "gameweek"]
        indexes = [
            models.Index(fields=["gameweek", "submitted_at"]),
        ]

    def __str__(self):
        return f"{self.fantasy_team.name} - {self.gameweek.name}"

    @property
    def is_locked(self):
        return self.locked_at is not None or self.gameweek.is_locked


class FantasyLineupPlayer(models.Model):
    """
    Player selected in a gameweek lineup.
    """

    lineup = models.ForeignKey(
        FantasyLineup,
        on_delete=models.CASCADE,
        related_name="players",
    )
    fantasy_player = models.ForeignKey(
        FantasyPlayer,
        on_delete=models.CASCADE,
        related_name="lineup_entries",
    )
    is_starter = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        unique_together = ["lineup", "fantasy_player"]

    def __str__(self):
        return f"{self.lineup} - {self.fantasy_player.display_name}"


class FantasyLeague(models.Model):
    """
    Public or private fantasy mini-league.
    """

    class LeagueType(models.TextChoices):
        PUBLIC = "PUBLIC", "Public"
        PRIVATE = "PRIVATE", "Private"

    fantasy_competition = models.ForeignKey(
        FantasyCompetition,
        on_delete=models.CASCADE,
        related_name="fantasy_leagues",
    )
    name = models.CharField(max_length=160)
    league_type = models.CharField(
        max_length=20,
        choices=LeagueType.choices,
        default=LeagueType.PUBLIC,
    )
    join_code = models.CharField(max_length=20, blank=True, null=True, unique=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_fantasy_leagues",
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fantasy_competition", "name"]
        unique_together = ["fantasy_competition", "name"]

    def save(self, *args, **kwargs):
        if self.league_type == self.LeagueType.PRIVATE and not self.join_code:
            self.join_code = uuid4().hex[:8].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class FantasyLeagueMembership(models.Model):
    """
    Links a fantasy team to a fantasy league.
    """

    fantasy_league = models.ForeignKey(
        FantasyLeague,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    fantasy_team = models.ForeignKey(
        FantasyTeam,
        on_delete=models.CASCADE,
        related_name="league_memberships",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at"]
        unique_together = ["fantasy_league", "fantasy_team"]

    def __str__(self):
        return f"{self.fantasy_team.name} in {self.fantasy_league.name}"


class FantasyPlayerGameweekScore(models.Model):
    """
    Manual or approved fantasy score for one real player in one gameweek.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    fantasy_player = models.ForeignKey(
        FantasyPlayer,
        on_delete=models.CASCADE,
        related_name="gameweek_scores",
    )
    gameweek = models.ForeignKey(
        FantasyGameweek,
        on_delete=models.CASCADE,
        related_name="player_scores",
    )
    match = models.ForeignKey(
        "dashboards.Match",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fantasy_player_scores",
    )

    points = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    breakdown = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="entered_fantasy_scores",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_fantasy_scores",
    )
    approved_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["gameweek", "fantasy_player"]
        unique_together = ["fantasy_player", "gameweek"]
        indexes = [
            models.Index(fields=["gameweek", "status"]),
            models.Index(fields=["fantasy_player", "gameweek"]),
        ]

    def __str__(self):
        return (
            f"{self.fantasy_player.display_name} - {self.gameweek.name}: {self.points}"
        )


class FantasyTransferWindow(models.Model):
    """
    A transfer window controls when fans can change fantasy squads.

    Example:
    - Gameweek 1 transfer window
    - Mid-season transfer window
    """

    fantasy_competition = models.ForeignKey(
        FantasyCompetition,
        on_delete=models.CASCADE,
        related_name="transfer_windows",
    )
    gameweek = models.ForeignKey(
        FantasyGameweek,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfer_windows",
    )

    name = models.CharField(max_length=160)

    opens_at = models.DateTimeField()
    closes_at = models.DateTimeField()

    is_active = models.BooleanField(default=True)

    free_transfers = models.PositiveIntegerField(default=1)
    max_transfers_per_window = models.PositiveIntegerField(default=3)

    points_cost_per_extra_transfer = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("4.00"),
    )

    allow_trades = models.BooleanField(
        default=False,
        help_text=(
            "Reserved for future team-to-team trade flows. "
            "MVP transfers use direct player swaps."
        ),
    )
    allow_transfers_after_lineup_lock = models.BooleanField(default=False)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["fantasy_competition", "opens_at"]
        indexes = [
            models.Index(fields=["fantasy_competition", "is_active"]),
            models.Index(fields=["opens_at", "closes_at"]),
            models.Index(fields=["gameweek"]),
        ]

    def __str__(self):
        return f"{self.fantasy_competition.name} - {self.name}"

    @property
    def is_open(self):
        now = timezone.now()
        return self.is_active and self.opens_at <= now <= self.closes_at


class FantasyTransfer(models.Model):
    """
    Records a fantasy squad transfer.

    MVP meaning:
    - TRANSFER: normal fantasy squad swap
    - TRADE: reserved label for future trade-style flows
    """

    class TransferType(models.TextChoices):
        TRANSFER = "TRANSFER", "Transfer"
        TRADE = "TRADE", "Trade"

    class Status(models.TextChoices):
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    fantasy_team = models.ForeignKey(
        FantasyTeam,
        on_delete=models.CASCADE,
        related_name="transfers",
    )
    fantasy_competition = models.ForeignKey(
        FantasyCompetition,
        on_delete=models.CASCADE,
        related_name="transfers",
    )
    transfer_window = models.ForeignKey(
        FantasyTransferWindow,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers",
    )
    gameweek = models.ForeignKey(
        FantasyGameweek,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers",
    )

    player_out = models.ForeignKey(
        FantasyPlayer,
        on_delete=models.PROTECT,
        related_name="transfers_out",
    )
    player_in = models.ForeignKey(
        FantasyPlayer,
        on_delete=models.PROTECT,
        related_name="transfers_in",
    )

    transfer_type = models.CharField(
        max_length=30,
        choices=TransferType.choices,
        default=TransferType.TRANSFER,
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.COMPLETED,
    )

    points_cost = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_fantasy_transfers",
    )

    reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["fantasy_team", "status"]),
            models.Index(fields=["fantasy_competition", "created_at"]),
            models.Index(fields=["transfer_window", "status"]),
            models.Index(fields=["gameweek", "status"]),
        ]

    def __str__(self):
        return (
            f"{self.fantasy_team.name}: "
            f"{self.player_out.display_name} -> {self.player_in.display_name}"
        )


class FantasyTeamGameweekScore(models.Model):
    """
    Calculated score for a fan's fantasy team in one gameweek.
    """

    fantasy_team = models.ForeignKey(
        FantasyTeam,
        on_delete=models.CASCADE,
        related_name="gameweek_scores",
    )
    gameweek = models.ForeignKey(
        FantasyGameweek,
        on_delete=models.CASCADE,
        related_name="team_scores",
    )

    points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    rank = models.PositiveIntegerField(blank=True, null=True)
    breakdown = models.JSONField(default=dict, blank=True)

    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["gameweek", "rank", "-points"]
        unique_together = ["fantasy_team", "gameweek"]
        indexes = [
            models.Index(fields=["gameweek", "-points"]),
            models.Index(fields=["fantasy_team", "gameweek"]),
        ]

    def __str__(self):
        return f"{self.fantasy_team.name} - {self.gameweek.name}: {self.points}"
