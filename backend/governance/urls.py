from django.urls import path

from . import views

urlpatterns = [
    # ---- Sport Variants ----
    path(
        "sport-variants/",
        views.sport_variant_list_create_view,
        name="sport-variant-list-create",
    ),
    path(
        "sport-variants/<int:pk>/",
        views.sport_variant_detail_view,
        name="sport-variant-detail",
    ),
    path(
        "sport-variants/<int:pk>/verify/",
        views.sport_variant_verify_view,
        name="sport-variant-verify",
    ),
    # ---- Competition Formats ----
    path(
        "competition-formats/",
        views.competition_format_list_create_view,
        name="competition-format-list-create",
    ),
    path(
        "competition-formats/<int:pk>/",
        views.competition_format_detail_view,
        name="competition-format-detail",
    ),
    path(
        "competition-formats/<int:pk>/verify/",
        views.competition_format_verify_view,
        name="competition-format-verify",
    ),
    # ---- Rules & Standards ----
    path(
        "rules/",
        views.rule_list_create_view,
        name="rule-list-create",
    ),
    path(
        "rules/<int:pk>/",
        views.rule_detail_view,
        name="rule-detail",
    ),
    path(
        "rules/<int:pk>/publish/",
        views.rule_publish_view,
        name="rule-publish",
    ),
    path(
        "rules/<int:pk>/unpublish/",
        views.rule_unpublish_view,
        name="rule-unpublish",
    ),
    # ---- Publish Standards to Leagues ----
    path(
        "league-standards/",
        views.league_standard_list_create_view,
        name="league-standard-list-create",
    ),
    path(
        "league-standards/<int:pk>/",
        views.league_standard_remove_view,
        name="league-standard-remove",
    ),
    path(
        "leagues/<int:league_pk>/standards/",
        views.league_standards_by_league_view,
        name="league-standards-by-league",
    ),
]
