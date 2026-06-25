from django.urls import path

from . import views

urlpatterns = [
    path("sports/", views.sports_view, name="engagements-sports"),
    path("polls/", views.polls_view, name="engagements-polls"),
    path(
        "polls/<int:poll_id>/", views.poll_detail_view, name="engagements-poll-detail"
    ),
    path(
        "polls/<int:poll_id>/vote/", views.poll_vote_view, name="engagements-poll-vote"
    ),
    path(
        "mvp-nominations/",
        views.mvp_nominations_view,
        name="engagements-mvp-nominations",
    ),
    path("mvp-nominations/vote/", views.mvp_vote_view, name="engagements-mvp-vote"),
    path("quizzes/", views.quizzes_view, name="engagements-quizzes"),
    path(
        "quizzes/<int:quiz_id>/", views.quiz_detail_view, name="engagements-quiz-detail"
    ),
    path(
        "quizzes/<int:quiz_id>/questions/",
        views.quiz_question_create_view,
        name="engagements-quiz-questions",
    ),
    path("quizzes/submit/", views.quiz_submit_view, name="engagements-quiz-submit"),
    path(
        "quizzes/my-submissions/",
        views.my_quiz_submissions_view,
        name="engagements-my-quiz-submissions",
    ),
]
