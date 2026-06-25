from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q, UniqueConstraint


class Sport(models.Model):
    SPORTS_CHOICES = [
        ("football", "Football"),
        ("basketball", "Basketball"),
        ("volleyball", "Volleyball"),
        ("netball", "Netball"),
        ("rugby", "Rugby"),
        ("cricket", "Cricket"),
        ("athletics", "Athletics"),
        ("swimming", "Swimming"),
        ("boxing", "Boxing"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=100, unique=True)
    sport_type = models.CharField(max_length=50, choices=SPORTS_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Poll(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    sport = models.ForeignKey(Sport, on_delete=models.CASCADE, related_name="polls")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_polls"
    )
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    allow_multiple_votes = models.BooleanField(default=False)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class PollOption(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options")
    label = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    vote_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.poll.title} - {self.label}"


class PollVote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes")
    option = models.ForeignKey(
        PollOption, on_delete=models.CASCADE, related_name="votes"
    )
    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="poll_votes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["poll", "voter"],
                condition=~Q(poll__allow_multiple_votes=True),
                name="unique_poll_vote_per_user",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.voter.email} - {self.poll.title}"


class MVPNomination(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    sport = models.ForeignKey(
        Sport, on_delete=models.CASCADE, related_name="mvp_nominations"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_mvp_nominations",
    )
    nominee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mvp_nominations_received",
    )
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            UniqueConstraint(
                fields=["nominee", "sport", "created_by", "starts_at"],
                name="unique_mvp_nomination_per_nominee",
            )
        ]

    def __str__(self):
        return f"{self.nominee.email} - {self.title}"


class MVPVote(models.Model):
    nomination = models.ForeignKey(
        MVPNomination, on_delete=models.CASCADE, related_name="votes"
    )
    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mvp_votes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["nomination", "voter"],
                name="unique_mvp_vote_per_user",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.voter.email} voted for {self.nomination.nominee.email}"


class Quiz(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    sport = models.ForeignKey(Sport, on_delete=models.CASCADE, related_name="quizzes")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_quizzes",
    )
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    passing_score = models.PositiveIntegerField(
        default=70, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    question_text = models.TextField()
    order = models.PositiveIntegerField(default=0)
    points = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.quiz.title} - Q{self.order}"


class QuizAnswer(models.Model):
    question = models.ForeignKey(
        QuizQuestion, on_delete=models.CASCADE, related_name="answers"
    )
    answer_text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.question} - {self.answer_text}"


class QuizSubmission(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="submissions")
    participant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quiz_submissions",
    )
    score = models.PositiveIntegerField(default=0)
    passed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["quiz", "participant"],
                name="unique_quiz_submission_per_user",
            )
        ]
        ordering = ["-completed_at"]

    def __str__(self):
        return f"{self.participant.email} - {self.quiz.title}"


class QuizAnswerSubmission(models.Model):
    submission = models.ForeignKey(
        QuizSubmission, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(
        QuizQuestion, on_delete=models.CASCADE, related_name="submissions"
    )
    selected_answer = models.ForeignKey(
        QuizAnswer, on_delete=models.CASCADE, related_name="+"
    )
    is_correct = models.BooleanField(default=False)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["submission", "question"],
                name="unique_answer_per_question_in_submission",
            )
        ]
        ordering = ["question__order"]

    def __str__(self):
        return f"{self.submission} - Q{self.question.order}"
