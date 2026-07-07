from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import Club
from dashboards.models import Competition, League, Match, Union, UnionWorkspace


WORKSPACE_DATA = {
    "URU": {
        "union": "Uganda Rugby Union",
        "sport": "Rugby",
        "leagues": [
            {
                "name": "Nile Special Rugby League",
                "slug": "nile-special-rugby-league",
                "description": "Top flight Ugandan rugby league.",
                "competitions": [
                    ("Nile Special Rugby League 2026", "nile-special-rugby-league-2026", "2026"),
                    ("Uganda Cup 2026", "uganda-cup-2026", "2026"),
                    ("Rugby 7s Series 2026", "rugby-7s-series-2026", "2026"),
                ],
            }
        ],
        "clubs": [
            ("KCB KOBS", "kcb-kobs", "KOBS"),
            ("Platinum Credit Heathens", "heathens-rfc", "Heathens"),
            ("Black Pirates", "black-pirates", "Pirates"),
            ("Impis RFC", "impis-rfc", "Impis"),
            ("Jinja Hippos", "jinja-hippos", "Hippos"),
            ("Toyota Buffaloes", "toyota-buffaloes", "Buffaloes"),
        ],
    },
    "FUFA": {
        "union": "Federation of Uganda Football Associations",
        "sport": "Football",
        "leagues": [
            {
                "name": "StarTimes Uganda Premier League",
                "slug": "startimes-uganda-premier-league",
                "description": "Top flight Ugandan football league.",
                "competitions": [
                    ("StarTimes Uganda Premier League 2026", "startimes-uganda-premier-league-2026", "2026"),
                    ("Stanbic Uganda Cup 2026", "stanbic-uganda-cup-2026", "2026"),
                    ("FUFA Super 8 2026", "fufa-super-8-2026", "2026"),
                ],
            }
        ],
        "clubs": [
            ("SC Villa", "sc-villa", "Villa"),
            ("Vipers SC", "vipers-sc", "Vipers"),
            ("KCCA FC", "kcca-fc", "KCCA"),
            ("Express FC", "express-fc", "Express"),
            ("URA FC", "ura-fc", "URA"),
            ("Kitara FC", "kitara-fc", "Kitara"),
        ],
    },
    "FUBA": {
        "union": "Federation of Uganda Basketball Associations",
        "sport": "Basketball",
        "leagues": [
            {
                "name": "National Basketball League",
                "slug": "national-basketball-league",
                "description": "Top flight Ugandan basketball league.",
                "competitions": [
                    ("National Basketball League 2026", "national-basketball-league-2026", "2026"),
                    ("Women’s National Basketball League 2026", "womens-national-basketball-league-2026", "2026"),
                    ("FUBA Playoffs 2026", "fuba-playoffs-2026", "2026"),
                ],
            }
        ],
        "clubs": [
            ("City Oilers", "city-oilers", "Oilers"),
            ("Namuwongo Blazers", "namuwongo-blazers", "Blazers"),
            ("KIU Titans", "kiu-titans", "KIU"),
            ("UCU Canons", "ucu-canons", "Canons"),
            ("JT Jaguars", "jt-jaguars", "Jaguars"),
            ("Power Basketball Club", "power-basketball-club", "Power"),
        ],
    },
    "BUDO": {
        "union": "Budo League",
        "sport": "Football",
        "leagues": [
            {
                "name": "Budo League",
                "slug": "budo-league",
                "description": "King’s College Budo old students community league.",
                "competitions": [
                    ("Budo League Season 2026", "budo-league-season-2026", "2026"),
                    ("Budo League Cup 2026", "budo-league-cup-2026", "2026"),
                ],
            }
        ],
        "clubs": [
            ("Budo Tigers", "budo-tigers", "Tigers"),
            ("Budo Lions", "budo-lions", "Lions"),
            ("Budo Eagles", "budo-eagles", "Eagles"),
            ("Budo Saints", "budo-saints", "Saints"),
            ("Budo Falcons", "budo-falcons", "Falcons"),
            ("Budo Panthers", "budo-panthers", "Panthers"),
        ],
    },
    "SMACK": {
        "union": "SMACK League",
        "sport": "Football",
        "leagues": [
            {
                "name": "SMACK League",
                "slug": "smack-league",
                "description": "St Mary’s College Kisubi old students community league.",
                "competitions": [
                    ("SMACK League Season 2026", "smack-league-season-2026", "2026"),
                    ("SMACK League Cup 2026", "smack-league-cup-2026", "2026"),
                ],
            }
        ],
        "clubs": [
            ("SMACK Spartans", "smack-spartans", "Spartans"),
            ("SMACK Cardinals", "smack-cardinals", "Cardinals"),
            ("SMACK Lions", "smack-lions", "Lions"),
            ("SMACK Eagles", "smack-eagles", "Eagles"),
            ("SMACK Knights", "smack-knights", "Knights"),
            ("SMACK Warriors", "smack-warriors", "Warriors"),
        ],
    },
}


