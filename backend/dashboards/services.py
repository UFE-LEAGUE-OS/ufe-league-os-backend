"""
Services for the dashboards app.

Provides standings calculation logic and live match update broadcasting.
"""

from django.db.models import F, Q, Sum

from .models import Competition, Match, Standing


def recalculate_standings(competition_id):
    """
    Recalculate (or create) standing entries for all clubs in a competition
    based on completed match results.

    This is the authoritative calculation engine for the standings table.
    It scans all completed matches for the given competition and computes:

        played, won, drawn, lost, goals_for, goals_against,
        goal_difference, points, form

    Returns a list of Standing records ordered by position.
    """
    competition = Competition.objects.get(id=competition_id)
    matches = Match.objects.filter(
        competition=competition,
        status=Match.Status.COMPLETED,
        home_score__isnull=False,
        away_score__isnull=False,
    )

    # Collect all clubs that have played in this competition
    club_ids = set(matches.values_list("home_club_id", flat=True)) | set(
        matches.values_list("away_club_id", flat=True)
    )

    standings_data = []
    for club_id in club_ids:
        # Matches where this club is home
        home_matches = matches.filter(home_club_id=club_id)
        # Matches where this club is away
        away_matches = matches.filter(away_club_id=club_id)

        played_home = home_matches.count()
        played_away = away_matches.count()
        played = played_home + played_away

        # Wins: home goals > away goals when club is home, and vice versa when away
        home_wins = home_matches.filter(home_score__gt=F("away_score")).count()
        away_wins = away_matches.filter(away_score__gt=F("home_score")).count()
        won = home_wins + away_wins

        # Draws: scores equal in any match
        home_draws = home_matches.filter(home_score=F("away_score")).count()
        away_draws = away_matches.filter(away_score=F("home_score")).count()
        drawn = home_draws + away_draws

        lost = played - won - drawn

        # Goals
        home_gf = home_matches.aggregate(total=Sum("home_score"))["total"] or 0
        away_gf = away_matches.aggregate(total=Sum("away_score"))["total"] or 0
        goals_for = home_gf + away_gf

        home_ga = home_matches.aggregate(total=Sum("away_score"))["total"] or 0
        away_ga = away_matches.aggregate(total=Sum("home_score"))["total"] or 0
        goals_against = home_ga + away_ga

        goal_difference = goals_for - goals_against
        points = (won * 3) + drawn

        # Form: last 5 matches in chronological order (most recent first)
        club_matches = list(
            matches.filter(Q(home_club_id=club_id) | Q(away_club_id=club_id)).order_by(
                "-match_date"
            )[:5]
        )
        # Reverse to get chronological order for form string
        form_parts = []
        for m in reversed(club_matches):
            if m.home_club_id == club_id:
                if m.home_score > m.away_score:
                    form_parts.append("W")
                elif m.home_score == m.away_score:
                    form_parts.append("D")
                else:
                    form_parts.append("L")
            else:
                if m.away_score > m.home_score:
                    form_parts.append("W")
                elif m.away_score == m.home_score:
                    form_parts.append("D")
                else:
                    form_parts.append("L")
        form = "".join(form_parts)

        standings_data.append(
            {
                "club_id": club_id,
                "played": played,
                "won": won,
                "drawn": drawn,
                "lost": lost,
                "goals_for": goals_for,
                "goals_against": goals_against,
                "goal_difference": goal_difference,
                "points": points,
                "form": form,
            }
        )

    # Sort: points desc, then goal_difference desc, then goals_for desc
    standings_data.sort(
        key=lambda x: (-x["points"], -x["goal_difference"], -x["goals_for"])
    )

    # Assign positions and upsert Standing records
    updated_standings = []
    for idx, entry in enumerate(standings_data, start=1):
        standing, created = Standing.objects.update_or_create(
            competition=competition,
            club_id=entry["club_id"],
            defaults={
                "position": idx,
                "played": entry["played"],
                "won": entry["won"],
                "drawn": entry["drawn"],
                "lost": entry["lost"],
                "goals_for": entry["goals_for"],
                "goals_against": entry["goals_against"],
                "goal_difference": entry["goal_difference"],
                "points": entry["points"],
                "form": entry["form"],
            },
        )
        updated_standings.append(standing)

    return updated_standings
