from rest_framework import serializers

from accounts.serializers import UserSummarySerializer
from .models import (
    MVPNomination,
    MVPVote,
    Poll,
    PollOption,
    PollVote,
    Quiz,
    QuizQuestion,
    QuizAnswer,
    QuizAnswerSubmission,
    QuizSubmission,
    Sport,
)


class SportSerializer(serializers.ModelSerializer):
    """Read serializer supporting list/retrieve of supported sports."""

    class Meta:
        model = Sport
        fields = ["id", "name", "sport_type", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class PollOptionSerializer(serializers.ModelSerializer):
    """Read serializer used in poll responses."""

    class Meta:
        model = PollOption
        fields = ["id", "label", "order", "vote_count"]
        read_only_fields = ["id", "vote_count"]


class PollSerializer(serializers.ModelSerializer):
    """Read serializer exposing active poll surveys."""

    options = PollOptionSerializer(many=True, read_only=True)
    created_by = UserSummarySerializer(read_only=True)
    sport = SportSerializer(read_only=True)

    class Meta:
        model = Poll
        fields = [
            "id",
            "title",
            "description",
            "sport",
            "created_by",
            "is_active",
            "is_public",
            "allow_multiple_votes",
            "starts_at",
            "ends_at",
            "options",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class PollCreateSerializer(serializers.ModelSerializer):
    """Write serializer for poll creation and updates."""

    options = serializers.ListField(
        child=serializers.CharField(max_length=255),
        allow_empty=False,
        write_only=True,
        min_length=2,
    )

    class Meta:
        model = Poll
        fields = [
            "title",
            "description",
            "sport",
            "is_active",
            "is_public",
            "allow_multiple_votes",
            "starts_at",
            "ends_at",
            "options",
        ]

    def create(self, validated_data):
        options_data = validated_data.pop("options")
        poll = Poll.objects.create(**validated_data)
        for index, label in enumerate(options_data):
            PollOption.objects.create(poll=poll, label=label, order=index)
        return poll

    def update(self, instance, validated_data):
        options_data = validated_data.pop("options", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if options_data is not None:
            instance.options.all().delete()
            for index, label in enumerate(options_data):
                PollOption.objects.create(poll=instance, label=label, order=index)

        return instance


class PollVoteSerializer(serializers.ModelSerializer):
    """Read serializer exposing poll submissions."""

    voter = UserSummarySerializer(read_only=True)
    option = PollOptionSerializer(read_only=True)

    class Meta:
        model = PollVote
        fields = ["id", "poll", "option", "voter", "created_at"]
        read_only_fields = ["id", "voter", "created_at"]


class PollVoteCreateSerializer(serializers.ModelSerializer):
    """Write serializer preventing duplicate votes per poll."""

    option = serializers.PrimaryKeyRelatedField(queryset=PollOption.objects.select_related("poll"))

    class Meta:
        model = PollVote
        fields = ["poll", "option"]

    def validate(self, attrs):
        poll = attrs["poll"]
        voter = self.context["request"].user

        if not poll.is_active:
            raise serializers.ValidationError("This poll is not active.")

        if PollVote.objects.filter(poll=poll, voter=voter).exists():
            raise serializers.ValidationError("You have already voted in this poll.")

        if attrs["option"].poll_id != poll.id:
            raise serializers.ValidationError("Invalid option for this poll.")

        return attrs

    def create(self, validated_data):
        vote = PollVote.objects.create(
            poll=validated_data["poll"],
            option=validated_data["option"],
            voter=self.context["request"].user,
        )
        option = validated_data["option"]
        option.vote_count += 1
        option.save(update_fields=["vote_count"])
        return vote


class MVPNominationSerializer(serializers.ModelSerializer):
    """Read serializer exposing active MVP nominations."""

    created_by = UserSummarySerializer(read_only=True)
    nominee = UserSummarySerializer(read_only=True)
    sport = SportSerializer(read_only=True)

    class Meta:
        model = MVPNomination
        fields = [
            "id",
            "title",
            "description",
            "sport",
            "created_by",
            "nominee",
            "is_active",
            "is_public",
            "starts_at",
            "ends_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class MVPNominationCreateSerializer(serializers.ModelSerializer):
    """Write serializer for MVP nomination creation."""

    class Meta:
        model = MVPNomination
        fields = [
            "title",
            "description",
            "sport",
            "nominee",
            "is_active",
            "is_public",
            "starts_at",
            "ends_at",
        ]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class MVPVoteSerializer(serializers.ModelSerializer):
    """Read serializer exposing MVP vote submissions."""

    voter = UserSummarySerializer(read_only=True)
    nomination = MVPNominationSerializer(read_only=True)

    class Meta:
        model = MVPVote
        fields = ["id", "nomination", "voter", "created_at"]
        read_only_fields = ["id", "voter", "created_at"]


class MVPVoteCreateSerializer(serializers.ModelSerializer):
    """Write serializer preventing duplicate votes per nomination."""

    nomination = serializers.PrimaryKeyRelatedField(queryset=MVPNomination.objects.select_related("sport"))

    class Meta:
        model = MVPVote
        fields = ["nomination"]

    def validate(self, attrs):
        nomination = attrs["nomination"]
        voter = self.context["request"].user

        if not nomination.is_active:
            raise serializers.ValidationError("This nomination is not active.")

        if MVPVote.objects.filter(nomination=nomination, voter=voter).exists():
            raise serializers.ValidationError("You have already voted for this nomination.")

        return attrs

    def create(self, validated_data):
        return MVPVote.objects.create(
            nomination=validated_data["nomination"],
            voter=self.context["request"].user,
        )


class QuizAnswerSerializer(serializers.ModelSerializer):
    """Read serializer exposing available quiz answers."""

    class Meta:
        model = QuizAnswer
        fields = ["id", "question", "answer_text", "is_correct", "order"]
        read_only_fields = ["id"]


class QuizQuestionSerializer(serializers.ModelSerializer):
    """Read serializer exposing quiz questions and answers."""

    answers = QuizAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = QuizQuestion
        fields = ["id", "quiz", "question_text", "order", "points", "answers"]
        read_only_fields = ["id"]


class QuizQuestionCreateSerializer(serializers.ModelSerializer):
    """Write serializer creating a question with at least 2 answers."""

    answers = serializers.ListField(
        child=serializers.ListField(
            child=serializers.CharField(max_length=255),
            min_length=2,
        ),
        allow_empty=False,
        write_only=True,
    )

    class Meta:
        model = QuizQuestion
        fields = ["quiz", "question_text", "order", "points", "answers"]

    def create(self, validated_data):
        answers_data = validated_data.pop("answers")
        question = QuizQuestion.objects.create(**validated_data)
        for index, answer_text in enumerate(answers_data):
            QuizAnswer.objects.create(question=question, answer_text=answer_text, order=index)
        return question


class QuizSerializer(serializers.ModelSerializer):
    """Read serializer for supported sports quiz engagement."""

    questions = QuizQuestionSerializer(many=True, read_only=True)
    created_by = UserSummarySerializer(read_only=True)
    sport = SportSerializer(read_only=True)

    class Meta:
        model = Quiz
        fields = [
            "id",
            "title",
            "description",
            "sport",
            "created_by",
            "is_active",
            "is_public",
            "passing_score",
            "time_limit_minutes",
            "starts_at",
            "ends_at",
            "questions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class QuizCreateSerializer(serializers.ModelSerializer):
    """Write serializer for quiz creation and updates."""

    class Meta:
        model = Quiz
        fields = [
            "title",
            "description",
            "sport",
            "is_active",
            "is_public",
            "passing_score",
            "time_limit_minutes",
            "starts_at",
            "ends_at",
        ]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class QuizAnswerSubmissionSerializer(serializers.ModelSerializer):
    """Write serializer mapping selected answers in a submission."""

    question = serializers.PrimaryKeyRelatedField(queryset=QuizQuestion.objects.select_related("quiz"))
    selected_answer = serializers.PrimaryKeyRelatedField(queryset=QuizAnswer.objects.all())

    class Meta:
        model = QuizAnswerSubmission
        fields = ["question", "selected_answer"]


class QuizSubmissionCreateSerializer(serializers.ModelSerializer):
    """Write serializer preventing duplicate submissions and computing score."""

    answers = QuizAnswerSubmissionSerializer(many=True)

    class Meta:
        model = QuizSubmission
        fields = ["quiz", "answers"]

    def validate(self, attrs):
        quiz = attrs["quiz"]
        participant = self.context["request"].user

        if not quiz.is_active:
            raise serializers.ValidationError("This quiz is not active.")

        if QuizSubmission.objects.filter(quiz=quiz, participant=participant).exists():
            raise serializers.ValidationError("You have already submitted this quiz.")

        provided_question_ids = {answer["question"].id for answer in attrs["answers"]}
        required_question_ids = set(quiz.questions.values_list("id", flat=True))

        if provided_question_ids != required_question_ids:
            raise serializers.ValidationError("You must answer all questions exactly once.")

        return attrs

    def create(self, validated_data):
        answers_data = validated_data.pop("answers")
        participant = self.context["request"].user
        quiz = validated_data["quiz"]
        submission = QuizSubmission.objects.create(quiz=quiz, participant=participant)

        score = 0
        for answer_data in answers_data:
            question = answer_data["question"]
            selected_answer = answer_data["selected_answer"]
            is_correct = selected_answer.is_correct
            if is_correct:
                score += question.points
            QuizAnswerSubmission.objects.create(
                submission=submission,
                question=question,
                selected_answer=selected_answer,
                is_correct=is_correct,
            )

        submission.score = score
        submission.passed = score >= quiz.passing_score
        submission.save(update_fields=["score", "passed"])
        return submission


class QuizSubmissionSerializer(serializers.ModelSerializer):
    """Read serializer exposing completed quiz attempts."""

    participant = UserSummarySerializer(read_only=True)

    class Meta:
        model = QuizSubmission
        fields = ["id", "quiz", "participant", "score", "passed", "completed_at"]
        read_only_fields = ["id", "participant", "completed_at"]