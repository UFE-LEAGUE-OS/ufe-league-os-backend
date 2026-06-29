from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import User
from dashboards.models import Match

from .models import (
    FantasyCompetition,
    FantasyGameweek,
    FantasyLeague,
    FantasyLeagueMembership,
    FantasyLineup,
    FantasyLineupPlayer,
    FantasyPlayer,
    FantasyPlayerGameweekScore,
    FantasySquadPlayer,
    FantasyTeam,
    FantasyTeamGameweekScore,
)

FANTASY_ADMIN_ROLES = {
    User.Role.LEAGUE_ADMIN,
    User.Role.UNION_ADMIN,
    User.Role.SUPER_ADMIN,
    User.Role.REFEREE,
}


def user_can_manage_fantasy(user):
    """
    Fantasy admin permissions.

    League Admin / Union Admin / Super Admin can manage full fantasy setup.
    Referee/Match Official can help with score entry.
    """
    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or user.role in FANTASY_ADMIN_ROLES)
    )


def user_can_approve_fantasy_scores(user):
    """
    Score approval is stricter than score entry.

    Match officials can submit draft scores, but League/Union/Super Admin
    should approve them.
    """
    approval_roles = {
        User.Role.LEAGUE_ADMIN,
        User.Role.UNION_ADMIN,
        User.Role.SUPER_ADMIN,
    }
    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or user.role in approval_roles)
    )


def require_fantasy_manager(user):
    if not user_can_manage_fantasy(user):
        raise PermissionDenied("You do not have permission to manage fantasy.")


def require_fantasy_score_approver(user):
    if not user_can_approve_fantasy_scores(user):
        raise PermissionDenied("You do not have permission to approve fantasy scores.")


def calculate_suggested_player_price(
    competition,
    previous_stats=None,
):
    """
    Calculate a suggested player price from previous stats.

    This is deliberately simple for the MVP.

    Expected previous_stats keys:
    - appearances
    - tries
    - try_assists
    - tackles
    - metres_carried
    - clean_breaks
    - player_of_match
    """

    previous_stats = previous_stats or {}

    appearances = Decimal(str(previous_stats.get("appearances", 0)))
    tries = Decimal(str(previous_stats.get("tries", 0)))
    try_assists = Decimal(str(previous_stats.get("try_assists", 0)))
    tackles = Decimal(str(previous_stats.get("tackles", 0)))
    metres_carried = Decimal(str(previous_stats.get("metres_carried", 0)))
    clean_breaks = Decimal(str(previous_stats.get("clean_breaks", 0)))
    player_of_match = Decimal(str(previous_stats.get("player_of_match", 0)))

    performance_score = (
        appearances * Decimal("0.4")
        + tries * Decimal("2.0")
        + try_assists * Decimal("1.5")
        + tackles / Decimal("20")
        + metres_carried / Decimal("100")
        + clean_breaks * Decimal("0.8")
        + player_of_match * Decimal("2.5")
    )

    price = competition.default_player_price + performance_score * Decimal("0.15")

    price = max(price, competition.min_player_price)
    price = min(price, competition.max_player_price)

    price = (price * 2).quantize(Decimal("1")) / 2
    return price.quantize(Decimal("0.01"))


def create_fantasy_team(owner, fantasy_competition, name):
    """
    Create one fantasy team for a fan in a fantasy competition.
    """

    if not fantasy_competition.is_open_for_team_creation:
        raise ValidationError(
            {"fantasy_competition": "This fantasy competition is not open."}
        )

    team, created = FantasyTeam.objects.get_or_create(
        owner=owner,
        fantasy_competition=fantasy_competition,
        defaults={"name": name},
    )

    if not created:
        raise ValidationError(
            {"fantasy_competition": "You already have a team for this competition."}
        )

    return team


