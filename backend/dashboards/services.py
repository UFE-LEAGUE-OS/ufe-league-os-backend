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

    # Optimization: If the Competition model had a M2M to Club, we would use that.
    # For now, we fetch all unique club IDs that appear in any match (not just completed)
    # to ensure teams with 0 games played are eventually supported.
    all_match_clubs = Match.objects.filter(competition=competition).values_list(
        "home_club_id", "away_club_id"
    )
    club_ids = set()
    for h_id, a_id in all_match_clubs:
        club_ids.add(h_id)
        club_ids.add(a_id)

    standings_data = []
    for club_id in club_ids:
        # Calculate stats from pre-fetched matches to avoid N+1 query patterns
        c_home = [m for m in matches if m.home_club_id == club_id]
        c_away = [m for m in matches if m.away_club_id == club_id]

        played_home = len(c_home)
        played_away = len(c_away)
        played = played_home + played_away

        won = sum(1 for m in c_home if m.home_score > m.away_score) + sum(
            1 for m in c_away if m.away_score > m.home_score
        )

        drawn = sum(1 for m in c_home if m.home_score == m.away_score) + sum(
            1 for m in c_away if m.away_score == m.home_score
        )

        lost = played - won - drawn
        goals_for = sum(m.home_score for m in c_home) + sum(
            m.away_score for m in c_away
        )
        goals_against = sum(m.away_score for m in c_home) + sum(
            m.home_score for m in c_away
        )

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
