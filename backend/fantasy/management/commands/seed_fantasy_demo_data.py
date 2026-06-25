from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Club, User
from dashboards.models import Competition, League, Match, Union
from fantasy.models import (
    FantasyCompetition,
    FantasyGameweek,
    FantasyLeague,
    FantasyPlayer,
)
from fantasy.services import calculate_suggested_player_price


class Command(BaseCommand):
    help = "Create demo fantasy league data for frontend and QA testing."

    def handle(self, *args, **options):
        league_admin, _ = User.objects.get_or_create(
            email="fantasy-admin-demo@example.com",
            defaults={
                "first_name": "Fantasy",
                "last_name": "Admin",
                "role": User.Role.LEAGUE_ADMIN,
                "is_email_verified": True,
            },
        )
        league_admin.set_password("StrongPass123!")
        league_admin.save()

        fan, _ = User.objects.get_or_create(
            email="fantasy-fan-demo@example.com",
            defaults={
                "first_name": "Fantasy",
                "last_name": "Fan",
                "role": User.Role.FAN,
                "is_email_verified": True,
            },
        )
        fan.set_password("StrongPass123!")
        fan.save()

        scoring_officer, _ = User.objects.get_or_create(
            email="fantasy-scorer-demo@example.com",
            defaults={
                "first_name": "Fantasy",
                "last_name": "Scorer",
                "role": User.Role.REFEREE,
                "is_email_verified": True,
            },
        )
        scoring_officer.set_password("StrongPass123!")
        scoring_officer.save()

        union, _ = Union.objects.get_or_create(
            slug="uganda-rugby-union-fantasy-demo",
            defaults={
                "name": "Uganda Rugby Union Fantasy Demo",
                "country": "Uganda",
            },
        )

        league, _ = League.objects.get_or_create(
            slug="nile-special-rugby-fantasy-demo",
            defaults={
                "union": union,
                "name": "Nile Special Rugby Premiership Fantasy Demo",
            },
        )

        real_competition, _ = Competition.objects.get_or_create(
            slug="nile-special-rugby-premiership-2026-fantasy-demo",
            defaults={
                "league": league,
                "name": "Nile Special Rugby Premiership 2026 Fantasy Demo",
                "season": "2026",
            },
        )

        clubs = {}
        club_data = [
            ("kcb-kobs-fantasy-demo", "KCB Kobs Fantasy Demo"),
            ("heathens-rfc-fantasy-demo", "Heathens RFC Fantasy Demo"),
            ("pirates-rugby-fantasy-demo", "Pirates Rugby Club Fantasy Demo"),
            ("impis-rfc-fantasy-demo", "Impis RFC Fantasy Demo"),
        ]

        for slug, name in club_data:
            club, _ = Club.objects.get_or_create(
                slug=slug,
                defaults={"name": name},
            )
            clubs[slug] = club

        match_one, _ = Match.objects.get_or_create(
            competition=real_competition,
            home_club=clubs["kcb-kobs-fantasy-demo"],
            away_club=clubs["heathens-rfc-fantasy-demo"],
            defaults={
                "match_date": timezone.now() + timedelta(days=7),
                "venue": "Legends Rugby Grounds",
                "status": Match.Status.SCHEDULED,
            },
        )

        match_two, _ = Match.objects.get_or_create(
            competition=real_competition,
            home_club=clubs["pirates-rugby-fantasy-demo"],
            away_club=clubs["impis-rfc-fantasy-demo"],
            defaults={
                "match_date": timezone.now() + timedelta(days=8),
                "venue": "Kings Park Arena",
                "status": Match.Status.SCHEDULED,
            },
        )

        fantasy_competition, _ = FantasyCompetition.objects.get_or_create(
            slug="nile-special-rugby-fantasy-2026-demo",
            defaults={
                "name": "Nile Special Rugby Fantasy 2026 Demo",
                "linked_competition": real_competition,
                "sport": FantasyCompetition.Sport.RUGBY,
                "season": "2026",
                "status": FantasyCompetition.Status.OPEN,
                "budget": Decimal("100.00"),
                "squad_size": 15,
                "lineup_size": 15,
                "max_players_per_club": 4,
                "captain_multiplier": Decimal("2.00"),
                "rules_summary": (
                    "Build a 15-player rugby fantasy squad with a 100 credit budget. "
                    "Captain earns double points. Lineups lock before the gameweek."
                ),
                "created_by": league_admin,
            },
        )

        gameweek, _ = FantasyGameweek.objects.get_or_create(
            fantasy_competition=fantasy_competition,
            number=1,
            defaults={
                "name": "Gameweek 1",
                "start_at": timezone.now(),
                "lock_at": timezone.now() + timedelta(days=6),
                "end_at": timezone.now() + timedelta(days=9),
                "status": FantasyGameweek.Status.OPEN,
            },
        )
        gameweek.matches.set([match_one, match_two])

        public_league, _ = FantasyLeague.objects.get_or_create(
            fantasy_competition=fantasy_competition,
            name="Nile Special Global Fantasy League",
            defaults={
                "league_type": FantasyLeague.LeagueType.PUBLIC,
                "created_by": league_admin,
                "is_active": True,
            },
        )

        private_league, _ = FantasyLeague.objects.get_or_create(
            fantasy_competition=fantasy_competition,
            name="KOBS Fans Mini League",
            defaults={
                "league_type": FantasyLeague.LeagueType.PRIVATE,
                "created_by": fan,
                "is_active": True,
            },
        )

        player_data = [
            {
                "name": "Ian Munyani",
                "club": clubs["kcb-kobs-fantasy-demo"],
                "position": FantasyPlayer.Position.CENTRE,
                "stats": {
                    "appearances": 12,
                    "tries": 4,
                    "try_assists": 3,
                    "tackles": 68,
                    "metres_carried": 412,
                    "clean_breaks": 9,
                    "player_of_match": 2,
                },
            },
            {
                "name": "Pius Ogena",
                "club": clubs["kcb-kobs-fantasy-demo"],
                "position": FantasyPlayer.Position.BACK_ROW,
                "stats": {
                    "appearances": 11,
                    "tries": 5,
                    "try_assists": 1,
                    "tackles": 94,
                    "metres_carried": 330,
                    "clean_breaks": 4,
                    "player_of_match": 1,
                },
            },
            {
                "name": "Joseph Aredo",
                "club": clubs["kcb-kobs-fantasy-demo"],
                "position": FantasyPlayer.Position.FLY_HALF,
                "stats": {
                    "appearances": 10,
                    "tries": 2,
                    "try_assists": 6,
                    "tackles": 40,
                    "metres_carried": 280,
                    "clean_breaks": 5,
                    "player_of_match": 2,
                },
            },
            {
                "name": "Kobs Utility Forward",
                "club": clubs["kcb-kobs-fantasy-demo"],
                "position": FantasyPlayer.Position.UTILITY,
                "stats": {"appearances": 8, "tries": 1, "tackles": 55},
            },
            {
                "name": "Philip Wokorach",
                "club": clubs["heathens-rfc-fantasy-demo"],
                "position": FantasyPlayer.Position.FULLBACK,
                "stats": {
                    "appearances": 12,
                    "tries": 6,
                    "try_assists": 5,
                    "tackles": 35,
                    "metres_carried": 520,
                    "clean_breaks": 12,
                    "player_of_match": 3,
                },
            },
            {
                "name": "Heathens Scrum Half",
                "club": clubs["heathens-rfc-fantasy-demo"],
                "position": FantasyPlayer.Position.SCRUM_HALF,
                "stats": {
                    "appearances": 10,
                    "tries": 2,
                    "try_assists": 4,
                    "tackles": 48,
                },
            },
            {
                "name": "Heathens Lock",
                "club": clubs["heathens-rfc-fantasy-demo"],
                "position": FantasyPlayer.Position.LOCK,
                "stats": {"appearances": 9, "tries": 1, "tackles": 70},
            },
            {
                "name": "Heathens Wing",
                "club": clubs["heathens-rfc-fantasy-demo"],
                "position": FantasyPlayer.Position.WING,
                "stats": {"appearances": 7, "tries": 4, "metres_carried": 240},
            },
            {
                "name": "Pirates Centre",
                "club": clubs["pirates-rugby-fantasy-demo"],
                "position": FantasyPlayer.Position.CENTRE,
                "stats": {"appearances": 10, "tries": 3, "tackles": 44},
            },
            {
                "name": "Pirates Back Row",
                "club": clubs["pirates-rugby-fantasy-demo"],
                "position": FantasyPlayer.Position.BACK_ROW,
                "stats": {"appearances": 11, "tries": 2, "tackles": 88},
            },
            {
                "name": "Pirates Fullback",
                "club": clubs["pirates-rugby-fantasy-demo"],
                "position": FantasyPlayer.Position.FULLBACK,
                "stats": {"appearances": 8, "tries": 4, "try_assists": 3},
            },
            {
                "name": "Pirates Prop",
                "club": clubs["pirates-rugby-fantasy-demo"],
                "position": FantasyPlayer.Position.PROP,
                "stats": {"appearances": 9, "tries": 1, "tackles": 64},
            },
            {
                "name": "Impis Fly Half",
                "club": clubs["impis-rfc-fantasy-demo"],
                "position": FantasyPlayer.Position.FLY_HALF,
                "stats": {"appearances": 9, "tries": 2, "try_assists": 5},
            },
            {
                "name": "Impis Wing",
                "club": clubs["impis-rfc-fantasy-demo"],
                "position": FantasyPlayer.Position.WING,
                "stats": {"appearances": 10, "tries": 5, "metres_carried": 380},
            },
            {
                "name": "Impis Hooker",
                "club": clubs["impis-rfc-fantasy-demo"],
                "position": FantasyPlayer.Position.HOOKER,
                "stats": {"appearances": 8, "tries": 2, "tackles": 58},
            },
            {
                "name": "Impis Utility Back",
                "club": clubs["impis-rfc-fantasy-demo"],
                "position": FantasyPlayer.Position.UTILITY,
                "stats": {"appearances": 7, "tries": 2, "try_assists": 2},
            },
        ]

        created_players = []

        for row in player_data:
            suggested_price = calculate_suggested_player_price(
                fantasy_competition,
                previous_stats=row["stats"],
            )

            player, _ = FantasyPlayer.objects.update_or_create(
                fantasy_competition=fantasy_competition,
                club=row["club"],
                display_name=row["name"],
                defaults={
                    "position": row["position"],
                    "previous_stats": row["stats"],
                    "calculated_price": suggested_price,
                    "final_price": suggested_price,
                    "price_source": FantasyPlayer.PriceSource.AUTO,
                    "is_active": True,
                    "is_available": True,
                },
            )
            created_players.append(player)

        self.stdout.write(self.style.SUCCESS("Fantasy demo data created."))

        self.stdout.write("")
        self.stdout.write("Demo fantasy admin login:")
        self.stdout.write("  email: fantasy-admin-demo@example.com")
        self.stdout.write("  password: StrongPass123!")

        self.stdout.write("")
        self.stdout.write("Demo fantasy fan login:")
        self.stdout.write("  email: fantasy-fan-demo@example.com")
        self.stdout.write("  password: StrongPass123!")

        self.stdout.write("")
        self.stdout.write("Demo fantasy scoring officer login:")
        self.stdout.write("  email: fantasy-scorer-demo@example.com")
        self.stdout.write("  password: StrongPass123!")

        self.stdout.write("")
        self.stdout.write("Fantasy competition:")
        self.stdout.write(f"  id: {fantasy_competition.id}")
        self.stdout.write(f"  name: {fantasy_competition.name}")

        self.stdout.write("")
        self.stdout.write("Gameweek:")
        self.stdout.write(f"  id: {gameweek.id}")
        self.stdout.write(f"  name: {gameweek.name}")

        self.stdout.write("")
        self.stdout.write("Fantasy leagues:")
        self.stdout.write(f"  public: {public_league.name}")
        self.stdout.write(f"  private: {private_league.name}")
        self.stdout.write(f"  private join code: {private_league.join_code}")

        self.stdout.write("")
        self.stdout.write(f"Players created/updated: {len(created_players)}")