def validate_squad_player_selection(fantasy_team, players):
    """
    Validate a full squad selection.

    Checks:
    - exact squad size
    - all players belong to the same fantasy competition
    - no duplicates
    - all players are active and available
    - budget is not exceeded
    - max players per club rule is respected
    """

    competition = fantasy_team.fantasy_competition
    player_ids = [player.id for player in players]

    if len(player_ids) != len(set(player_ids)):
        raise ValidationError({"player_ids": "A player cannot be selected twice."})

    if len(players) != competition.squad_size:
        raise ValidationError(
            {
                "player_ids": (
                    f"Squad must contain exactly {competition.squad_size} players."
                )
            }
        )

    invalid_competition_players = [
        player.display_name
        for player in players
        if player.fantasy_competition_id != competition.id
    ]
    if invalid_competition_players:
        raise ValidationError(
            {
                "player_ids": (
                    "All selected players must belong to the same fantasy competition."
                )
            }
        )

    unavailable_players = [
        player.display_name
        for player in players
        if not player.is_active or not player.is_available
    ]
    if unavailable_players:
        raise ValidationError(
            {
                "player_ids": (
                    "Some selected players are unavailable: "
                    + ", ".join(unavailable_players)
                )
            }
        )

    budget_used = sum(
        (player.final_price for player in players),
        Decimal("0.00"),
    )
    if budget_used > competition.budget:
        raise ValidationError(
            {
                "budget": (
                    f"Budget exceeded. Used {budget_used}, "
                    f"available {competition.budget}."
                )
            }
        )

    club_counts = {}
    for player in players:
        club_counts[player.club_id] = club_counts.get(player.club_id, 0) + 1

    over_limit_clubs = [
        club_id
        for club_id, count in club_counts.items()
        if count > competition.max_players_per_club
    ]
    if over_limit_clubs:
        raise ValidationError(
            {
                "club_limit": (
                    f"Cannot select more than {competition.max_players_per_club} "
                    "players from the same club."
                )
            }
        )


def replace_fantasy_squad(fantasy_team, player_ids):
    """
    Replace a team's active squad with a confirmed selection.
    """

    players = list(
        FantasyPlayer.objects.select_related("club", "fantasy_competition").filter(
            id__in=player_ids
        )
    )

    if len(players) != len(set(player_ids)):
        raise ValidationError(
            {"player_ids": "One or more selected players do not exist."}
        )

    validate_squad_player_selection(fantasy_team, players)

    with transaction.atomic():
        fantasy_team.squad_players.filter(is_active=True).update(
            is_active=False,
            removed_at=timezone.now(),
        )

        squad_rows = []
        for player in players:
            squad_rows.append(
                FantasySquadPlayer(
                    fantasy_team=fantasy_team,
                    fantasy_player=player,
                    price_at_selection=player.final_price,
                    is_active=True,
                )
            )

        FantasySquadPlayer.objects.bulk_create(squad_rows)

    return fantasy_team


def submit_lineup(
    fantasy_team,
    gameweek,
    player_ids,
    captain_id,
    vice_captain_id=None,
):
    """
    Submit or update a gameweek lineup.

    Lineups can only be changed before gameweek lock time.
    """

    competition = fantasy_team.fantasy_competition

    if gameweek.fantasy_competition_id != competition.id:
        raise ValidationError({"gameweek": "Gameweek belongs to another competition."})

    if not gameweek.can_submit_lineup:
        raise ValidationError({"gameweek": "This gameweek is locked."})

    if len(player_ids) != len(set(player_ids)):
        raise ValidationError(
            {"player_ids": "A player cannot appear twice in a lineup."}
        )

    if len(player_ids) != competition.lineup_size:
        raise ValidationError(
            {
                "player_ids": (
                    f"Lineup must contain exactly {competition.lineup_size} players."
                )
            }
        )

    active_squad_ids = set(
        fantasy_team.squad_players.filter(is_active=True).values_list(
            "fantasy_player_id",
            flat=True,
        )
    )

    if not set(player_ids).issubset(active_squad_ids):
        raise ValidationError(
            {"player_ids": "Lineup players must be selected from your active squad."}
        )

    if captain_id not in player_ids:
        raise ValidationError({"captain_id": "Captain must be in the selected lineup."})

    if vice_captain_id and vice_captain_id not in player_ids:
        raise ValidationError(
            {"vice_captain_id": "Vice captain must be in the selected lineup."}
        )

    if vice_captain_id and vice_captain_id == captain_id:
        raise ValidationError(
            {"vice_captain_id": "Vice captain cannot be the same as captain."}
        )

    captain = FantasyPlayer.objects.get(id=captain_id)
    vice_captain = None
    if vice_captain_id:
        vice_captain = FantasyPlayer.objects.get(id=vice_captain_id)

    with transaction.atomic():
        lineup, _created = FantasyLineup.objects.update_or_create(
            fantasy_team=fantasy_team,
            gameweek=gameweek,
            defaults={
                "captain": captain,
                "vice_captain": vice_captain,
            },
        )

        lineup.players.all().delete()

        lineup_rows = []
        for index, player_id in enumerate(player_ids):
            lineup_rows.append(
                FantasyLineupPlayer(
                    lineup=lineup,
                    fantasy_player_id=player_id,
                    is_starter=True,
                    sort_order=index + 1,
                )
            )

        FantasyLineupPlayer.objects.bulk_create(lineup_rows)

    return lineup


