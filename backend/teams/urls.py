from django.urls import path

from .views import (
    player_registration_detail_view,
    player_registration_list_create_view,
    player_transfer_detail_view,
    player_transfer_list_create_view,
    squad_detail_view,
    squad_list_create_view,
    squad_member_detail_view,
    squad_member_list_create_view,
    squad_submission_detail_view,
    squad_submission_list_create_view,
    squad_submission_review_view,
    staff_member_detail_view,
    staff_member_list_create_view,
    team_detail_view,
    team_list_create_view,
)

urlpatterns = [
    # Teams
    path("teams/", team_list_create_view, name="team-list-create"),
    path("teams/<int:pk>/", team_detail_view, name="team-detail"),
    # Squads
    path("squads/", squad_list_create_view, name="squad-list-create"),
    path("squads/<int:pk>/", squad_detail_view, name="squad-detail"),
    # Squad Members
    path(
        "squads/<int:squad_pk>/members/",
        squad_member_list_create_view,
        name="squad-member-list-create",
    ),
    path(
        "squads/<int:squad_pk>/members/<int:pk>/",
        squad_member_detail_view,
        name="squad-member-detail",
    ),
    # Player Registrations
    path(
        "players/",
        player_registration_list_create_view,
        name="player-registration-list-create",
    ),
    path(
        "players/<int:pk>/",
        player_registration_detail_view,
        name="player-registration-detail",
    ),
    # Staff Members
    path(
        "staff/",
        staff_member_list_create_view,
        name="staff-member-list-create",
    ),
    path(
        "staff/<int:pk>/",
        staff_member_detail_view,
        name="staff-member-detail",
    ),
    # Player Transfers
    path(
        "transfers/",
        player_transfer_list_create_view,
        name="player-transfer-list-create",
    ),
    path(
        "transfers/<int:pk>/",
        player_transfer_detail_view,
        name="player-transfer-detail",
    ),
    # Squad Submissions
    path(
        "submissions/",
        squad_submission_list_create_view,
        name="squad-submission-list-create",
    ),
    path(
        "submissions/<int:pk>/",
        squad_submission_detail_view,
        name="squad-submission-detail",
    ),
    # Union review of squad submissions
    path(
        "submissions/<int:pk>/review/",
        squad_submission_review_view,
        name="squad-submission-review",
    ),
]