SPORT_MAP = {
    "Rugby": Club.Sport.RUGBY,
    "Football": Club.Sport.FOOTBALL,
    "Basketball": Club.Sport.BASKETBALL,
}


class Command(BaseCommand):
    help = "Seed workspace-specific competitions, clubs and fixtures for union workspace dashboards."

    def handle(self, *args, **options):
        created_matches = 0

        for acronym, data in WORKSPACE_DATA.items():
            workspace = UnionWorkspace.objects.filter(acronym__iexact=acronym).first()

            if workspace is None:
                self.stdout.write(self.style.WARNING(f"Skipping {acronym}: workspace not found."))
                continue

            union_slug = slugify(data["union"])
            union = Union.objects.filter(name__iexact=data["union"]).first()

            if union is None:
                union = Union.objects.create(
                    name=data["union"],
                    slug=union_slug,
                    country="Uganda",
                    description=f"{data['union']} workspace demo record.",
                )
            else:
                union.country = union.country or "Uganda"
                union.description = union.description or f"{data['union']} workspace demo record."
                union.save(update_fields=["country", "description"])

            workspace.related_union = union
            workspace.sport = data["sport"]
            workspace.status = UnionWorkspace.Status.ACTIVE
            workspace.save(update_fields=["related_union", "sport", "status", "updated_at"])

            # Remove previously generated demo matches for this workspace before rebuilding.
            # This prevents old matches from keeping links to clubs that were later renamed/reused.
            for league_data in data["leagues"]:
                for _comp_name, comp_slug, _season in league_data["competitions"]:
                    Match.objects.filter(competition__slug=comp_slug).delete()

            sport_value = SPORT_MAP[data["sport"]]
            clubs = []

            for name, slug, short_name in data["clubs"]:
                club = (
                    Club.objects.filter(slug=slug).first()
                    or Club.objects.filter(name__iexact=name).first()
                )

                if club is None:
                    club = Club.objects.create(
                        name=name,
                        slug=slug,
                        short_name=short_name,
                        sport=sport_value,
                    )
                else:
                    club.name = name
                    club.slug = slug
                    club.short_name = short_name
                    club.sport = sport_value
                    club.save(update_fields=["name", "slug", "short_name", "sport"])

                clubs.append(club)

            for league_data in data["leagues"]:
                league, _ = League.objects.update_or_create(
                    slug=league_data["slug"],
                    defaults={
                        "union": union,
                        "name": league_data["name"],
                        "description": league_data["description"],
                        "is_active": True,
                    },
                )

                competitions = []

                for comp_name, comp_slug, season in league_data["competitions"]:
                    competition, _ = Competition.objects.update_or_create(
                        league=league,
                        slug=comp_slug,
                        defaults={
                            "name": comp_name,
                            "season": season,
                            "is_active": True,
                            "start_date": timezone.localdate(),
                            "end_date": timezone.localdate() + timedelta(days=120),
                        },
                    )
                    competitions.append(competition)

                for index, competition in enumerate(competitions):
                    if len(clubs) < 2:
                        continue

                    pairs = [
                        (clubs[0], clubs[1]),
                        (clubs[2 % len(clubs)], clubs[3 % len(clubs)]),
                        (clubs[4 % len(clubs)], clubs[5 % len(clubs)]),
                    ]

                    for round_index, (home, away) in enumerate(pairs, start=1):
                        match_date = timezone.now() + timedelta(days=(index * 7) + round_index)
                        existing = Match.objects.filter(
                            competition=competition,
                            home_club=home,
                            away_club=away,
                            round=f"Round {round_index}",
                        ).first()

                        if existing:
                            existing.match_date = match_date
                            existing.venue = self._venue_for(data["sport"], home)
                            existing.status = Match.Status.SCHEDULED
                            existing.save(update_fields=["match_date", "venue", "status", "updated_at"])
                        else:
                            Match.objects.create(
                                competition=competition,
                                home_club=home,
                                away_club=away,
                                status=Match.Status.SCHEDULED,
                                match_date=match_date,
                                venue=self._venue_for(data["sport"], home),
                                round=f"Round {round_index}",
                            )
                            created_matches += 1

            self.stdout.write(self.style.SUCCESS(f"Seeded operations data for {acronym}"))

        self.stdout.write(self.style.SUCCESS(f"Created {created_matches} new scheduled matches."))

    def _venue_for(self, sport, club):
        if sport == "Basketball":
            return "Lugogo Indoor Arena"

        if sport == "Football":
            return "Nakivubo Stadium"

        return "Legends Rugby Grounds"
