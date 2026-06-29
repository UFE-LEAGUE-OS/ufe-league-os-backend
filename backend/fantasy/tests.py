from io import StringIO
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Club, User
from dashboards.models import Competition, League, Match, Union

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
from .services import calculate_suggested_player_price


class FantasyTestMixin:
    def setUp(self):
        self.fan = User.objects.create_user(
            email="fantasy-fan@example.com",
            password="StrongPass123!",
            first_name="Fantasy",
            last_name="Fan",
            role=User.Role.FAN,
        )
        self.other_fan = User.objects.create_user(
            email="other-fantasy-fan@example.com",
            password="StrongPass123!",
            first_name="Other",
            last_name="Fan",
            role=User.Role.FAN,
        )
        self.league_admin = User.objects.create_user(
            email="fantasy-league-admin@example.com",
            password="StrongPass123!",
            first_name="League",
            last_name="Admin",
            role=User.Role.LEAGUE_ADMIN,
        )
        self.referee = User.objects.create_user(
            email="fantasy-referee@example.com",
            password="StrongPass123!",
            first_name="Match",
            last_name="Official",
            role=User.Role.REFEREE,
        )

        self.union = Union.objects.create(
            name="Uganda Rugby Union Fantasy Test",
            slug="uganda-rugby-union-fantasy-test",
            country="Uganda",
        )
        self.league = League.objects.create(
            union=self.union,
            name="Nile Special Rugby League Fantasy Test",
            slug="nile-special-rugby-league-fantasy-test",
        )
        self.real_competition = Competition.objects.create(
            league=self.league,
            name="Nile Special Rugby Premiership Fantasy Test",
            slug="nile-special-rugby-premiership-fantasy-test",
            season="2026",
        )

        self.kobs = Club.objects.create(
            name="KCB Kobs Fantasy Test",
            slug="kcb-kobs-fantasy-test",
        )
        self.heathens = Club.objects.create(
            name="Heathens Fantasy Test",
            slug="heathens-fantasy-test",
        )
        self.pirates = Club.objects.create(
            name="Pirates Fantasy Test",
            slug="pirates-fantasy-test",
        )

        self.match = Match.objects.create(
            competition=self.real_competition,
            home_club=self.kobs,
            away_club=self.heathens,
            match_date=timezone.now() + timedelta(days=7),
            venue="Legends Rugby Grounds",
            status=Match.Status.SCHEDULED,
        )

        self.fantasy_competition = FantasyCompetition.objects.create(
            name="Nile Special Rugby Fantasy 2026",
            slug="nile-special-rugby-fantasy-2026",
            linked_competition=self.real_competition,
            sport=FantasyCompetition.Sport.RUGBY,
            season="2026",
            status=FantasyCompetition.Status.OPEN,
            budget=Decimal("100.00"),
            squad_size=3,
            lineup_size=3,
            max_players_per_club=2,
            captain_multiplier=Decimal("2.00"),
            created_by=self.league_admin,
        )

        now = timezone.now()
        self.gameweek = FantasyGameweek.objects.create(
            fantasy_competition=self.fantasy_competition,
            name="Gameweek 1",
            number=1,
            start_at=now,
            lock_at=now + timedelta(days=2),
            end_at=now + timedelta(days=4),
            status=FantasyGameweek.Status.OPEN,
        )
        self.gameweek.matches.add(self.match)

        self.player_1 = FantasyPlayer.objects.create(
            fantasy_competition=self.fantasy_competition,
            club=self.kobs,
            display_name="Ian Munyani",
            position=FantasyPlayer.Position.CENTRE,
            calculated_price=Decimal("9.50"),
            final_price=Decimal("9.50"),
            previous_stats={
                "appearances": 12,
                "tries": 4,
                "try_assists": 3,
                "tackles": 68,
                "metres_carried": 412,
                "clean_breaks": 9,
                "player_of_match": 2,
            },
        )
        self.player_2 = FantasyPlayer.objects.create(
            fantasy_competition=self.fantasy_competition,
            club=self.kobs,
            display_name="Pius Ogena",
            position=FantasyPlayer.Position.BACK_ROW,
            calculated_price=Decimal("8.00"),
            final_price=Decimal("8.00"),
        )
        self.player_3 = FantasyPlayer.objects.create(
            fantasy_competition=self.fantasy_competition,
            club=self.heathens,
            display_name="Philip Wokorach",
            position=FantasyPlayer.Position.FULLBACK,
            calculated_price=Decimal("10.00"),
            final_price=Decimal("10.00"),
        )
        self.player_4 = FantasyPlayer.objects.create(
            fantasy_competition=self.fantasy_competition,
            club=self.pirates,
            display_name="Pirates Utility Back",
            position=FantasyPlayer.Position.UTILITY,
            calculated_price=Decimal("5.00"),
            final_price=Decimal("5.00"),
        )

    @property
    def selected_player_ids(self):
        return [self.player_1.id, self.player_2.id, self.player_3.id]