def create_fantasy_league(created_by, fantasy_competition, name, league_type):
    if fantasy_competition.status == FantasyCompetition.Status.CANCELLED:
        raise ValidationError({"fantasy_competition": "Competition is cancelled."})

    return FantasyLeague.objects.create(
        fantasy_competition=fantasy_competition,
        name=name,
        league_type=league_type,
        created_by=created_by,
    )


def join_private_fantasy_league(fantasy_team, join_code):
    league = FantasyLeague.objects.filter(
        join_code=str(join_code).strip().upper(),
        league_type=FantasyLeague.LeagueType.PRIVATE,
        is_active=True,
    ).first()

    if league is None:
        raise ValidationError({"join_code": "Fantasy league was not found."})

    if league.fantasy_competition_id != fantasy_team.fantasy_competition_id:
        raise ValidationError(
            {"fantasy_team": "Team belongs to a different fantasy competition."}
        )

    membership, _created = FantasyLeagueMembership.objects.get_or_create(
        fantasy_league=league,
        fantasy_team=fantasy_team,
    )
    return membership


def create_or_update_player_score(
    gameweek,
    fantasy_player,
    points,
    breakdown,
    entered_by,
    status,
    match_id=None,
):
    """
    Create or update a player gameweek score.

    Match officials/scoring officers can submit scores.
    League/Union/Super Admin can approve them later.
    """

    if fantasy_player.fantasy_competition_id != gameweek.fantasy_competition_id:
        raise ValidationError(
            {"fantasy_player": "Player belongs to a different fantasy competition."}
        )

    match = None
    if match_id:
        match = Match.objects.filter(id=match_id).first()
        if match is None:
            raise ValidationError({"match_id": "Match was not found."})

    score, _created = FantasyPlayerGameweekScore.objects.update_or_create(
        fantasy_player=fantasy_player,
        gameweek=gameweek,
        defaults={
            "match": match,
            "points": points,
            "breakdown": breakdown or {},
            "status": status,
            "entered_by": entered_by,
        },
    )

    return score


def approve_player_score(score, approved_by):
    require_fantasy_score_approver(approved_by)

    score.status = FantasyPlayerGameweekScore.Status.APPROVED
    score.approved_by = approved_by
    score.approved_at = timezone.now()
    score.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return score


