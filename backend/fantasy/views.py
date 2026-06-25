from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import (
    FantasyCompetition,
    FantasyGameweek,
    FantasyLeague,
    FantasyLeagueMembership,
    FantasyLineup,
    FantasyPlayer,
    FantasyPlayerGameweekScore,
    FantasyTeam,
    FantasyTeamGameweekScore,
)
from .serializers import (
    FantasyCompetitionSerializer,
    FantasyGameweekSerializer,
    FantasyLeagueCreateSerializer,
    FantasyLeagueJoinSerializer,
    FantasyLeagueMembershipSerializer,
    FantasyLeagueSerializer,
    FantasyLineupSerializer,
    FantasyLineupSubmitSerializer,
    FantasyPlayerGameweekScoreSerializer,
    FantasyPlayerPriceUpdateSerializer,
    FantasyPlayerScoreSubmitSerializer,
    FantasyPlayerSerializer,
    FantasySquadUpdateSerializer,
    FantasyTeamCreateSerializer,
    FantasyTeamGameweekScoreSerializer,
    FantasyTeamSerializer,
)
from .services import (
    approve_player_score,
    calculate_gameweek_scores,
    close_gameweek,
    create_fantasy_league,
    create_fantasy_team,
    create_or_update_player_score,
    calculate_suggested_player_price,
    join_private_fantasy_league,
    replace_fantasy_squad,
    require_fantasy_manager,
    submit_lineup,
)


def _get_positive_int(value, default, maximum=None):
    """
    Convert query parameter values into safe positive integers.

    This protects the API from bad query params like:
    ?limit=abc
    ?limit=-50
    ?limit=1000000
    """
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default

    if number < 0:
        number = default

    if maximum is not None:
        number = min(number, maximum)

    return number


