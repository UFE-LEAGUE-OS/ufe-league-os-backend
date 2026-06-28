from django.contrib import admin

from .models import (
    MVPNomination,
    MVPVote,
    Poll,
    PollOption,
    PollVote,
    Quiz,
    QuizAnswer,
    QuizAnswerSubmission,
    QuizQuestion,
    QuizSubmission,
    Sport,
)


@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    list_display = ["name", "sport_type", "is_active", "created_at"]
    list_filter = ["sport_type", "is_active"]
    search_fields = ["name"]


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ["title", "sport", "created_by", "is_active", "created_at"]
    list_filter = ["sport", "is_active", "allow_multiple_votes"]
    search_fields = ["title", "description"]


@admin.register(PollOption)
class PollOptionAdmin(admin.ModelAdmin):
    list_display = ["poll", "label", "order", "vote_count"]
    list_filter = ["poll__sport"]
    search_fields = ["label"]


@admin.register(PollVote)
class PollVoteAdmin(admin.ModelAdmin):
    list_display = ["poll", "option", "voter", "created_at"]
    list_filter = ["poll__sport"]
    search_fields = ["voter__email", "poll__title"]


@admin.register(MVPNomination)
class MVPNominationAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "sport",
        "nominee",
        "created_by",
        "is_active",
        "created_at",
    ]
    list_filter = ["sport", "is_active"]
    search_fields = ["title", "nominee__email"]


@admin.register(MVPVote)
class MVPVoteAdmin(admin.ModelAdmin):
    list_display = ["nomination", "voter", "created_at"]
    list_filter = ["nomination__sport"]
    search_fields = ["voter__email"]


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ["title", "sport", "created_by", "is_active", "created_at"]
    list_filter = ["sport", "is_active"]
    search_fields = ["title", "description"]


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ["quiz", "question_text", "order", "points"]
    list_filter = ["quiz__sport"]
    search_fields = ["question_text"]


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = ["question", "answer_text", "is_correct", "order"]


@admin.register(QuizSubmission)
class QuizSubmissionAdmin(admin.ModelAdmin):
    list_display = ["quiz", "participant", "score", "passed", "completed_at"]
    list_filter = ["quiz__sport", "passed"]
    search_fields = ["participant__email", "quiz__title"]


@admin.register(QuizAnswerSubmission)
class QuizAnswerSubmissionAdmin(admin.ModelAdmin):
    list_display = ["submission", "question", "selected_answer", "is_correct"]
    list_filter = ["submission__quiz__sport"]
    search_fields = ["submission__participant__email"]
