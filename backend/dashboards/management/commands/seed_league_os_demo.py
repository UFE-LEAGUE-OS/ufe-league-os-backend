from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import (
    Club,
    Follow,
    Notification,
    NotificationPreference,
    PaymentHistory,
    User,
    Wallet,
)
from dashboards.models import Competition, League, Match, Standing, Union
from fantasy.models import (
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
from memberships.models import (
    MembershipCard,
    MembershipPayment,
    MembershipPlan,
    MembershipSubscription,
)
from ticketing.models import Ticket, TicketOrder, TicketOrderItem, TicketType

try:
    from sponsorships.models import (
        SponsorAccount,
        SponsorAccountMember,
        SponsorBenefit,
        SponsorCategory,
        SponsorPackage,
        SponsorshipOwnerType,
        SponsorshipScopeType,
    )
except ImportError:  # pragma: no cover - keeps command safe if sponsorship app changes.
    SponsorAccount = None
    SponsorAccountMember = None
    SponsorBenefit = None
    SponsorCategory = None
    SponsorPackage = None
    SponsorshipOwnerType = None
    SponsorshipScopeType = None


RUGBY = "RUGBY"
FOOTBALL = "FOOTBALL"
BASKETBALL = "BASKETBALL"

UNIONS = [
    {
        "name": "Uganda Rugby Union",
        "slug": "uganda-rugby-union",
        "country": "Uganda",
        "description": "National rugby union federation demo record.",
    },
    {
        "name": "Federation of Uganda Football Associations",
        "slug": "fufa",
        "country": "Uganda",
        "description": "National football federation demo record.",
    },
    {
        "name": "Federation of Uganda Basketball Associations",
        "slug": "fuba",
        "country": "Uganda",
        "description": "National basketball federation demo record.",
    },
]

LEAGUES = [
    {
        "name": "Nile Special Rugby Premiership",
        "slug": "nile-special-rugby-premiership",
        "union_slug": "uganda-rugby-union",
        "description": "Top-flight rugby competition in the League OS demo.",
    },
    {
        "name": "StarTimes Uganda Premier League",
        "slug": "startimes-uganda-premier-league",
        "union_slug": "fufa",
        "description": "Top-flight football competition in the League OS demo.",
    },
    {
        "name": "National Basketball League",
        "slug": "national-basketball-league",
        "union_slug": "fuba",
        "description": "Top-flight basketball competition in the League OS demo.",
    },
]

CLUBS = [
    # Rugby: 12 clubs x 30 fantasy players = 360 players.
    ("KCB KOBS", "kobs", "KOBS", RUGBY, "Legends Rugby Grounds"),
    (
        "Platinum Credit Heathens",
        "heathens-rfc",
        "Heathens",
        RUGBY,
        "Kyadondo Rugby Club",
    ),
    (
        "Black Pirates",
        "black-pirates",
        "Pirates",
        RUGBY,
        "Kings Park Arena, Bweyogerere",
    ),
    ("Impis RFC", "impis-rfc", "Impis", RUGBY, "Makerere Rugby Grounds"),
    ("Jinja Hippos", "jinja-hippos", "Hippos", RUGBY, "Dam Waters Rugby Grounds"),
    ("Toyota Buffaloes", "toyota-buffaloes", "Buffaloes", RUGBY, "Kyadondo Rugby Club"),
    ("Rams RFC", "rams-rfc", "Rams", RUGBY, "Makerere Rugby Grounds"),
    ("Mongers RFC", "mongers-rfc", "Mongers", RUGBY, "Entebbe Rugby Grounds"),
    (
        "Walukuba Barbarians",
        "walukuba-barbarians",
        "Walukuba",
        RUGBY,
        "Walukuba Grounds",
    ),
    ("Warriors RFC", "warriors-rfc", "Warriors", RUGBY, "Legends Rugby Grounds"),
    (
        "Eagles Rugby Club",
        "eagles-rugby-club",
        "Eagles",
        RUGBY,
        "Kitante Sports Ground",
    ),
    ("KOBS Women", "kobs-women", "KOBS Women", RUGBY, "Legends Rugby Grounds"),
    # Football: 10 clubs x 25 fantasy players = 250 players.
    ("SC Villa", "sc-villa", "Villa", FOOTBALL, "Muteesa II Stadium, Wankulukuku"),
    ("Vipers SC", "vipers-sc", "Vipers", FOOTBALL, "St Mary's Stadium, Kitende"),
    ("KCCA FC", "kcca-fc", "KCCA", FOOTBALL, "MTN Omondi Stadium, Lugogo"),
    (
        "Express FC",
        "express-fc",
        "Express",
        FOOTBALL,
        "Muteesa II Stadium, Wankulukuku",
    ),
    ("URA FC", "ura-fc", "URA", FOOTBALL, "Nakivubo Stadium"),
    ("Maroons FC", "maroons-fc", "Maroons", FOOTBALL, "Luzira Prisons Ground"),
    ("Wakiso Giants", "wakiso-giants", "Wakiso", FOOTBALL, "Kabaka Kyabaggu Stadium"),
    ("UPDF FC", "updf-fc", "UPDF", FOOTBALL, "Bombo Military Barracks Ground"),
    ("BUL FC", "bul-fc", "BUL", FOOTBALL, "FUFA Technical Centre, Njeru"),
    ("Kitara FC", "kitara-fc", "Kitara", FOOTBALL, "Masindi Municipal Stadium"),
    # Basketball: 8 clubs x 15 fantasy players = 120 players.
    ("City Oilers", "city-oilers", "Oilers", BASKETBALL, "Lugogo Indoor Arena"),
    (
        "Namuwongo Blazers",
        "namuwongo-blazers",
        "Blazers",
        BASKETBALL,
        "Lugogo Indoor Arena",
    ),
    ("KIU Titans", "kiu-titans", "KIU", BASKETBALL, "KIU Courts"),
    ("UCU Canons", "ucu-canons", "Canons", BASKETBALL, "UCU Mukono Arena"),
    (
        "Power Basketball Club",
        "power-basketball-club",
        "Power",
        BASKETBALL,
        "Lugogo Indoor Arena",
    ),
    ("Javon Ladies", "javon-ladies", "Javon", BASKETBALL, "Lugogo Indoor Arena"),
    ("JT Jaguars", "jt-jaguars", "Jaguars", BASKETBALL, "Lugogo Indoor Arena"),
    ("Our Saviour BC", "our-saviour-bc", "Saviour", BASKETBALL, "Lugogo Indoor Arena"),
]

COMPETITIONS = [
    {
        "name": "Nile Special Rugby Premiership 2026",
        "slug": "nile-special-rugby-premiership-2026",
        "league_slug": "nile-special-rugby-premiership",
        "season": "2026",
        "sport": RUGBY,
    },
    {
        "name": "StarTimes Uganda Premier League 2026",
        "slug": "startimes-uganda-premier-league-2026",
        "league_slug": "startimes-uganda-premier-league",
        "season": "2026",
        "sport": FOOTBALL,
    },
    {
        "name": "National Basketball League 2026",
        "slug": "national-basketball-league-2026",
        "league_slug": "national-basketball-league",
        "season": "2026",
        "sport": BASKETBALL,
    },
]

SPONSORS = [
    ("Nile Special", "UG-BRN-DEMO-NILE", "BEVERAGE"),
    ("KCB Bank Uganda", "UG-BRN-DEMO-KCB", "BANKING"),
    ("MTN Uganda", "UG-BRN-DEMO-MTN", "TELECOM"),
    ("Stanbic Bank Uganda", "UG-BRN-DEMO-STANBIC", "BANKING"),
    ("Refactory", "UG-BRN-DEMO-REFACTORY", "EDUCATION"),
]

FIRST_NAMES = [
    "Akena",
    "Brian",
    "Calvin",
    "Daniel",
    "Edwin",
    "Farouk",
    "Gideon",
    "Hakim",
    "Ivan",
    "Joel",
    "Kevin",
    "Lawrence",
    "Martin",
    "Nelson",
    "Oscar",
    "Paul",
    "Quentin",
    "Raymond",
    "Samuel",
    "Timothy",
    "Umar",
    "Victor",
    "William",
    "Yasin",
    "Zziwa",
    "Adrian",
    "Benon",
    "Collins",
    "Derrick",
    "Elijah",
]

LAST_NAMES = [
    "Akello",
    "Baluku",
    "Byaruhanga",
    "Ddamulira",
    "Egesa",
    "Kato",
    "Kisembo",
    "Lubega",
    "Mugisha",
    "Mukasa",
    "Mutebi",
    "Nsubuga",
    "Ocitti",
    "Okello",
    "Otim",
    "Sebugwawo",
    "Ssenyonga",
    "Tibamanya",
    "Waiswa",
    "Wandera",
]

POSITIONS_BY_SPORT = {
    RUGBY: [
        "PROP",
        "HOOKER",
        "LOCK",
        "BACK_ROW",
        "SCRUM_HALF",
        "FLY_HALF",
        "CENTRE",
        "WING",
        "FULLBACK",
    ],
    FOOTBALL: ["GOALKEEPER", "DEFENDER", "MIDFIELDER", "FORWARD"],
    BASKETBALL: ["GUARD", "FORWARD_BASKETBALL", "CENTER_BASKETBALL"],
}

PLAYERS_PER_CLUB = {
    RUGBY: 30,
    FOOTBALL: 25,
    BASKETBALL: 15,
}


class Command(BaseCommand):
    help = "Seed League OS demo data for local, staging, or production-demo use."

    def add_arguments(self, parser):
        parser.add_argument(
            "--environment",
            default="local",
            choices=["local", "staging", "production-demo"],
            help="Labels the seeded records so the team knows where they were created.",
        )
        parser.add_argument(
            "--email",
            default="keithseruyange+registertest@gmail.com",
            help="Main fan account that receives demo memberships, tickets and fantasy team.",
        )
        parser.add_argument(
            "--demo-password",
            default="StrongPass123!",
            help="Password for demo users created by this command.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.environment = options["environment"]
        self.demo_password = options["demo_password"]
        self.main_email = options["email"].strip().lower()

        self.stdout.write(self.style.NOTICE("Seeding League OS demo data..."))

        self.ensure_users()
        self.ensure_public_sports_data()
        self.ensure_memberships()
        self.ensure_ticketing()
        self.ensure_fantasy()
        self.ensure_sponsors()
        self.ensure_keith_activity()

        self.stdout.write(self.style.SUCCESS("League OS demo data seed completed."))
        self.print_summary()

    def field_names(self, model):
        return {field.name for field in model._meta.get_fields()}

    def apply_existing_fields(self, obj, values):
        fields = self.field_names(obj.__class__)
        for key, value in values.items():
            if key in fields:
                setattr(obj, key, value)

    def ensure_users(self):
        self.main_user = self.upsert_user(
            email=self.main_email,
            first_name="Keith",
            last_name="Seruyange",
            role=User.Role.FAN,
            favourite_sport="Rugby",
        )
        self.super_admin = self.upsert_user(
            email="superadmin-demo@leagueos.local",
            first_name="Demo",
            last_name="Super Admin",
            role=User.Role.SUPER_ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        self.ticketing_officer = self.upsert_user(
            email="ticketing-demo@leagueos.local",
            first_name="Demo",
            last_name="Ticketing Officer",
            role=User.Role.TICKETING_OFFICER,
        )
        self.sponsor_owner = self.upsert_user(
            email="sponsor-nile-demo@leagueos.local",
            first_name="Nile",
            last_name="Sponsor",
            role=User.Role.SPONSOR,
            is_sponsor=True,
            sponsor_type=User.SponsorType.CORPORATE,
        )

        Wallet.objects.update_or_create(
            user=self.main_user,
            defaults={"balance": Decimal("0.00"), "currency": "UGX", "is_active": True},
        )

    def upsert_user(self, email, first_name, last_name, role, **extra):
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(
                email=email,
                password=self.demo_password,
                first_name=first_name,
                last_name=last_name,
            )
        user.first_name = first_name
        user.last_name = last_name
        user.role = role
        user.is_email_verified = True
        for key, value in extra.items():
            setattr(user, key, value)
        user.set_password(self.demo_password)
        user.save()
        return user

    def ensure_public_sports_data(self):
        self.unions = {}
        for data in UNIONS:
            union = Union.objects.filter(slug=data["slug"]).first()
            if union is None:
                union = Union.objects.filter(name=data["name"]).first()
            if union is None:
                union = Union(slug=data["slug"])

            union.name = data["name"]
            union.slug = data["slug"]
            union.country = data["country"]
            union.description = data["description"]
            union.save()

            self.unions[data["slug"]] = union

        self.leagues = {}
        for data in LEAGUES:
            league = League.objects.filter(slug=data["slug"]).first()
            if league is None:
                league = League.objects.filter(name=data["name"]).first()
            if league is None:
                league = League(slug=data["slug"])

            league.union = self.unions[data["union_slug"]]
            league.name = data["name"]
            league.slug = data["slug"]
            league.description = data["description"]
            league.is_active = True
            league.save()

            self.leagues[data["slug"]] = league

        self.clubs = {}
        for name, slug, short_name, sport, venue in CLUBS:
            club = (
                Club.objects.filter(slug=slug).first()
                or Club.objects.filter(name=name).first()
            )
            if club is None:
                club = Club(slug=slug)
            club.name = name
            club.slug = slug
            self.apply_existing_fields(
                club,
                {
                    "short_name": short_name,
                    "sport": sport,
                    "primary_color": "#7b3ff2",
                    "secondary_color": "#ff7a18",
                    "logo": f"clubs/logos/{slug}.png",
                    "banner": f"clubs/banners/{slug}.jpg",
                },
            )
            club.save()
            self.clubs[slug] = club
            club.demo_home_venue = venue

        self.competitions = {}
        today = timezone.localdate()
        for data in COMPETITIONS:
            competition, _ = Competition.objects.update_or_create(
                league=self.leagues[data["league_slug"]],
                slug=data["slug"],
                defaults={
                    "name": data["name"],
                    "season": data["season"],
                    "is_active": True,
                    "start_date": today,
                    "end_date": today.replace(year=today.year + 1),
                },
            )
            self.competitions[data["sport"]] = competition

        self.ensure_matches_and_standings()

    def ensure_matches_and_standings(self):
        now = timezone.now()
        clubs_by_sport = self.group_clubs_by_sport()

        for sport, clubs in clubs_by_sport.items():
            competition = self.competitions[sport]
            for index, club in enumerate(clubs, start=1):
                Standing.objects.update_or_create(
                    competition=competition,
                    club=club,
                    defaults={
                        "position": index,
                        "played": 5,
                        "won": max(0, 6 - index) if index <= 6 else 1,
                        "drawn": 1 if index % 4 == 0 else 0,
                        "lost": index % 3,
                        "goals_for": 80 - index * 2,
                        "goals_against": 40 + index,
                        "goal_difference": 40 - index * 3,
                        "points": max(1, 24 - index * 2),
                        "form": "WWDLW" if index <= 4 else "LDWLW",
                    },
                )

            pairings = list(zip(clubs[::2], clubs[1::2], strict=False))
            for index, (home, away) in enumerate(pairings, start=1):
                status = Match.Status.SCHEDULED
                match_date = now + timedelta(days=index * 3)
                home_score = None
                away_score = None

                if index == 1:
                    status = Match.Status.LIVE
                    match_date = now - timedelta(minutes=35)
                    home_score = 10
                    away_score = 7
                elif index in [2, 3]:
                    status = Match.Status.COMPLETED
                    match_date = now - timedelta(days=index)
                    home_score = 18 + index
                    away_score = 12 + index

                ref = f"DEMO-{sport}-GW{index:02d}-{home.slug}-vs-{away.slug}"
                match = Match.objects.filter(round=ref).first()
                if match is None:
                    match = Match(round=ref)

                match.competition = competition
                match.home_club = home
                match.away_club = away
                match.status = status
                match.match_date = match_date
                match.venue = getattr(home, "demo_home_venue", "League OS Demo Stadium")
                match.home_score = home_score
                match.away_score = away_score
                match.home_halftime_score = (
                    7 if status != Match.Status.SCHEDULED else None
                )
                match.away_halftime_score = (
                    3 if status != Match.Status.SCHEDULED else None
                )
                match.is_featured = index <= 2
                match.save()

    def group_clubs_by_sport(self):
        grouped = {RUGBY: [], FOOTBALL: [], BASKETBALL: []}
        for name, slug, short_name, sport, venue in CLUBS:
            grouped[sport].append(self.clubs[slug])
        return grouped

    def ensure_memberships(self):
        plan_templates = [
            ("Bronze Member", MembershipPlan.Tier.BASIC, Decimal("50000.00")),
            ("Gold Member", MembershipPlan.Tier.GOLD, Decimal("120000.00")),
            ("Platinum Member", MembershipPlan.Tier.PLATINUM, Decimal("250000.00")),
        ]
        benefits = [
            "Digital membership card",
            "Member ticket offers",
            "Priority club updates",
            "Fan rewards eligibility",
        ]

        self.membership_plans = {}
        for club in self.clubs.values():
            for name, tier, price in plan_templates:
                plan, _ = MembershipPlan.objects.update_or_create(
                    club=club,
                    name=f"{club.short_name if hasattr(club, 'short_name') and club.short_name else club.name} {name}",
                    defaults={
                        "description": f"Demo {name.lower()} plan for {club.name} fans.",
                        "tier": tier,
                        "billing_cycle": MembershipPlan.BillingCycle.ANNUAL,
                        "price_amount": price,
                        "currency": "UGX",
                        "benefits": benefits,
                        "is_active": True,
                        "is_visible": True,
                    },
                )
                self.membership_plans[(club.slug, tier)] = plan

        kobs_gold = self.membership_plans[("kobs", MembershipPlan.Tier.GOLD)]
        start = timezone.now() - timedelta(days=20)
        end = timezone.now() + timedelta(days=345)
        subscription, _ = MembershipSubscription.objects.update_or_create(
            user=self.main_user,
            plan=kobs_gold,
            status=MembershipSubscription.Status.ACTIVE,
            defaults={"club": self.clubs["kobs"], "starts_at": start, "ends_at": end},
        )
        MembershipCard.objects.update_or_create(
            subscription=subscription,
            defaults={
                "user": self.main_user,
                "club": self.clubs["kobs"],
                "card_number": "MEM-KOBS-DEMO-001",
                "qr_code_data": f"membership:{subscription.id}:{self.main_user.id}",
                "tier": MembershipPlan.Tier.GOLD,
                "billing_cycle": MembershipPlan.BillingCycle.ANNUAL,
                "valid_from": start,
                "valid_until": end,
                "status": MembershipCard.CardStatus.ACTIVE,
                "metadata": {"is_demo": True, "environment": self.environment},
            },
        )
        MembershipPayment.objects.update_or_create(
            transaction_reference="DEMO-MEMBERSHIP-KOBS-GOLD-001",
            defaults={
                "subscription": subscription,
                "subscription_plan": kobs_gold,
                "amount_paid": Decimal("120000.00"),
                "currency": "UGX",
                "payment_method": MembershipPayment.PaymentMethod.MANUAL,
                "provider": MembershipPayment.PaymentProvider.MANUAL,
                "provider_status": "confirmed-demo",
                "paid_at": timezone.now() - timedelta(days=19),
                "status": MembershipPayment.Status.CONFIRMED,
                "provider_response": {"is_demo": True, "environment": self.environment},
            },
        )

    def ensure_ticketing(self):
        self.ticket_types = []
        sale_start = timezone.now() - timedelta(days=7)
        sale_end = timezone.now() + timedelta(days=30)
        ticket_templates = [
            ("Regular", Decimal("20000.00"), 500),
            ("VIP Stand", Decimal("60000.00"), 120),
            ("Student", Decimal("10000.00"), 200),
        ]

        matches = Match.objects.filter(
            status__in=[Match.Status.SCHEDULED, Match.Status.LIVE]
        ).order_by("match_date")[:12]
        for match in matches:
            for name, price, quantity in ticket_templates:
                ticket_type, _ = TicketType.objects.update_or_create(
                    match=match,
                    name=name,
                    defaults={
                        "description": f"{name} demo ticket for {match.home_club.name} vs {match.away_club.name}.",
                        "price": price,
                        "currency": "UGX",
                        "quantity_available": quantity,
                        "quantity_sold": 25 if name == "Regular" else 5,
                        "sale_start_at": sale_start,
                        "sale_end_at": sale_end,
                        "status": TicketType.Status.ACTIVE,
                        "created_by": self.super_admin,
                    },
                )
                self.ticket_types.append(ticket_type)

        demo_ticket_types = []
        seen_match_ids = set()
        for ticket_type in self.ticket_types:
            if ticket_type.match_id in seen_match_ids:
                continue
            demo_ticket_types.append(ticket_type)
            seen_match_ids.add(ticket_type.match_id)
            if len(demo_ticket_types) == 3:
                break

        for index, ticket_type in enumerate(demo_ticket_types, start=1):
            reference = f"DEMO-TICKET-ORDER-{index:03d}"
            order = TicketOrder.objects.filter(payment_reference=reference).first()
            if order is None:
                order = TicketOrder(payment_reference=reference, buyer=self.main_user)
            order.total_amount = ticket_type.price
            order.currency = "UGX"
            order.status = TicketOrder.Status.PAID
            order.provider = TicketOrder.PaymentProvider.MANUAL
            order.provider_status = "confirmed-demo"
            order.paid_at = timezone.now() - timedelta(days=index)
            order.save()

            TicketOrderItem.objects.update_or_create(
                order=order,
                ticket_type=ticket_type,
                defaults={
                    "quantity": 1,
                    "unit_price": ticket_type.price,
                    "total_price": ticket_type.price,
                },
            )
            ticket, _ = Ticket.objects.get_or_create(
                order=order,
                ticket_type=ticket_type,
                match=ticket_type.match,
                owner=self.main_user,
                defaults={"status": Ticket.Status.ACTIVE},
            )
            if index == 3:
                ticket.status = Ticket.Status.USED
                ticket.used_at = timezone.now() - timedelta(hours=5)
                ticket.checked_in_by = self.ticketing_officer
                ticket.save()

    def ensure_fantasy(self):
        self.fantasy_competitions = {}
        for sport, competition in self.competitions.items():
            fantasy_competition, _ = FantasyCompetition.objects.update_or_create(
                slug=f"demo-{sport.lower()}-fantasy-2026",
                defaults={
                    "name": f"Demo {sport.title()} Fantasy 2026",
                    "linked_competition": competition,
                    "sport": sport,
                    "season": "2026",
                    "status": FantasyCompetition.Status.OPEN,
                    "budget": Decimal("100.00"),
                    "squad_size": 15 if sport != BASKETBALL else 10,
                    "lineup_size": (
                        15 if sport == RUGBY else 11 if sport == FOOTBALL else 5
                    ),
                    "max_players_per_club": 4,
                    "rules_summary": "Demo fantasy rules for League OS development and testing.",
                    "created_by": self.super_admin,
                },
            )
            self.fantasy_competitions[sport] = fantasy_competition
            self.ensure_gameweeks(fantasy_competition, sport)
            self.ensure_fantasy_players(fantasy_competition, sport)

        self.ensure_main_fantasy_team()

    def ensure_gameweeks(self, fantasy_competition, sport):
        now = timezone.now()
        matches = Match.objects.filter(competition=self.competitions[sport]).order_by(
            "match_date"
        )[:3]
        for number in range(1, 4):
            start_at = now + timedelta(days=(number - 1) * 7)
            gameweek, _ = FantasyGameweek.objects.update_or_create(
                fantasy_competition=fantasy_competition,
                number=number,
                defaults={
                    "name": f"Gameweek {number}",
                    "start_at": start_at,
                    "lock_at": start_at + timedelta(hours=1),
                    "end_at": start_at + timedelta(days=6),
                    "status": (
                        FantasyGameweek.Status.OPEN
                        if number == 1
                        else FantasyGameweek.Status.UPCOMING
                    ),
                },
            )
            gameweek.matches.set(matches)

    def ensure_fantasy_players(self, fantasy_competition, sport):
        clubs = self.group_clubs_by_sport()[sport]
        positions = POSITIONS_BY_SPORT[sport]
        count_per_club = PLAYERS_PER_CLUB[sport]
        for club_index, club in enumerate(clubs, start=1):
            for player_number in range(1, count_per_club + 1):
                first_name = FIRST_NAMES[
                    (player_number + club_index) % len(FIRST_NAMES)
                ]
                last_name = LAST_NAMES[
                    (player_number * 2 + club_index) % len(LAST_NAMES)
                ]
                display_name = f"{first_name} {last_name} {club.short_name if hasattr(club, 'short_name') and club.short_name else club_index}{player_number:02d}"
                position = positions[(player_number - 1) % len(positions)]
                price = Decimal("4.50") + Decimal(str((player_number % 9) * 0.5))
                FantasyPlayer.objects.update_or_create(
                    fantasy_competition=fantasy_competition,
                    club=club,
                    display_name=display_name,
                    defaults={
                        "position": position,
                        "calculated_price": price,
                        "final_price": price,
                        "price_source": FantasyPlayer.PriceSource.AUTO,
                        "previous_stats": {
                            "appearances": 5 + (player_number % 8),
                            "points": 20 + player_number,
                            "is_demo": True,
                        },
                        "current_form": Decimal(str(4 + (player_number % 6))),
                        "is_active": True,
                        "is_available": player_number % 13 != 0,
                        "availability_note": (
                            "Minor knock" if player_number % 13 == 0 else ""
                        ),
                    },
                )

    def ensure_main_fantasy_team(self):
        competition = self.fantasy_competitions[RUGBY]
        team, _ = FantasyTeam.objects.update_or_create(
            owner=self.main_user,
            fantasy_competition=competition,
            defaults={
                "name": "Keith's Demo XV",
                "total_points": Decimal("126.50"),
                "current_rank": 4,
            },
        )
        players = FantasyPlayer.objects.filter(
            fantasy_competition=competition
        ).order_by("final_price", "display_name")[:15]
        for player in players:
            FantasySquadPlayer.objects.update_or_create(
                fantasy_team=team,
                fantasy_player=player,
                defaults={"price_at_selection": player.final_price, "is_active": True},
            )
        gameweek = FantasyGameweek.objects.filter(
            fantasy_competition=competition, number=1
        ).first()
        if gameweek and players:
            lineup, _ = FantasyLineup.objects.update_or_create(
                fantasy_team=team,
                gameweek=gameweek,
                defaults={"captain": players[0], "vice_captain": players[1]},
            )
            for index, player in enumerate(players[:15], start=1):
                FantasyLineupPlayer.objects.update_or_create(
                    lineup=lineup,
                    fantasy_player=player,
                    defaults={"is_starter": True, "sort_order": index},
                )
                FantasyPlayerGameweekScore.objects.update_or_create(
                    fantasy_player=player,
                    gameweek=gameweek,
                    match=gameweek.matches.first(),
                    defaults={
                        "points": Decimal(str(3 + (index % 8))),
                        "breakdown": {"demo_minutes": 80, "demo_actions": index},
                        "status": "APPROVED",
                        "entered_by": self.super_admin,
                        "approved_by": self.super_admin,
                        "approved_at": timezone.now(),
                    },
                )
            FantasyTeamGameweekScore.objects.update_or_create(
                fantasy_team=team,
                gameweek=gameweek,
                defaults={
                    "points": Decimal("64.50"),
                    "rank": 4,
                    "breakdown": {"is_demo": True},
                },
            )
        league, _ = FantasyLeague.objects.update_or_create(
            join_code="LOSDEMO",
            defaults={
                "fantasy_competition": competition,
                "name": "League OS Demo Rugby League",
                "league_type": FantasyLeague.LeagueType.PUBLIC,
                "created_by": self.super_admin,
                "is_active": True,
            },
        )
        FantasyLeagueMembership.objects.get_or_create(
            fantasy_league=league, fantasy_team=team
        )

    def ensure_sponsors(self):
        if SponsorAccount is None:
            return
        for name, brn, category in SPONSORS:
            sponsor, _ = SponsorAccount.objects.update_or_create(
                registration_country="UG",
                brn=brn,
                defaults={
                    "owner": self.sponsor_owner,
                    "sponsor_type": SponsorAccount.SponsorType.CORPORATE,
                    "name": name,
                    "tin": f"TIN-{brn}",
                    "status": SponsorAccount.Status.APPROVED,
                },
            )
            SponsorAccountMember.objects.update_or_create(
                sponsor_account=sponsor,
                user=self.sponsor_owner,
                defaults={
                    "member_role": SponsorAccountMember.MemberRole.OWNER,
                    "is_active": True,
                },
            )
            package, _ = SponsorPackage.objects.update_or_create(
                name=f"{name} Matchday Sponsor Package",
                owner_type=SponsorshipOwnerType.CLUB,
                owner_identifier="kobs",
                scope_type=SponsorshipScopeType.MATCH,
                scope_identifier="demo-matchday",
                defaults={
                    "description": f"Demo sponsor placement package for {name}.",
                    "owner_name": "KCB KOBS",
                    "scope_name": "KCB KOBS Matchday",
                    "sponsor_type_allowed": SponsorPackage.SponsorTypeAllowed.CORPORATE,
                    "category": getattr(
                        SponsorCategory, category, SponsorCategory.GENERAL
                    ),
                    "price_amount": Decimal("2500000.00"),
                    "currency": "UGX",
                    "is_exclusive": False,
                    "requires_platform_fee": True,
                    "platform_fee_amount": Decimal("150000.00"),
                    "activation_rule": SponsorPackage.ActivationRule.AFTER_ADMIN_APPROVAL,
                    "status": SponsorPackage.Status.ACTIVE,
                    "created_by": self.super_admin,
                    "approved_by": self.super_admin,
                    "approved_at": timezone.now(),
                },
            )
            SponsorBenefit.objects.update_or_create(
                sponsor_package=package,
                benefit_type=SponsorBenefit.BenefitType.FAN_DASHBOARD_AD,
                name="Fan dashboard advert placement",
                defaults={
                    "description": "Demo sponsor spotlight placement shown on the fan dashboard.",
                    "quantity": 1,
                    "value_amount": Decimal("500000.00"),
                    "requires_payment_confirmation": True,
                    "is_platform_controlled": True,
                },
            )

    def ensure_keith_activity(self):
        for club_slug in ["kobs", "heathens-rfc", "black-pirates"]:
            Follow.objects.update_or_create(
                user=self.main_user,
                content_type=Follow.ContentType.CLUB,
                object_id=self.clubs[club_slug].id,
            )

        payments = [
            (
                "DEMO-PAYMENT-MEMBERSHIP-001",
                PaymentHistory.PaymentType.MEMBERSHIP_FEE,
                Decimal("120000.00"),
                "KCB KOBS Gold Membership",
            ),
            (
                "DEMO-PAYMENT-TICKET-001",
                PaymentHistory.PaymentType.TICKET_PURCHASE,
                Decimal("20000.00"),
                "Regular ticket purchase",
            ),
            (
                "DEMO-PAYMENT-TICKET-002",
                PaymentHistory.PaymentType.TICKET_PURCHASE,
                Decimal("60000.00"),
                "VIP ticket purchase",
            ),
            (
                "DEMO-PAYMENT-SPONSOR-001",
                PaymentHistory.PaymentType.SPONSORSHIP,
                Decimal("250000.00"),
                "Pending sponsorship contribution",
            ),
        ]
        for reference, payment_type, amount, description in payments:
            PaymentHistory.objects.update_or_create(
                reference=reference,
                defaults={
                    "user": self.main_user,
                    "payment_type": payment_type,
                    "amount": amount,
                    "currency": "UGX",
                    "status": (
                        PaymentHistory.PaymentStatus.PENDING
                        if "SPONSOR" in reference
                        else PaymentHistory.PaymentStatus.COMPLETED
                    ),
                    "description": description,
                    "metadata": {"is_demo": True, "environment": self.environment},
                },
            )

        notifications = [
            (
                "MATCH_REMINDER",
                "MATCH",
                "KCB KOBS matchday reminder",
                "KCB KOBS vs Heathens kicks off soon.",
            ),
            (
                "TICKET_UPDATES",
                "TICKET",
                "Your ticket is ready",
                "Your demo ticket QR code is active.",
            ),
            (
                "MEMBERSHIP_UPDATES",
                "MEMBERSHIP",
                "Membership activated",
                "Your KCB KOBS Gold Membership is active.",
            ),
            (
                "FANTASY_UPDATES",
                "FANTASY",
                "Fantasy gameweek open",
                "Submit your Demo XV lineup before lock time.",
            ),
            (
                "LEAGUE_NEWS",
                "CLUB",
                "Demo news available",
                "New seeded news and match stories are ready for testing.",
            ),
        ]
        for event_type, category, title, message in notifications:
            Notification.objects.update_or_create(
                user=self.main_user,
                title=title,
                defaults={
                    "event_type": event_type,
                    "category": category,
                    "priority": Notification.Priority.NORMAL,
                    "message": message,
                    "action_url": "/dashboard/fan",
                    "metadata": {"is_demo": True, "environment": self.environment},
                    "is_read": False,
                },
            )
            NotificationPreference.objects.update_or_create(
                user=self.main_user,
                event_type=event_type,
                defaults={
                    "email_enabled": True,
                    "push_enabled": True,
                    "sms_enabled": False,
                },
            )

    def print_summary(self):
        counts = {
            "clubs": Club.objects.count(),
            "matches": Match.objects.count(),
            "membership_plans": MembershipPlan.objects.count(),
            "ticket_types": TicketType.objects.count(),
            "fantasy_players": FantasyPlayer.objects.count(),
            "fantasy_teams": FantasyTeam.objects.count(),
            "tickets": Ticket.objects.count(),
            "notifications": Notification.objects.filter(user=self.main_user).count(),
        }
        for label, value in counts.items():
            self.stdout.write(f"{label}: {value}")