class FantasyModelAndServiceTests(FantasyTestMixin, APITestCase):
    def test_gameweek_is_not_locked_before_lock_time(self):
        self.assertFalse(self.gameweek.is_locked)
        self.assertTrue(self.gameweek.can_submit_lineup)

    def test_calculate_suggested_player_price_from_previous_stats(self):
        price = calculate_suggested_player_price(
            self.fantasy_competition,
            previous_stats=self.player_1.previous_stats,
        )

        self.assertGreaterEqual(price, self.fantasy_competition.min_player_price)
        self.assertLessEqual(price, self.fantasy_competition.max_player_price)
        self.assertEqual(price % Decimal("0.50"), Decimal("0.00"))

    def test_private_fantasy_league_generates_join_code(self):
        league = FantasyLeague.objects.create(
            fantasy_competition=self.fantasy_competition,
            name="KOBS Fans Mini League",
            league_type=FantasyLeague.LeagueType.PRIVATE,
            created_by=self.fan,
        )

        self.assertTrue(league.join_code)
        self.assertEqual(len(league.join_code), 8)

    def test_public_fantasy_leagues_can_have_empty_join_code(self):
        first_league = FantasyLeague.objects.create(
            fantasy_competition=self.fantasy_competition,
            name="Public League One",
            league_type=FantasyLeague.LeagueType.PUBLIC,
            created_by=self.fan,
        )
        second_league = FantasyLeague.objects.create(
            fantasy_competition=self.fantasy_competition,
            name="Public League Two",
            league_type=FantasyLeague.LeagueType.PUBLIC,
            created_by=self.other_fan,
        )

        self.assertIsNone(first_league.join_code)
        self.assertIsNone(second_league.join_code)