def calculate_gameweek_scores(gameweek):
    """
    Calculate fantasy team scores for a gameweek.

    Only APPROVED player scores count.
    Captain gets the competition captain multiplier.
    """

    competition = gameweek.fantasy_competition

    approved_scores = {
        score.fantasy_player_id: score
        for score in gameweek.player_scores.filter(
            status=FantasyPlayerGameweekScore.Status.APPROVED
        )
    }

    lineups = (
        gameweek.lineups.select_related(
            "fantasy_team",
            "captain",
            "vice_captain",
        )
        .prefetch_related("players")
        .all()
    )

    team_scores = []

    with transaction.atomic():
        for lineup in lineups:
            total_points = Decimal("0.00")
            player_breakdown = []

            for lineup_player in lineup.players.all():
                score = approved_scores.get(lineup_player.fantasy_player_id)
                points = score.points if score else Decimal("0.00")

                is_captain = lineup_player.fantasy_player_id == lineup.captain_id
                multiplier = Decimal("1.00")

                if is_captain:
                    multiplier = competition.captain_multiplier

                final_points = (points * multiplier).quantize(Decimal("0.01"))
                total_points += final_points

                player_breakdown.append(
                    {
                        "fantasy_player_id": lineup_player.fantasy_player_id,
                        "player": lineup_player.fantasy_player.display_name,
                        "base_points": str(points),
                        "multiplier": str(multiplier),
                        "points": str(final_points),
                        "is_captain": is_captain,
                    }
                )

            team_score, _created = FantasyTeamGameweekScore.objects.update_or_create(
                fantasy_team=lineup.fantasy_team,
                gameweek=gameweek,
                defaults={
                    "points": total_points,
                    "breakdown": {"players": player_breakdown},
                },
            )
            team_scores.append(team_score)

        ranked_scores = list(
            FantasyTeamGameweekScore.objects.filter(gameweek=gameweek).order_by(
                "-points",
                "fantasy_team__name",
            )
        )

        for index, score in enumerate(ranked_scores, start=1):
            score.rank = index
            score.save(update_fields=["rank", "calculated_at"])

        teams = FantasyTeam.objects.filter(fantasy_competition=competition)
        for team in teams:
            total = team.gameweek_scores.aggregate(total=Sum("points"))[
                "total"
            ] or Decimal("0.00")
            team.total_points = total
            team.save(update_fields=["total_points", "updated_at"])

        ranked_teams = list(
            FantasyTeam.objects.filter(fantasy_competition=competition).order_by(
                "-total_points",
                "name",
            )
        )
        for index, team in enumerate(ranked_teams, start=1):
            team.current_rank = index
            team.save(update_fields=["current_rank", "updated_at"])

    return FantasyTeamGameweekScore.objects.filter(gameweek=gameweek).order_by("rank")


def close_gameweek(gameweek):
    scores = calculate_gameweek_scores(gameweek)
    gameweek.status = FantasyGameweek.Status.COMPLETED
    gameweek.save(update_fields=["status", "updated_at"])
    return scores


def get_fantasy_admin_dashboard_summary(fantasy_competition_id=None):
    """
    Build a summary for the Fantasy Admin Dashboard.

    This avoids making the frontend call many separate endpoints just to load
    the admin dashboard cards.
    """

    competitions = FantasyCompetition.objects.all()
    gameweeks = FantasyGameweek.objects.all()
    players = FantasyPlayer.objects.all()
    teams = FantasyTeam.objects.all()
    leagues = FantasyLeague.objects.all()
    player_scores = FantasyPlayerGameweekScore.objects.all()

    if fantasy_competition_id:
        competitions = competitions.filter(id=fantasy_competition_id)
        gameweeks = gameweeks.filter(fantasy_competition_id=fantasy_competition_id)
        players = players.filter(fantasy_competition_id=fantasy_competition_id)
        teams = teams.filter(fantasy_competition_id=fantasy_competition_id)
        leagues = leagues.filter(fantasy_competition_id=fantasy_competition_id)
        player_scores = player_scores.filter(
            gameweek__fantasy_competition_id=fantasy_competition_id
        )

    return {
        "competitions_count": competitions.count(),
        "open_competitions_count": competitions.filter(
            status=FantasyCompetition.Status.OPEN
        ).count(),
        "gameweeks_count": gameweeks.count(),
        "open_gameweeks_count": gameweeks.filter(
            status=FantasyGameweek.Status.OPEN
        ).count(),
        "locked_gameweeks_count": gameweeks.filter(
            status=FantasyGameweek.Status.LOCKED
        ).count(),
        "completed_gameweeks_count": gameweeks.filter(
            status=FantasyGameweek.Status.COMPLETED
        ).count(),
        "players_count": players.count(),
        "available_players_count": players.filter(
            is_active=True,
            is_available=True,
        ).count(),
        "teams_count": teams.count(),
        "leagues_count": leagues.count(),
        "public_leagues_count": leagues.filter(
            league_type=FantasyLeague.LeagueType.PUBLIC
        ).count(),
        "private_leagues_count": leagues.filter(
            league_type=FantasyLeague.LeagueType.PRIVATE
        ).count(),
        "draft_scores_count": player_scores.filter(
            status=FantasyPlayerGameweekScore.Status.DRAFT
        ).count(),
        "submitted_scores_count": player_scores.filter(
            status=FantasyPlayerGameweekScore.Status.SUBMITTED
        ).count(),
        "approved_scores_count": player_scores.filter(
            status=FantasyPlayerGameweekScore.Status.APPROVED
        ).count(),
        "rejected_scores_count": player_scores.filter(
            status=FantasyPlayerGameweekScore.Status.REJECTED
        ).count(),
    }