def _paginated_response(queryset, serializer_class, request):
    """
    Simple offset pagination helper.

    The frontend can call:
    ?limit=20&offset=0
    ?limit=20&offset=20
    """
    limit = _get_positive_int(
        request.query_params.get("limit"), default=50, maximum=100
    )
    offset = _get_positive_int(request.query_params.get("offset"), default=0)

    total = queryset.count()
    page = queryset[offset : offset + limit]

    serializer = serializer_class(page, many=True)
    return Response(
        {
            "count": total,
            "limit": limit,
            "offset": offset,
            "results": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


def _user_can_view_fantasy_league(user, league):
    """
    Public leagues can be viewed by anyone.

    Private leagues can only be viewed by:
    - the creator
    - a user who has joined with one of their fantasy teams
    """
    if league.league_type == FantasyLeague.LeagueType.PUBLIC:
        return True

    if not user or not user.is_authenticated:
        return False

    if league.created_by_id == user.id:
        return True

    return FantasyLeagueMembership.objects.filter(
        fantasy_league=league,
        fantasy_team__owner=user,
    ).exists()


@extend_schema(tags=["Fantasy"])
@api_view(["GET"])
@permission_classes([AllowAny])
def fantasy_competition_list_view(request):
    queryset = FantasyCompetition.objects.select_related("linked_competition").all()

    sport = request.query_params.get("sport")
    status_filter = request.query_params.get("status")

    if sport:
        queryset = queryset.filter(sport=str(sport).upper())

    if status_filter:
        queryset = queryset.filter(status=str(status_filter).upper())

    serializer = FantasyCompetitionSerializer(queryset, many=True)
    return Response(
        {"count": queryset.count(), "results": serializer.data},
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy"])
@api_view(["GET"])
@permission_classes([AllowAny])
def fantasy_competition_detail_view(request, competition_id):
    competition = (
        FantasyCompetition.objects.select_related("linked_competition")
        .filter(id=competition_id)
        .first()
    )

    if competition is None:
        return Response(
            {"detail": "Fantasy competition not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    gameweeks = competition.gameweeks.all()
    leagues = competition.fantasy_leagues.filter(is_active=True)

    return Response(
        {
            "competition": FantasyCompetitionSerializer(competition).data,
            "gameweeks": FantasyGameweekSerializer(gameweeks, many=True).data,
            "leagues": FantasyLeagueSerializer(leagues, many=True).data,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy"])
@api_view(["GET"])
@permission_classes([AllowAny])
def fantasy_competition_gameweeks_view(request, competition_id):
    """
    List gameweeks for one fantasy competition.

    Frontend screen use:
    - Fantasy Competition Detail
    - Gameweek Lineup Centre
    - Score & Gameweek Operations
    """
    queryset = FantasyGameweek.objects.filter(
        fantasy_competition_id=competition_id
    ).order_by("number")

    status_filter = request.query_params.get("status")
    if status_filter:
        queryset = queryset.filter(status=str(status_filter).upper())

    return _paginated_response(queryset, FantasyGameweekSerializer, request)


@extend_schema(tags=["Fantasy"])
@api_view(["GET"])
@permission_classes([AllowAny])
def fantasy_player_market_view(request, competition_id):
    queryset = FantasyPlayer.objects.select_related(
        "fantasy_competition",
        "club",
    ).filter(fantasy_competition_id=competition_id)

    search = request.query_params.get("search")
    club_id = request.query_params.get("club")
    position = request.query_params.get("position")
    available = request.query_params.get("available")

    if search:
        queryset = queryset.filter(display_name__icontains=search)

    if club_id:
        queryset = queryset.filter(club_id=club_id)

    if position:
        queryset = queryset.filter(position=str(position).upper())

    if available == "true":
        queryset = queryset.filter(is_active=True, is_available=True)

    serializer = FantasyPlayerSerializer(queryset, many=True)
    return Response(
        {"count": queryset.count(), "results": serializer.data},
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def fantasy_team_create_view(request):
    serializer = FantasyTeamCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    team = create_fantasy_team(
        owner=request.user,
        fantasy_competition=serializer.validated_data["fantasy_competition"],
        name=serializer.validated_data["name"],
    )

    return Response(
        {
            "message": "Fantasy team created successfully.",
            "team": FantasyTeamSerializer(team).data,
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(tags=["Fantasy"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_fantasy_teams_view(request):
    queryset = (
        FantasyTeam.objects.filter(owner=request.user)
        .select_related("fantasy_competition")
        .prefetch_related("squad_players", "squad_players__fantasy_player")
    )

    serializer = FantasyTeamSerializer(queryset, many=True)
    return Response(
        {"count": queryset.count(), "results": serializer.data},
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fantasy_team_detail_view(request, team_id):
    """
    Get one authenticated user's fantasy team.

    Frontend screen use:
    - My Fantasy Team Dashboard
    - Review & Confirm Squad
    - Gameweek Lineup Centre
    """
    team = (
        FantasyTeam.objects.filter(id=team_id, owner=request.user)
        .select_related("fantasy_competition", "owner")
        .prefetch_related(
            "squad_players",
            "squad_players__fantasy_player",
            "squad_players__fantasy_player__club",
        )
        .first()
    )

    if team is None:
        return Response(
            {"detail": "Fantasy team not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        {"team": FantasyTeamSerializer(team).data},
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fantasy_team_history_view(request, team_id):
    """
    Get one authenticated user's fantasy team history.

    Frontend screen use:
    - Live Points / Gameweek Results / History
    - My Fantasy Team Dashboard
    """
    team = FantasyTeam.objects.filter(id=team_id, owner=request.user).first()

    if team is None:
        return Response(
            {"detail": "Fantasy team not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    scores = (
        FantasyTeamGameweekScore.objects.filter(fantasy_team=team)
        .select_related("fantasy_team", "fantasy_team__owner", "gameweek")
        .order_by("-gameweek__number")
    )

    lineups = (
        FantasyLineup.objects.filter(fantasy_team=team)
        .select_related("fantasy_team", "gameweek", "captain", "vice_captain")
        .prefetch_related("players", "players__fantasy_player")
        .order_by("-gameweek__number")
    )

    return Response(
        {
            "team": FantasyTeamSerializer(team).data,
            "scores": FantasyTeamGameweekScoreSerializer(scores, many=True).data,
            "lineups": FantasyLineupSerializer(lineups, many=True).data,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def fantasy_team_squad_update_view(request, team_id):
    team = FantasyTeam.objects.filter(id=team_id, owner=request.user).first()

    if team is None:
        return Response(
            {"detail": "Fantasy team not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = FantasySquadUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    team = replace_fantasy_squad(
        fantasy_team=team,
        player_ids=serializer.validated_data["player_ids"],
    )

    return Response(
        {
            "message": "Fantasy squad updated successfully.",
            "team": FantasyTeamSerializer(team).data,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def fantasy_team_lineup_submit_view(request, team_id):
    team = FantasyTeam.objects.filter(id=team_id, owner=request.user).first()

    if team is None:
        return Response(
            {"detail": "Fantasy team not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = FantasyLineupSubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    lineup = submit_lineup(
        fantasy_team=team,
        gameweek=serializer.validated_data["gameweek"],
        player_ids=serializer.validated_data["player_ids"],
        captain_id=serializer.validated_data["captain_id"],
        vice_captain_id=serializer.validated_data.get("vice_captain_id"),
    )

    return Response(
        {
            "message": "Fantasy lineup submitted successfully.",
            "lineup": FantasyLineupSerializer(lineup).data,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_lineups_view(request):
    queryset = (
        FantasyLineup.objects.filter(fantasy_team__owner=request.user)
        .select_related("fantasy_team", "gameweek", "captain", "vice_captain")
        .prefetch_related("players", "players__fantasy_player")
        .order_by("-submitted_at")
    )

    serializer = FantasyLineupSerializer(queryset, many=True)
    return Response(
        {"count": queryset.count(), "results": serializer.data},
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def fantasy_league_create_view(request):
    serializer = FantasyLeagueCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    league = create_fantasy_league(
        created_by=request.user,
        fantasy_competition=serializer.validated_data["fantasy_competition"],
        name=serializer.validated_data["name"],
        league_type=serializer.validated_data["league_type"],
    )

    return Response(
        {
            "message": "Fantasy league created successfully.",
            "league": FantasyLeagueSerializer(league).data,
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(tags=["Fantasy"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def fantasy_league_join_view(request):
    serializer = FantasyLeagueJoinSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    fantasy_team = serializer.validated_data["fantasy_team"]

    if fantasy_team.owner_id != request.user.id:
        return Response(
            {"detail": "You can only join a league using your own fantasy team."},
            status=status.HTTP_403_FORBIDDEN,
        )

    membership = join_private_fantasy_league(
        fantasy_team=fantasy_team,
        join_code=serializer.validated_data["join_code"],
    )

    return Response(
        {
            "message": "Fantasy league joined successfully.",
            "membership": FantasyLeagueMembershipSerializer(membership).data,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_fantasy_leagues_view(request):
    queryset = (
        FantasyLeagueMembership.objects.filter(fantasy_team__owner=request.user)
        .select_related("fantasy_league", "fantasy_team")
        .order_by("-joined_at")
    )

    serializer = FantasyLeagueMembershipSerializer(queryset, many=True)
    return Response(
        {"count": queryset.count(), "results": serializer.data},
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy"])
@api_view(["GET"])
@permission_classes([AllowAny])
def fantasy_league_available_view(request):
    """
    List available fantasy leagues.

    Default behaviour:
    - returns PUBLIC leagues only

    Private league behaviour:
    - private leagues are only returned to authenticated users
    - user must be the creator or must have joined using one of their teams

    Frontend screen use:
    - Fantasy Leagues & Leaderboards
    """
    queryset = (
        FantasyLeague.objects.filter(is_active=True)
        .select_related("fantasy_competition", "created_by")
        .order_by("fantasy_competition__name", "name")
    )

    competition_id = request.query_params.get("competition")
    if competition_id:
        queryset = queryset.filter(fantasy_competition_id=competition_id)

    league_type = request.query_params.get("league_type")

    if league_type:
        normalized_league_type = str(league_type).upper()

        if normalized_league_type == FantasyLeague.LeagueType.PRIVATE:
            if not request.user.is_authenticated:
                return Response(
                    {
                        "detail": (
                            "Authentication is required to view private fantasy leagues."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            queryset = queryset.filter(
                league_type=FantasyLeague.LeagueType.PRIVATE
            ).filter(
                Q(created_by=request.user)
                | Q(memberships__fantasy_team__owner=request.user)
            )
            queryset = queryset.distinct()

        elif normalized_league_type == FantasyLeague.LeagueType.PUBLIC:
            queryset = queryset.filter(league_type=FantasyLeague.LeagueType.PUBLIC)

        else:
            queryset = queryset.none()

    else:
        queryset = queryset.filter(league_type=FantasyLeague.LeagueType.PUBLIC)

    return _paginated_response(queryset, FantasyLeagueSerializer, request)


@extend_schema(tags=["Fantasy"])
@api_view(["GET"])
@permission_classes([AllowAny])
def fantasy_league_detail_view(request, league_id):
    """
    Get fantasy league detail.

    Public leagues can be viewed by anyone.
    Private leagues can only be viewed by the creator or joined members.
    """
    league = (
        FantasyLeague.objects.select_related("fantasy_competition", "created_by")
        .filter(id=league_id, is_active=True)
        .first()
    )

    if league is None:
        return Response(
            {"detail": "Fantasy league not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _user_can_view_fantasy_league(request.user, league):
        return Response(
            {"detail": "You do not have permission to view this fantasy league."},
            status=status.HTTP_403_FORBIDDEN,
        )

    memberships = (
        FantasyLeagueMembership.objects.filter(fantasy_league=league)
        .select_related("fantasy_team", "fantasy_team__owner")
        .order_by("fantasy_team__current_rank", "-fantasy_team__total_points")
    )

    return Response(
        {
            "league": FantasyLeagueSerializer(league).data,
            "members_count": memberships.count(),
            "members": FantasyLeagueMembershipSerializer(memberships, many=True).data,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy"])
@api_view(["GET"])
@permission_classes([AllowAny])
def fantasy_league_leaderboard_view(request, league_id):
    """
    Get overall or gameweek leaderboard for one fantasy league.

    Query params:
    - gameweek_id optional

    Without gameweek_id:
    returns overall team ranking.

    With gameweek_id:
    returns gameweek score ranking for teams in that league.
    """
    league = FantasyLeague.objects.filter(id=league_id, is_active=True).first()

    if league is None:
        return Response(
            {"detail": "Fantasy league not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _user_can_view_fantasy_league(request.user, league):
        return Response(
            {"detail": "You do not have permission to view this fantasy league."},
            status=status.HTTP_403_FORBIDDEN,
        )

    gameweek_id = request.query_params.get("gameweek_id")

    if gameweek_id:
        queryset = (
            FantasyTeamGameweekScore.objects.filter(
                gameweek_id=gameweek_id,
                fantasy_team__league_memberships__fantasy_league=league,
            )
            .select_related("fantasy_team", "fantasy_team__owner", "gameweek")
            .distinct()
            .order_by("rank", "-points")
        )

        return _paginated_response(
            queryset,
            FantasyTeamGameweekScoreSerializer,
            request,
        )

    queryset = (
        FantasyTeam.objects.filter(league_memberships__fantasy_league=league)
        .select_related("owner", "fantasy_competition")
        .prefetch_related("squad_players", "squad_players__fantasy_player")
        .distinct()
        .order_by("current_rank", "-total_points", "name")
    )

    return _paginated_response(queryset, FantasyTeamSerializer, request)


@extend_schema(tags=["Fantasy"])
@api_view(["GET"])
@permission_classes([AllowAny])
def fantasy_gameweek_leaderboard_view(request, gameweek_id):
    queryset = (
        FantasyTeamGameweekScore.objects.filter(gameweek_id=gameweek_id)
        .select_related("fantasy_team", "fantasy_team__owner", "gameweek")
        .order_by("rank", "-points")
    )

    serializer = FantasyTeamGameweekScoreSerializer(queryset, many=True)
    return Response(
        {"count": queryset.count(), "results": serializer.data},
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy Admin"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_fantasy_competition_create_view(request):
    require_fantasy_manager(request.user)

    serializer = FantasyCompetitionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    competition = serializer.save(created_by=request.user)

    return Response(
        {
            "message": "Fantasy competition created successfully.",
            "competition": FantasyCompetitionSerializer(competition).data,
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(tags=["Fantasy Admin"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_fantasy_gameweek_create_view(request):
    require_fantasy_manager(request.user)

    serializer = FantasyGameweekSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    gameweek = serializer.save()

    return Response(
        {
            "message": "Fantasy gameweek created successfully.",
            "gameweek": FantasyGameweekSerializer(gameweek).data,
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(tags=["Fantasy Admin"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_fantasy_player_create_view(request):
    require_fantasy_manager(request.user)

    serializer = FantasyPlayerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    competition = serializer.validated_data["fantasy_competition"]
    previous_stats = serializer.validated_data.get("previous_stats") or {}
    calculated_price = calculate_suggested_player_price(
        competition,
        previous_stats=previous_stats,
    )

    player = serializer.save(
        calculated_price=calculated_price,
        final_price=calculated_price,
        price_source=FantasyPlayer.PriceSource.AUTO,
    )

    return Response(
        {
            "message": "Fantasy player created successfully.",
            "player": FantasyPlayerSerializer(player).data,
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(tags=["Fantasy Admin"])
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def admin_fantasy_player_price_update_view(request, player_id):
    require_fantasy_manager(request.user)

    player = FantasyPlayer.objects.filter(id=player_id).first()
    if player is None:
        return Response(
            {"detail": "Fantasy player not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = FantasyPlayerPriceUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    player.final_price = serializer.validated_data["final_price"]
    player.price_override_reason = serializer.validated_data.get(
        "price_override_reason",
        "",
    )
    player.price_source = FantasyPlayer.PriceSource.MANUAL
    player.price_locked_at = None
    player.save(
        update_fields=[
            "final_price",
            "price_override_reason",
            "price_source",
            "price_locked_at",
            "updated_at",
        ]
    )

    return Response(
        {
            "message": "Fantasy player price updated successfully.",
            "player": FantasyPlayerSerializer(player).data,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy Admin"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_gameweek_player_score_view(request, gameweek_id):
    require_fantasy_manager(request.user)

    gameweek = FantasyGameweek.objects.filter(id=gameweek_id).first()
    if gameweek is None:
        return Response(
            {"detail": "Fantasy gameweek not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = FantasyPlayerScoreSubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    score = create_or_update_player_score(
        gameweek=gameweek,
        fantasy_player=serializer.validated_data["fantasy_player"],
        points=serializer.validated_data["points"],
        breakdown=serializer.validated_data.get("breakdown", {}),
        entered_by=request.user,
        status=serializer.validated_data["status"],
        match_id=serializer.validated_data.get("match_id"),
    )

    return Response(
        {
            "message": "Fantasy player score saved successfully.",
            "score": FantasyPlayerGameweekScoreSerializer(score).data,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy Admin"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_player_score_approve_view(request, score_id):
    score = FantasyPlayerGameweekScore.objects.filter(id=score_id).first()

    if score is None:
        return Response(
            {"detail": "Fantasy player score not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    score = approve_player_score(score, approved_by=request.user)

    return Response(
        {
            "message": "Fantasy player score approved successfully.",
            "score": FantasyPlayerGameweekScoreSerializer(score).data,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy Admin"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_gameweek_calculate_view(request, gameweek_id):
    require_fantasy_manager(request.user)

    gameweek = FantasyGameweek.objects.filter(id=gameweek_id).first()
    if gameweek is None:
        return Response(
            {"detail": "Fantasy gameweek not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    scores = calculate_gameweek_scores(gameweek)

    return Response(
        {
            "message": "Fantasy gameweek scores calculated successfully.",
            "scores": FantasyTeamGameweekScoreSerializer(scores, many=True).data,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Fantasy Admin"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_gameweek_close_view(request, gameweek_id):
    require_fantasy_manager(request.user)

    gameweek = FantasyGameweek.objects.filter(id=gameweek_id).first()
    if gameweek is None:
        return Response(
            {"detail": "Fantasy gameweek not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    scores = close_gameweek(gameweek)

    return Response(
        {
            "message": "Fantasy gameweek closed successfully.",
            "gameweek": FantasyGameweekSerializer(gameweek).data,
            "scores": FantasyTeamGameweekScoreSerializer(scores, many=True).data,
        },
        status=status.HTTP_200_OK,
    )
