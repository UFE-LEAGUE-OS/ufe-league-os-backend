from django.urls import path

from .views import (
    player_registry_search_view,
    player_registration_detail_view,
    player_registration_list_create_view,
    player_registration_submission_decision_view,
    player_registration_submission_detail_view,
    player_registration_submission_list_create_view,
    player_registration_submission_resubmit_view,
    player_registration_submission_submit_view,
    player_registration_submission_withdraw_view,
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
from .transfer_views import (
    player_transfer_detail_view,
    player_transfer_list_create_view,
    player_transfer_submission_cancel_view,
    player_transfer_submission_consent_view,
    player_transfer_submission_decline_view,
    player_transfer_submission_detail_view,
    player_transfer_submission_list_create_view,
    player_transfer_submission_resubmit_view,
    player_transfer_submission_source_response_view,
    player_transfer_submission_submit_view,
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
    path(
        "player-registry-search/",
        player_registry_search_view,
        name="player-registry-search",
    ),
    path(
        "player-registration-submissions/",
        player_registration_submission_list_create_view,
        name="player-registration-submission-list-create",
    ),
    path(
        "player-registration-submissions/<int:pk>/",
        player_registration_submission_detail_view,
        name="player-registration-submission-detail",
    ),
    path(
        "player-registration-submissions/<int:pk>/submit/",
        player_registration_submission_submit_view,
        name="player-registration-submission-submit",
    ),
    path(
        "player-registration-submissions/<int:pk>/resubmit/",
        player_registration_submission_resubmit_view,
        name="player-registration-submission-resubmit",
    ),
    path(
        "player-registration-submissions/<int:pk>/withdraw/",
        player_registration_submission_withdraw_view,
        name="player-registration-submission-withdraw",
    ),
    path(
        "player-registration-submissions/<int:pk>/decision/",
        player_registration_submission_decision_view,
        name="player-registration-submission-decision",
    ),
    # Maintained Player Transfers
    path(
        "player-transfer-submissions/",
        player_transfer_submission_list_create_view,
        name="player-transfer-submission-list-create",
    ),
    path(
        "player-transfer-submissions/<int:pk>/",
        player_transfer_submission_detail_view,
        name="player-transfer-submission-detail",
    ),
    path(
        "player-transfer-submissions/<int:pk>/submit/",
        player_transfer_submission_submit_view,
        name="player-transfer-submission-submit",
    ),
    path(
        "player-transfer-submissions/<int:pk>/resubmit/",
        player_transfer_submission_resubmit_view,
        name="player-transfer-submission-resubmit",
    ),
    path(
        "player-transfer-submissions/<int:pk>/cancel/",
        player_transfer_submission_cancel_view,
        name="player-transfer-submission-cancel",
    ),
    path(
        "player-transfer-submissions/<int:pk>/source-response/",
        player_transfer_submission_source_response_view,
        name="player-transfer-submission-source-response",
    ),
    path(
        "player-transfer-submissions/<int:pk>/consent/",
        player_transfer_submission_consent_view,
        name="player-transfer-submission-consent",
    ),
    path(
        "player-transfer-submissions/<int:pk>/decline/",
        player_transfer_submission_decline_view,
        name="player-transfer-submission-decline",
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
