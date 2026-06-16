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

    union = models.ForeignKey(
        Union, on_delete=models.CASCADE, related_name="leagues"
    )
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
    round = models.CharField(max_length=100, blank=True, help_text="Matchweek, round, or group stage")
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
    form = models.CharField(
        max_length=50, blank=True, help_text="e.g. WWDLW"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position"]
        unique_together = ["competition", "club"]

    def __str__(self):
        return f"{self.club.name} - {self.competition.name} (Pos: {self.position})"