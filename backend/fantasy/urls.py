from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .governance_views import (
    FantasyScoringRuleViewSet,
    FantasyTransferRuleViewSet,
    FantasySquadRuleViewSet,
    FantasyPriceStructureViewSet,
    FantasyEligibilityRuleViewSet,
    FantasyCompetitionMappingViewSet,
    FantasyFeatureFlagViewSet,
)

# Governance router
governance_router = DefaultRouter()
governance_router.register(
    r"scoring-rules", FantasyScoringRuleViewSet, basename="fantasy-scoring-rule"
)
governance_router.register(
    r"transfer-rules", FantasyTransferRuleViewSet, basename="fantasy-transfer-rule"
)
governance_router.register(
    r"squad-rules", FantasySquadRuleViewSet, basename="fantasy-squad-rule"
)
governance_router.register(
    r"price-structures",
    FantasyPriceStructureViewSet,
    basename="fantasy-price-structure",
)
governance_router.register(
    r"eligibility-rules",
    FantasyEligibilityRuleViewSet,
    basename="fantasy-eligibility-rule",
)
governance_router.register(
    r"competition-mappings",
    FantasyCompetitionMappingViewSet,
    basename="fantasy-competition-mapping",
)
governance_router.register(
    r"feature-flags", FantasyFeatureFlagViewSet, basename="fantasy-feature-flag"
)

urlpatterns = [
    # Original fantasy endpoints
    path("competitions/", views.fantasy_competition_list_view, name="fantasy-competition-list"),
    path("competitions/<int:competition_id>/", views.fantasy_competition_detail_view, name="fantasy-competition-detail"),
    path("competitions/<int:competition_id>/gameweeks/", views.fantasy_competition_gameweeks_view, name="fantasy-competition-gameweeks"),
    path("competitions/<int:competition_id>/players/", views.fantasy_player_market_view, name="fantasy-player-market"),
    path("teams/", views.fantasy_team_create_view, name="fantasy-team-create"),
    path("teams/me/", views.my_fantasy_teams_view, name="fantasy-my-teams"),
    path("teams/<int:team_id>/", views.fantasy_team_detail_view, name="fantasy-team-detail"),
    path("teams/<int:team_id>/history/", views.fantasy_team_history_view, name="fantasy-team-history"),
    path("teams/<int:team_id>/squad/", views.fantasy_team_squad_update_view, name="fantasy-team-squad-update"),
    path("teams/<int:team_id>/lineups/", views.fantasy_team_lineup_submit_view, name="fantasy-team-lineup-submit"),
    path("lineups/me/", views.my_lineups_view, name="fantasy-my-lineups"),
    path("leagues/", views.fantasy_league_create_view, name="fantasy-league-create"),
    path("leagues/available/", views.fantasy_league_available_view, name="fantasy-league-available"),
    path("leagues/join/", views.fantasy_league_join_view, name="fantasy-league-join"),
    path("leagues/my/", views.my_fantasy_leagues_view, name="fantasy-my-leagues"),
    path("leagues/<int:league_id>/", views.fantasy_league_detail_view, name="fantasy-league-detail"),
    path("leagues/<int:league_id>/leaderboard/", views.fantasy_league_leaderboard_view, name="fantasy-league-leaderboard"),
    path("gameweeks/<int:gameweek_id>/leaderboard/", views.fantasy_gameweek_leaderboard_view, name="fantasy-gameweek-leaderboard"),
    path("admin/competitions/", views.admin_fantasy_competition_create_view, name="fantasy-admin-competition-create"),
    path("admin/gameweeks/", views.admin_fantasy_gameweek_create_view, name="fantasy-admin-gameweek-create"),
    path("admin/players/", views.admin_fantasy_player_create_view, name="fantasy-admin-player-create"),
    path("admin/players/<int:player_id>/price/", views.admin_fantasy_player_price_update_view, name="fantasy-admin-player-price-update"),
    path("admin/gameweeks/<int:gameweek_id>/player-scores/", views.admin_gameweek_player_score_view, name="fantasy-admin-player-score"),
    path("admin/player-scores/<int:score_id>/approve/", views.admin_player_score_approve_view, name="fantasy-admin-player-score-approve"),
    path("admin/gameweeks/<int:gameweek_id>/calculate/", views.admin_gameweek_calculate_view, name="fantasy-admin-gameweek-calculate"),
    path("admin/gameweeks/<int:gameweek_id>/close/", views.admin_gameweek_close_view, name="fantasy-admin-gameweek-close"),
    path("admin/dashboard/", views.admin_fantasy_dashboard_view, name="fantasy-admin-dashboard"),
    path("admin/competitions/<int:competition_id>/", views.admin_fantasy_competition_detail_update_view, name="fantasy-admin-competition-detail-update"),
    path("admin/gameweeks/<int:gameweek_id>/", views.admin_fantasy_gameweek_detail_update_view, name="fantasy-admin-gameweek-detail-update"),
    path("admin/players/<int:player_id>/", views.admin_fantasy_player_detail_update_view, name="fantasy-admin-player-detail-update"),
    path("admin/players/<int:player_id>/recalculate-price/", views.admin_fantasy_player_recalculate_price_view, name="fantasy-admin-player-recalculate-price"),
    path("admin/player-scores/<int:score_id>/", views.admin_player_score_detail_update_view, name="fantasy-admin-player-score-detail-update"),
    path("admin/player-scores/<int:score_id>/reject/", views.admin_player_score_reject_view, name="fantasy-admin-player-score-reject"),
    # Governance endpoints
    path("", include(governance_router.urls)),
]
