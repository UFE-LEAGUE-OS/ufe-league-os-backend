from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User

from .models import MVPNomination, Poll, Quiz, QuizSubmission, Sport
from .serializers import (
    MVPNominationSerializer,
    MVPNominationCreateSerializer,
    MVPVoteCreateSerializer,
    MVPVoteSerializer,
    PollCreateSerializer,
    PollSerializer,
    PollVoteSerializer,
    PollVoteCreateSerializer,
    QuizCreateSerializer,
    QuizQuestionCreateSerializer,
    QuizQuestionSerializer,
    QuizSerializer,
    QuizSubmissionCreateSerializer,
    QuizSubmissionSerializer,
    SportSerializer,
)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def sports_view(request):
    if request.method == "GET":
        sports = Sport.objects.filter(is_active=True)
        serializer = SportSerializer(sports, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.user.role not in [User.Role.CLUB_ADMIN, User.Role.SUPER_ADMIN]:
        return Response(
            {"detail": "You do not have permission to create sports."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = SportSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def polls_view(request):
    if request.method == "GET":
        sport_id = request.query_params.get("sport")
        polls = Poll.objects.select_related("sport", "created_by").filter(
            is_active=True
        )

        if sport_id:
            polls = polls.filter(sport_id=sport_id)

        return Response(
            {
                "count": polls.count(),
                "results": PollSerializer(
                    polls, many=True, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    serializer = PollCreateSerializer(data=request.data, context={"request": request})
    if serializer.is_valid():
        poll = serializer.save()
        poll_data = PollSerializer(poll, context={"request": request}).data
        return Response(poll_data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def poll_detail_view(request, poll_id):
    poll = Poll.objects.select_related("sport", "created_by").filter(id=poll_id).first()

    if poll is None:
        return Response(
            {"detail": "Poll not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            PollSerializer(poll, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    if poll.created_by != request.user and request.user.role not in [
        User.Role.CLUB_ADMIN,
        User.Role.SUPER_ADMIN,
    ]:
        return Response(
            {"detail": "You do not have permission to modify this poll."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "PATCH":
        serializer = PollCreateSerializer(poll, data=request.data, partial=True)
        if serializer.is_valid():
            poll = serializer.save()
            return Response(
                PollSerializer(poll, context={"request": request}).data,
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    poll.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def poll_vote_view(request, poll_id):
    data = request.data.copy()
    data["poll"] = poll_id
    serializer = PollVoteCreateSerializer(data=data, context={"request": request})
    if serializer.is_valid():
        vote = serializer.save()
        return Response(
            PollVoteSerializer(vote, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def mvp_nominations_view(request):
    if request.method == "GET":
        sport_id = request.query_params.get("sport")
        nominations = MVPNomination.objects.select_related(
            "sport", "created_by", "nominee"
        ).filter(is_active=True)

        if sport_id:
            nominations = nominations.filter(sport_id=sport_id)

        return Response(
            {
                "count": nominations.count(),
                "results": MVPNominationSerializer(
                    nominations, many=True, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    serializer = MVPNominationCreateSerializer(
        data=request.data, context={"request": request}
    )
    if serializer.is_valid():
        nomination = serializer.save()
        return Response(
            MVPNominationSerializer(nomination, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mvp_vote_view(request):
    serializer = MVPVoteCreateSerializer(
        data=request.data, context={"request": request}
    )
    if serializer.is_valid():
        vote = serializer.save()
        return Response(
            MVPVoteSerializer(vote, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def quizzes_view(request):
    if request.method == "GET":
        sport_id = request.query_params.get("sport")
        quizzes = Quiz.objects.select_related("sport", "created_by").filter(
            is_active=True
        )

        if sport_id:
            quizzes = quizzes.filter(sport_id=sport_id)

        return Response(
            {
                "count": quizzes.count(),
                "results": QuizSerializer(
                    quizzes, many=True, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    serializer = QuizCreateSerializer(data=request.data, context={"request": request})
    if serializer.is_valid():
        quiz = serializer.save()
        return Response(
            QuizSerializer(quiz, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def quiz_detail_view(request, quiz_id):
    quiz = Quiz.objects.select_related("sport", "created_by").filter(id=quiz_id).first()

    if quiz is None:
        return Response(
            {"detail": "Quiz not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            QuizSerializer(quiz, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    if quiz.created_by != request.user and request.user.role not in [
        User.Role.CLUB_ADMIN,
        User.Role.SUPER_ADMIN,
    ]:
        return Response(
            {"detail": "You do not have permission to modify this quiz."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "PATCH":
        serializer = QuizCreateSerializer(quiz, data=request.data, partial=True)
        if serializer.is_valid():
            quiz = serializer.save()
            return Response(
                QuizSerializer(quiz, context={"request": request}).data,
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    quiz.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def quiz_question_create_view(request, quiz_id):
    quiz = Quiz.objects.filter(id=quiz_id).first()

    if quiz is None:
        return Response(
            {"detail": "Quiz not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if quiz.created_by != request.user and request.user.role not in [
        User.Role.CLUB_ADMIN,
        User.Role.SUPER_ADMIN,
    ]:
        return Response(
            {"detail": "You do not have permission to add questions to this quiz."},
            status=status.HTTP_403_FORBIDDEN,
        )

    request.data["quiz"] = quiz_id
    serializer = QuizQuestionCreateSerializer(data=request.data)
    if serializer.is_valid():
        question = serializer.save()
        return Response(
            QuizQuestionSerializer(question, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def quiz_submit_view(request):
    serializer = QuizSubmissionCreateSerializer(
        data=request.data, context={"request": request}
    )
    if serializer.is_valid():
        submission = serializer.save()
        return Response(
            QuizSubmissionSerializer(submission, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_quiz_submissions_view(request):
    submissions = QuizSubmission.objects.select_related("quiz").filter(
        participant=request.user
    )
    return Response(
        {
            "count": submissions.count(),
            "results": QuizSubmissionSerializer(
                submissions, many=True, context={"request": request}
            ).data,
        },
        status=status.HTTP_200_OK,
    )