class FantasyFanAPITests(FantasyTestMixin, APITestCase):
    def test_competition_discovery_endpoint_lists_open_competitions(self):
        response = self.client.get("/api/fantasy/competitions/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["name"], self.fantasy_competition.name
        )
        self.assertEqual(
            response.data["results"][0]["sport"], FantasyCompetition.Sport.RUGBY
        )

    def test_competition_detail_endpoint_returns_gameweeks_and_leagues(self):
        FantasyLeague.objects.create(
            fantasy_competition=self.fantasy_competition,
            name="Global Rugby Fantasy League",
            league_type=FantasyLeague.LeagueType.PUBLIC,
            created_by=self.league_admin,
        )

        response = self.client.get(
            f"/api/fantasy/competitions/{self.fantasy_competition.id}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["competition"]["name"],
            self.fantasy_competition.name,
        )
        self.assertEqual(len(response.data["gameweeks"]), 1)
        self.assertEqual(len(response.data["leagues"]), 1)

    def test_player_market_endpoint_lists_players(self):
        response = self.client.get(
            f"/api/fantasy/competitions/{self.fantasy_competition.id}/players/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 4)

        player_names = {player["display_name"] for player in response.data["results"]}
        self.assertIn("Ian Munyani", player_names)
        self.assertIn("Philip Wokorach", player_names)

    def test_player_market_filters_by_available_players(self):
        self.player_4.is_available = False
        self.player_4.save(update_fields=["is_available"])

        response = self.client.get(
            f"/api/fantasy/competitions/{self.fantasy_competition.id}/players/",
            {"available": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 3)

    def test_fan_can_create_fantasy_team(self):
        self.client.force_authenticate(user=self.fan)

        response = self.client.post(
            "/api/fantasy/teams/",
            {
                "fantasy_competition_id": self.fantasy_competition.id,
                "name": "Kobs Warriors Fantasy XV",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["team"]["name"], "Kobs Warriors Fantasy XV")
        self.assertEqual(
            FantasyTeam.objects.filter(
                owner=self.fan,
                fantasy_competition=self.fantasy_competition,
            ).count(),
            1,
        )

    def test_fan_cannot_create_two_teams_in_same_competition(self):
        FantasyTeam.objects.create(
            owner=self.fan,
            fantasy_competition=self.fantasy_competition,
            name="First Team",
        )
        self.client.force_authenticate(user=self.fan)

        response = self.client.post(
            "/api/fantasy/teams/",
            {
                "fantasy_competition_id": self.fantasy_competition.id,
                "name": "Second Team",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_fan_can_update_squad(self):
        team = FantasyTeam.objects.create(
            owner=self.fan,
            fantasy_competition=self.fantasy_competition,
            name="Kobs Warriors Fantasy XV",
        )
        self.client.force_authenticate(user=self.fan)

        response = self.client.post(
            f"/api/fantasy/teams/{team.id}/squad/",
            {"player_ids": self.selected_player_ids},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(team.squad_players.filter(is_active=True).count(), 3)

        team.refresh_from_db()
        self.assertEqual(team.active_squad_count, 3)
        self.assertEqual(team.budget_used, Decimal("27.50"))
        self.assertEqual(team.budget_remaining, Decimal("72.50"))

    def test_squad_builder_rejects_too_many_players_from_same_club(self):
        team = FantasyTeam.objects.create(
            owner=self.fan,
            fantasy_competition=self.fantasy_competition,
            name="Kobs Warriors Fantasy XV",
        )
        third_kobs_player = FantasyPlayer.objects.create(
            fantasy_competition=self.fantasy_competition,
            club=self.kobs,
            display_name="Third Kobs Player",
            position=FantasyPlayer.Position.WING,
            calculated_price=Decimal("5.00"),
            final_price=Decimal("5.00"),
        )
        self.client.force_authenticate(user=self.fan)

        response = self.client.post(
            f"/api/fantasy/teams/{team.id}/squad/",
            {
                "player_ids": [
                    self.player_1.id,
                    self.player_2.id,
                    third_kobs_player.id,
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("club_limit", response.data)

    def test_fan_can_submit_gameweek_lineup(self):
        team = FantasyTeam.objects.create(
            owner=self.fan,
            fantasy_competition=self.fantasy_competition,
            name="Kobs Warriors Fantasy XV",
        )
        self.client.force_authenticate(user=self.fan)

        self.client.post(
            f"/api/fantasy/teams/{team.id}/squad/",
            {"player_ids": self.selected_player_ids},
            format="json",
        )

        response = self.client.post(
            f"/api/fantasy/teams/{team.id}/lineups/",
            {
                "gameweek_id": self.gameweek.id,
                "player_ids": self.selected_player_ids,
                "captain_id": self.player_3.id,
                "vice_captain_id": self.player_1.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FantasyLineup.objects.filter(fantasy_team=team).count(), 1)
        self.assertEqual(FantasyLineupPlayer.objects.count(), 3)

    def test_lineup_submission_rejects_locked_gameweek(self):
        team = FantasyTeam.objects.create(
            owner=self.fan,
            fantasy_competition=self.fantasy_competition,
            name="Kobs Warriors Fantasy XV",
        )
        FantasySquadPlayer.objects.bulk_create(
            [
                FantasySquadPlayer(
                    fantasy_team=team,
                    fantasy_player=player,
                    price_at_selection=player.final_price,
                )
                for player in [self.player_1, self.player_2, self.player_3]
            ]
        )
        self.gameweek.lock_at = timezone.now() - timedelta(minutes=1)
        self.gameweek.save(update_fields=["lock_at"])

        self.client.force_authenticate(user=self.fan)

        response = self.client.post(
            f"/api/fantasy/teams/{team.id}/lineups/",
            {
                "gameweek_id": self.gameweek.id,
                "player_ids": self.selected_player_ids,
                "captain_id": self.player_3.id,
                "vice_captain_id": self.player_1.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("gameweek", response.data)

    def test_fan_can_create_private_league_and_join_by_code(self):
        team = FantasyTeam.objects.create(
            owner=self.fan,
            fantasy_competition=self.fantasy_competition,
            name="Kobs Warriors Fantasy XV",
        )
        self.client.force_authenticate(user=self.fan)

        create_response = self.client.post(
            "/api/fantasy/leagues/",
            {
                "fantasy_competition_id": self.fantasy_competition.id,
                "name": "KOBS Fans Mini League",
                "league_type": FantasyLeague.LeagueType.PRIVATE,
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, 201)
        join_code = create_response.data["league"]["join_code"]
        self.assertTrue(join_code)

        join_response = self.client.post(
            "/api/fantasy/leagues/join/",
            {
                "fantasy_team_id": team.id,
                "join_code": join_code,
            },
            format="json",
        )

        self.assertEqual(join_response.status_code, 200)
        self.assertEqual(FantasyLeagueMembership.objects.count(), 1)

    def test_fan_cannot_update_another_users_team_squad(self):
        other_team = FantasyTeam.objects.create(
            owner=self.other_fan,
            fantasy_competition=self.fantasy_competition,
            name="Other Fan Team",
        )
        self.client.force_authenticate(user=self.fan)

        response = self.client.post(
            f"/api/fantasy/teams/{other_team.id}/squad/",
            {"player_ids": self.selected_player_ids},
            format="json",
        )

        self.assertEqual(response.status_code, 404)


class FantasyAdminAPITests(FantasyTestMixin, APITestCase):
    def test_fan_cannot_create_admin_fantasy_player(self):
        self.client.force_authenticate(user=self.fan)

        response = self.client.post(
            "/api/fantasy/admin/players/",
            {
                "fantasy_competition": self.fantasy_competition.id,
                "club": self.kobs.id,
                "display_name": "Unauthorized Player",
                "position": FantasyPlayer.Position.CENTRE,
                "previous_stats": {},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_league_admin_can_create_fantasy_player_with_auto_price(self):
        self.client.force_authenticate(user=self.league_admin)

        response = self.client.post(
            "/api/fantasy/admin/players/",
            {
                "fantasy_competition": self.fantasy_competition.id,
                "club": self.kobs.id,
                "display_name": "New Star Centre",
                "position": FantasyPlayer.Position.CENTRE,
                "previous_stats": {
                    "appearances": 12,
                    "tries": 4,
                    "try_assists": 3,
                    "tackles": 68,
                    "metres_carried": 412,
                    "clean_breaks": 9,
                    "player_of_match": 2,
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["player"]["price_source"], FantasyPlayer.PriceSource.AUTO
        )
        self.assertGreater(
            Decimal(response.data["player"]["final_price"]), Decimal("5.00")
        )

    def test_league_admin_can_override_player_price(self):
        self.client.force_authenticate(user=self.league_admin)

        response = self.client.patch(
            f"/api/fantasy/admin/players/{self.player_1.id}/price/",
            {
                "final_price": "10.00",
                "price_override_reason": "Adjusted for star player value.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.player_1.refresh_from_db()
        self.assertEqual(self.player_1.final_price, Decimal("10.00"))
        self.assertEqual(self.player_1.price_source, FantasyPlayer.PriceSource.MANUAL)

    def test_referee_can_submit_player_score_but_cannot_approve(self):
        self.client.force_authenticate(user=self.referee)

        submit_response = self.client.post(
            f"/api/fantasy/admin/gameweeks/{self.gameweek.id}/player-scores/",
            {
                "fantasy_player_id": self.player_1.id,
                "match_id": self.match.id,
                "points": "8.00",
                "breakdown": {"appearance": 2, "try": 5, "assist": 1},
                "status": FantasyPlayerGameweekScore.Status.SUBMITTED,
            },
            format="json",
        )

        self.assertEqual(submit_response.status_code, 200)
        score_id = submit_response.data["score"]["id"]

        approve_response = self.client.post(
            f"/api/fantasy/admin/player-scores/{score_id}/approve/",
            {},
            format="json",
        )

        self.assertEqual(approve_response.status_code, 403)

    def test_league_admin_can_approve_player_score(self):
        score = FantasyPlayerGameweekScore.objects.create(
            fantasy_player=self.player_1,
            gameweek=self.gameweek,
            match=self.match,
            points=Decimal("8.00"),
            breakdown={"appearance": 2, "try": 5, "assist": 1},
            status=FantasyPlayerGameweekScore.Status.SUBMITTED,
            entered_by=self.referee,
        )

        self.client.force_authenticate(user=self.league_admin)

        response = self.client.post(
            f"/api/fantasy/admin/player-scores/{score.id}/approve/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        score.refresh_from_db()
        self.assertEqual(score.status, FantasyPlayerGameweekScore.Status.APPROVED)
        self.assertEqual(score.approved_by, self.league_admin)
        self.assertIsNotNone(score.approved_at)

    def test_leaderboard_calculation_uses_approved_scores_and_captain_multiplier(self):
        team = FantasyTeam.objects.create(
            owner=self.fan,
            fantasy_competition=self.fantasy_competition,
            name="Kobs Warriors Fantasy XV",
        )
        FantasySquadPlayer.objects.bulk_create(
            [
                FantasySquadPlayer(
                    fantasy_team=team,
                    fantasy_player=player,
                    price_at_selection=player.final_price,
                )
                for player in [self.player_1, self.player_2, self.player_3]
            ]
        )
        lineup = FantasyLineup.objects.create(
            fantasy_team=team,
            gameweek=self.gameweek,
            captain=self.player_3,
            vice_captain=self.player_1,
        )
        FantasyLineupPlayer.objects.bulk_create(
            [
                FantasyLineupPlayer(
                    lineup=lineup,
                    fantasy_player=player,
                    is_starter=True,
                    sort_order=index,
                )
                for index, player in enumerate(
                    [self.player_1, self.player_2, self.player_3],
                    start=1,
                )
            ]
        )

        FantasyPlayerGameweekScore.objects.create(
            fantasy_player=self.player_1,
            gameweek=self.gameweek,
            match=self.match,
            points=Decimal("8.00"),
            status=FantasyPlayerGameweekScore.Status.APPROVED,
            entered_by=self.referee,
            approved_by=self.league_admin,
            approved_at=timezone.now(),
        )
        FantasyPlayerGameweekScore.objects.create(
            fantasy_player=self.player_2,
            gameweek=self.gameweek,
            match=self.match,
            points=Decimal("5.00"),
            status=FantasyPlayerGameweekScore.Status.APPROVED,
            entered_by=self.referee,
            approved_by=self.league_admin,
            approved_at=timezone.now(),
        )
        FantasyPlayerGameweekScore.objects.create(
            fantasy_player=self.player_3,
            gameweek=self.gameweek,
            match=self.match,
            points=Decimal("10.00"),
            status=FantasyPlayerGameweekScore.Status.APPROVED,
            entered_by=self.referee,
            approved_by=self.league_admin,
            approved_at=timezone.now(),
        )

        self.client.force_authenticate(user=self.league_admin)

        response = self.client.post(
            f"/api/fantasy/admin/gameweeks/{self.gameweek.id}/calculate/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        team_score = FantasyTeamGameweekScore.objects.get(
            fantasy_team=team,
            gameweek=self.gameweek,
        )

        # 8 + 5 + captain 10*2 = 33
        self.assertEqual(team_score.points, Decimal("33.00"))
        self.assertEqual(team_score.rank, 1)

        team.refresh_from_db()
        self.assertEqual(team.total_points, Decimal("33.00"))
        self.assertEqual(team.current_rank, 1)

    def test_league_admin_can_close_gameweek(self):
        self.client.force_authenticate(user=self.league_admin)

        response = self.client.post(
            f"/api/fantasy/admin/gameweeks/{self.gameweek.id}/close/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.gameweek.refresh_from_db()
        self.assertEqual(self.gameweek.status, FantasyGameweek.Status.COMPLETED)


class FantasyManagementCommandTests(APITestCase):
    def test_seed_fantasy_demo_data_command_creates_demo_records(self):
        out = StringIO()
        call_command("seed_fantasy_demo_data", stdout=out)

        self.assertIn("Fantasy demo data created.", out.getvalue())

        self.assertTrue(
            FantasyCompetition.objects.filter(
                slug="nile-special-rugby-fantasy-2026-demo"
            ).exists()
        )
        self.assertTrue(
            FantasyGameweek.objects.filter(
                fantasy_competition__slug="nile-special-rugby-fantasy-2026-demo",
                number=1,
            ).exists()
        )
        self.assertGreaterEqual(
            FantasyPlayer.objects.filter(
                fantasy_competition__slug="nile-special-rugby-fantasy-2026-demo"
            ).count(),
            15,
        )
        self.assertTrue(
            FantasyLeague.objects.filter(
                fantasy_competition__slug="nile-special-rugby-fantasy-2026-demo",
                league_type=FantasyLeague.LeagueType.PRIVATE,
                join_code__isnull=False,
            ).exists()
        )


class FantasyAPIRefinementTests(FantasyTestMixin, APITestCase):
    def _create_team_with_squad(self, owner=None, name="Kobs Warriors Fantasy XV"):
        owner = owner or self.fan

        team = FantasyTeam.objects.create(
            owner=owner,
            fantasy_competition=self.fantasy_competition,
            name=name,
        )

        FantasySquadPlayer.objects.bulk_create(
            [
                FantasySquadPlayer(
                    fantasy_team=team,
                    fantasy_player=player,
                    price_at_selection=player.final_price,
                )
                for player in [self.player_1, self.player_2, self.player_3]
            ]
        )

        return team

    def test_competition_gameweeks_endpoint_supports_pagination_and_status_filter(self):
        FantasyGameweek.objects.create(
            fantasy_competition=self.fantasy_competition,
            name="Gameweek 2",
            number=2,
            start_at=timezone.now() + timedelta(days=10),
            lock_at=timezone.now() + timedelta(days=12),
            end_at=timezone.now() + timedelta(days=14),
            status=FantasyGameweek.Status.COMPLETED,
        )

        paginated_response = self.client.get(
            f"/api/fantasy/competitions/{self.fantasy_competition.id}/gameweeks/",
            {"limit": 1, "offset": 0},
        )

        self.assertEqual(paginated_response.status_code, 200)
        self.assertEqual(paginated_response.data["count"], 2)
        self.assertEqual(paginated_response.data["limit"], 1)
        self.assertEqual(len(paginated_response.data["results"]), 1)

        filtered_response = self.client.get(
            f"/api/fantasy/competitions/{self.fantasy_competition.id}/gameweeks/",
            {"status": FantasyGameweek.Status.OPEN},
        )

        self.assertEqual(filtered_response.status_code, 200)
        self.assertEqual(filtered_response.data["count"], 1)
        self.assertEqual(
            filtered_response.data["results"][0]["status"],
            FantasyGameweek.Status.OPEN,
        )

    def test_team_detail_endpoint_returns_authenticated_users_team(self):
        team = self._create_team_with_squad()
        self.client.force_authenticate(user=self.fan)

        response = self.client.get(f"/api/fantasy/teams/{team.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["team"]["name"], team.name)
        self.assertEqual(len(response.data["team"]["squad_players"]), 3)

    def test_team_detail_endpoint_does_not_return_another_users_team(self):
        other_team = self._create_team_with_squad(
            owner=self.other_fan,
            name="Other Fan Fantasy Team",
        )
        self.client.force_authenticate(user=self.fan)

        response = self.client.get(f"/api/fantasy/teams/{other_team.id}/")

        self.assertEqual(response.status_code, 404)

    def test_team_history_endpoint_returns_scores_and_lineups(self):
        team = self._create_team_with_squad()

        lineup = FantasyLineup.objects.create(
            fantasy_team=team,
            gameweek=self.gameweek,
            captain=self.player_3,
            vice_captain=self.player_1,
        )

        FantasyLineupPlayer.objects.bulk_create(
            [
                FantasyLineupPlayer(
                    lineup=lineup,
                    fantasy_player=player,
                    is_starter=True,
                    sort_order=index,
                )
                for index, player in enumerate(
                    [self.player_1, self.player_2, self.player_3],
                    start=1,
                )
            ]
        )

        FantasyTeamGameweekScore.objects.create(
            fantasy_team=team,
            gameweek=self.gameweek,
            points=Decimal("33.00"),
            rank=1,
            breakdown={"players": []},
        )

        self.client.force_authenticate(user=self.fan)

        response = self.client.get(f"/api/fantasy/teams/{team.id}/history/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["team"]["name"], team.name)
        self.assertEqual(len(response.data["scores"]), 1)
        self.assertEqual(len(response.data["lineups"]), 1)

    def test_available_leagues_endpoint_returns_public_leagues_by_default(self):
        public_league = FantasyLeague.objects.create(
            fantasy_competition=self.fantasy_competition,
            name="Public Rugby Fantasy League",
            league_type=FantasyLeague.LeagueType.PUBLIC,
            created_by=self.league_admin,
        )
        private_league = FantasyLeague.objects.create(
            fantasy_competition=self.fantasy_competition,
            name="Private KOBS Fans League",
            league_type=FantasyLeague.LeagueType.PRIVATE,
            created_by=self.fan,
        )

        response = self.client.get("/api/fantasy/leagues/available/")

        self.assertEqual(response.status_code, 200)

        league_names = {league["name"] for league in response.data["results"]}

        self.assertIn(public_league.name, league_names)
        self.assertNotIn(private_league.name, league_names)

    def test_anonymous_user_cannot_list_private_available_leagues(self):
        FantasyLeague.objects.create(
            fantasy_competition=self.fantasy_competition,
            name="Private KOBS Fans League",
            league_type=FantasyLeague.LeagueType.PRIVATE,
            created_by=self.fan,
        )

        response = self.client.get(
            "/api/fantasy/leagues/available/",
            {"league_type": FantasyLeague.LeagueType.PRIVATE},
        )

        self.assertEqual(response.status_code, 403)

    def test_authenticated_user_only_sees_own_or_joined_private_leagues(self):
        team = self._create_team_with_squad(owner=self.fan)

        own_private_league = FantasyLeague.objects.create(
            fantasy_competition=self.fantasy_competition,
            name="My Private Fantasy League",
            league_type=FantasyLeague.LeagueType.PRIVATE,
            created_by=self.fan,
        )
        joined_private_league = FantasyLeague.objects.create(
            fantasy_competition=self.fantasy_competition,
            name="Joined Private Fantasy League",
            league_type=FantasyLeague.LeagueType.PRIVATE,
            created_by=self.other_fan,
        )
        unrelated_private_league = FantasyLeague.objects.create(
            fantasy_competition=self.fantasy_competition,
            name="Unrelated Private Fantasy League",
            league_type=FantasyLeague.LeagueType.PRIVATE,
            created_by=self.other_fan,
        )

        FantasyLeagueMembership.objects.create(
            fantasy_league=joined_private_league,
            fantasy_team=team,
        )

        self.client.force_authenticate(user=self.fan)

        response = self.client.get(
            "/api/fantasy/leagues/available/",
            {"league_type": FantasyLeague.LeagueType.PRIVATE},
        )

        self.assertEqual(response.status_code, 200)

        league_names = {league["name"] for league in response.data["results"]}

        self.assertIn(own_private_league.name, league_names)
        self.assertIn(joined_private_league.name, league_names)
        self.assertNotIn(unrelated_private_league.name, league_names)

    def test_public_league_detail_can_be_viewed_without_login(self):
        public_league = FantasyLeague.objects.create(
            fantasy_competition=self.fantasy_competition,
            name="Public Rugby Fantasy League",
            league_type=FantasyLeague.LeagueType.PUBLIC,
            created_by=self.league_admin,
        )

        response = self.client.get(f"/api/fantasy/leagues/{public_league.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["league"]["name"], public_league.name)

    def test_private_league_detail_requires_creator_or_member(self):
        private_league = FantasyLeague.objects.create(
            fantasy_competition=self.fantasy_competition,
            name="Private KOBS Fans League",
            league_type=FantasyLeague.LeagueType.PRIVATE,
            created_by=self.fan,
        )

        anonymous_response = self.client.get(
            f"/api/fantasy/leagues/{private_league.id}/"
        )
        self.assertEqual(anonymous_response.status_code, 403)

        self.client.force_authenticate(user=self.other_fan)
        other_user_response = self.client.get(
            f"/api/fantasy/leagues/{private_league.id}/"
        )
        self.assertEqual(other_user_response.status_code, 403)

        self.client.force_authenticate(user=self.fan)
        creator_response = self.client.get(f"/api/fantasy/leagues/{private_league.id}/")

        self.assertEqual(creator_response.status_code, 200)
        self.assertEqual(creator_response.data["league"]["name"], private_league.name)

    def test_league_leaderboard_returns_overall_and_gameweek_rankings(self):
        team = self._create_team_with_squad()
        team.total_points = Decimal("33.00")
        team.current_rank = 1
        team.save(update_fields=["total_points", "current_rank", "updated_at"])

        public_league = FantasyLeague.objects.create(
            fantasy_competition=self.fantasy_competition,
            name="Public Rugby Fantasy League",
            league_type=FantasyLeague.LeagueType.PUBLIC,
            created_by=self.league_admin,
        )

        FantasyLeagueMembership.objects.create(
            fantasy_league=public_league,
            fantasy_team=team,
        )

        FantasyTeamGameweekScore.objects.create(
            fantasy_team=team,
            gameweek=self.gameweek,
            points=Decimal("33.00"),
            rank=1,
            breakdown={"players": []},
        )

        overall_response = self.client.get(
            f"/api/fantasy/leagues/{public_league.id}/leaderboard/"
        )

        self.assertEqual(overall_response.status_code, 200)
        self.assertEqual(overall_response.data["count"], 1)
        self.assertEqual(overall_response.data["results"][0]["name"], team.name)

        gameweek_response = self.client.get(
            f"/api/fantasy/leagues/{public_league.id}/leaderboard/",
            {"gameweek_id": self.gameweek.id},
        )

        self.assertEqual(gameweek_response.status_code, 200)
        self.assertEqual(gameweek_response.data["count"], 1)
        self.assertEqual(
            gameweek_response.data["results"][0]["fantasy_team_name"],
            team.name,
        )


class FantasyAdminOperationsRefinementTests(FantasyTestMixin, APITestCase):
    def test_fan_cannot_access_fantasy_admin_dashboard(self):
        self.client.force_authenticate(user=self.fan)

        response = self.client.get("/api/fantasy/admin/dashboard/")

        self.assertEqual(response.status_code, 403)

    def test_league_admin_dashboard_returns_summary(self):
        self.client.force_authenticate(user=self.league_admin)

        response = self.client.get(
            "/api/fantasy/admin/dashboard/",
            {"competition": self.fantasy_competition.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["competitions_count"], 1)
        self.assertEqual(response.data["summary"]["gameweeks_count"], 1)
        self.assertEqual(response.data["summary"]["players_count"], 4)
        self.assertEqual(response.data["summary"]["available_players_count"], 4)

    def test_league_admin_can_list_and_update_fantasy_competition(self):
        self.client.force_authenticate(user=self.league_admin)

        list_response = self.client.get(
            "/api/fantasy/admin/competitions/",
            {"search": "Nile", "limit": 10, "offset": 0},
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["count"], 1)

        update_response = self.client.patch(
            f"/api/fantasy/admin/competitions/{self.fantasy_competition.id}/",
            {
                "name": "Nile Special Rugby Fantasy Updated",
                "status": FantasyCompetition.Status.LOCKED,
                "budget": "120.00",
                "squad_size": 3,
                "lineup_size": 2,
                "rules_summary": "Updated admin rules.",
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, 200)

        self.fantasy_competition.refresh_from_db()
        self.assertEqual(
            self.fantasy_competition.name,
            "Nile Special Rugby Fantasy Updated",
        )
        self.assertEqual(
            self.fantasy_competition.status,
            FantasyCompetition.Status.LOCKED,
        )
        self.assertEqual(self.fantasy_competition.budget, Decimal("120.00"))
        self.assertEqual(self.fantasy_competition.lineup_size, 2)

    def test_competition_update_rejects_lineup_size_larger_than_squad_size(self):
        self.client.force_authenticate(user=self.league_admin)

        response = self.client.patch(
            f"/api/fantasy/admin/competitions/{self.fantasy_competition.id}/",
            {
                "squad_size": 3,
                "lineup_size": 4,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("lineup_size", response.data)

    def test_league_admin_can_update_gameweek_settings(self):
        self.client.force_authenticate(user=self.league_admin)

        response = self.client.patch(
            f"/api/fantasy/admin/gameweeks/{self.gameweek.id}/",
            {
                "name": "Updated Gameweek 1",
                "status": FantasyGameweek.Status.SCORING,
                "matches": [self.match.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.gameweek.refresh_from_db()
        self.assertEqual(self.gameweek.name, "Updated Gameweek 1")
        self.assertEqual(self.gameweek.status, FantasyGameweek.Status.SCORING)
        self.assertEqual(self.gameweek.matches.count(), 1)

    def test_league_admin_can_update_player_and_recalculate_price(self):
        self.client.force_authenticate(user=self.league_admin)

        update_response = self.client.patch(
            f"/api/fantasy/admin/players/{self.player_1.id}/",
            {
                "display_name": "Ian Munyani Updated",
                "is_available": False,
                "availability_note": "Injury watch.",
                "previous_stats": {
                    "appearances": 15,
                    "tries": 7,
                    "try_assists": 5,
                    "tackles": 80,
                    "metres_carried": 500,
                    "clean_breaks": 12,
                    "player_of_match": 3,
                },
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, 200)

        self.player_1.refresh_from_db()
        self.assertEqual(self.player_1.display_name, "Ian Munyani Updated")
        self.assertFalse(self.player_1.is_available)
        self.assertEqual(self.player_1.availability_note, "Injury watch.")

        recalculate_response = self.client.post(
            f"/api/fantasy/admin/players/{self.player_1.id}/recalculate-price/",
            {},
            format="json",
        )

        self.assertEqual(recalculate_response.status_code, 200)

        self.player_1.refresh_from_db()
        self.assertEqual(self.player_1.price_source, FantasyPlayer.PriceSource.AUTO)
        self.assertGreaterEqual(
            self.player_1.final_price,
            self.fantasy_competition.min_player_price,
        )
        self.assertLessEqual(
            self.player_1.final_price,
            self.fantasy_competition.max_player_price,
        )

    def test_admin_can_list_update_and_reject_player_score(self):
        score = FantasyPlayerGameweekScore.objects.create(
            fantasy_player=self.player_1,
            gameweek=self.gameweek,
            match=self.match,
            points=Decimal("8.00"),
            breakdown={"appearance": 2, "try": 5, "assist": 1},
            status=FantasyPlayerGameweekScore.Status.SUBMITTED,
            entered_by=self.referee,
        )

        self.client.force_authenticate(user=self.league_admin)

        list_response = self.client.get(
            f"/api/fantasy/admin/gameweeks/{self.gameweek.id}/player-scores/",
            {"status": FantasyPlayerGameweekScore.Status.SUBMITTED},
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["count"], 1)

        detail_response = self.client.get(
            f"/api/fantasy/admin/player-scores/{score.id}/"
        )

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data["score"]["id"], score.id)

        update_response = self.client.patch(
            f"/api/fantasy/admin/player-scores/{score.id}/",
            {
                "points": "7.50",
                "breakdown": {"appearance": 2, "try": 5, "penalty": "-0.50"},
                "status": FantasyPlayerGameweekScore.Status.DRAFT,
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, 200)

        score.refresh_from_db()
        self.assertEqual(score.points, Decimal("7.50"))
        self.assertEqual(score.status, FantasyPlayerGameweekScore.Status.DRAFT)

        reject_response = self.client.post(
            f"/api/fantasy/admin/player-scores/{score.id}/reject/",
            {},
            format="json",
        )

        self.assertEqual(reject_response.status_code, 200)

        score.refresh_from_db()
        self.assertEqual(score.status, FantasyPlayerGameweekScore.Status.REJECTED)
        self.assertEqual(score.approved_by, self.league_admin)
        self.assertIsNotNone(score.approved_at)

    def test_referee_cannot_reject_player_score(self):
        score = FantasyPlayerGameweekScore.objects.create(
            fantasy_player=self.player_1,
            gameweek=self.gameweek,
            match=self.match,
            points=Decimal("8.00"),
            breakdown={"appearance": 2, "try": 5, "assist": 1},
            status=FantasyPlayerGameweekScore.Status.SUBMITTED,
            entered_by=self.referee,
        )

        self.client.force_authenticate(user=self.referee)

        response = self.client.post(
            f"/api/fantasy/admin/player-scores/{score.id}/reject/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