def update_fantasy_competition_settings(competition, data, updated_by):
    """
    Update fantasy competition settings.

    This is admin-only business logic.
    """
    require_fantasy_manager(updated_by)

    editable_fields = [
        "name",
        "season",
        "status",
        "budget",
        "squad_size",
        "lineup_size",
        "max_players_per_club",
        "captain_multiplier",
        "min_player_price",
        "max_player_price",
        "default_player_price",
        "rules_summary",
    ]

    for field in editable_fields:
        if field in data:
            setattr(competition, field, data[field])

    competition.save()
    return competition


def update_fantasy_gameweek_settings(gameweek, data, updated_by):
    """
    Update fantasy gameweek setup.

    This handles normal fields plus the many-to-many match selection.
    """
    require_fantasy_manager(updated_by)

    matches = data.pop("matches", None)

    editable_fields = [
        "name",
        "number",
        "start_at",
        "lock_at",
        "end_at",
        "status",
    ]

    for field in editable_fields:
        if field in data:
            setattr(gameweek, field, data[field])

    gameweek.save()

    if matches is not None:
        gameweek.matches.set(matches)

    return gameweek


def update_fantasy_player_admin(player, data, updated_by):
    """
    Update fantasy player details, availability, stats, and price.

    Pricing rules:
    - If recalculate_price=true, the system recalculates from previous_stats.
    - If final_price is supplied directly, it becomes a manual override.
    """
    require_fantasy_manager(updated_by)

    recalculate_price = data.pop("recalculate_price", False)

    club_id = data.pop("club", None)
    if club_id:
        from accounts.models import Club

        club = Club.objects.filter(id=club_id).first()
        if club is None:
            raise ValidationError({"club": "Club was not found."})
        player.club = club

    editable_fields = [
        "display_name",
        "position",
        "previous_stats",
        "current_form",
        "is_active",
        "is_available",
        "availability_note",
    ]

    for field in editable_fields:
        if field in data:
            setattr(player, field, data[field])

    if recalculate_price:
        calculated_price = calculate_suggested_player_price(
            player.fantasy_competition,
            previous_stats=player.previous_stats,
        )
        player.calculated_price = calculated_price
        player.final_price = calculated_price
        player.price_source = FantasyPlayer.PriceSource.AUTO
        player.price_override_reason = ""
        player.price_locked_at = None

    if "final_price" in data:
        player.final_price = data["final_price"]
        player.price_source = FantasyPlayer.PriceSource.MANUAL
        player.price_override_reason = data.get("price_override_reason", "")
        player.price_locked_at = timezone.now()

    player.save()
    return player


def update_fantasy_player_score_admin(score, data, updated_by):
    """
    Update a fantasy player score.

    Score status rules:
    - DRAFT/SUBMITTED can be set by fantasy managers.
    - APPROVED/REJECTED requires League/Union/Super Admin approval permissions.
    """
    require_fantasy_manager(updated_by)

    if "match_id" in data:
        match_id = data["match_id"]
        if match_id is None:
            score.match = None
        else:
            match = Match.objects.filter(id=match_id).first()
            if match is None:
                raise ValidationError({"match_id": "Match was not found."})
            score.match = match

    if "points" in data:
        score.points = data["points"]

    if "breakdown" in data:
        score.breakdown = data["breakdown"]

    if "status" in data:
        new_status = data["status"]

        if new_status in [
            FantasyPlayerGameweekScore.Status.APPROVED,
            FantasyPlayerGameweekScore.Status.REJECTED,
        ]:
            require_fantasy_score_approver(updated_by)
            score.approved_by = updated_by
            score.approved_at = timezone.now()

        score.status = new_status

    score.save()
    return score


def reject_player_score(score, rejected_by):
    """
    Reject a submitted player score.

    Rejection is treated like an approval decision, so only approval roles can do it.
    """
    require_fantasy_score_approver(rejected_by)

    score.status = FantasyPlayerGameweekScore.Status.REJECTED
    score.approved_by = rejected_by
    score.approved_at = timezone.now()
    score.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return score
