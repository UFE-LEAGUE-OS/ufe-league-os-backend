from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from accounts.models import Club, User
from dashboards.models import Competition, League, Match, Union
from ticketing.models import TicketType

DEMO_MATCHES = {
    1: {
        "sport": "Football",
        "union_slug": "fufa-presentation-demo",
        "union_name": "FUFA Presentation Demo",
        "league_slug": "uganda-premier-league-presentation-demo",
        "league_name": "Uganda Premier League Presentation Demo",
        "competition_slug": "upl-2026-presentation-demo",
        "competition_name": "Uganda Premier League 2026 Presentation Demo",
        "season": "2026",
        "home_slug": "kcca-fc-presentation-demo",
        "home_name": "KCCA FC",
        "away_slug": "vipers-sc-presentation-demo",
        "away_name": "Vipers SC",
        "venue": "MTN Omondi Stadium, Lugogo",
        "ordinary_price": "15000.00",
        "vip_price": "50000.00",
    },
    2: {
        "sport": "Football",
        "union_slug": "fufa-presentation-demo",
        "union_name": "FUFA Presentation Demo",
        "league_slug": "uganda-premier-league-presentation-demo",
        "league_name": "Uganda Premier League Presentation Demo",
        "competition_slug": "upl-2026-presentation-demo",
        "competition_name": "Uganda Premier League 2026 Presentation Demo",
        "season": "2026",
        "home_slug": "sc-villa-presentation-demo",
        "home_name": "SC Villa",
        "away_slug": "express-fc-presentation-demo",
        "away_name": "Express FC",
        "venue": "Mandela National Stadium, Namboole",
        "ordinary_price": "15000.00",
        "vip_price": "50000.00",
    },
    3: {
        "sport": "Rugby",
        "union_slug": "uganda-rugby-union-presentation-demo",
        "union_name": "Uganda Rugby Union Presentation Demo",
        "league_slug": "nile-special-rugby-premiership-presentation-demo",
        "league_name": "Nile Special Rugby Premiership Presentation Demo",
        "competition_slug": "nile-special-rugby-2026-presentation-demo",
        "competition_name": "Nile Special Rugby Premiership 2026 Presentation Demo",
        "season": "2026",
        "home_slug": "betway-kobs-presentation-demo",
        "home_name": "Betway KOBS",
        "away_slug": "stanbic-pirates-presentation-demo",
        "away_name": "Stanbic Pirates",
        "venue": "Kyadondo Rugby Club",
        "ordinary_price": "10000.00",
        "vip_price": "50000.00",
    },
}


def demo_checkout_is_enabled():
    return (
        getattr(settings, "TICKETING_DEMO_CHECKOUT_ENABLED", False)
        and getattr(settings, "FLUTTERWAVE_MODE", "test") == "test"
    )


def ensure_presentation_demo_ticketing_match(frontend_match_id):
    """
    Creates real backend demo data for frontend dummy ticket cards.

    This is for staging/presentation only. It lets the current frontend dummy
    cards reach a real Flutterwave test checkout without manually running a seed
    command first.
    """

    demo = DEMO_MATCHES.get(int(frontend_match_id), DEMO_MATCHES[3])

    ticketing_officer, _ = User.objects.get_or_create(
        email="ticketing-demo@example.com",
        defaults={
            "first_name": "Ticketing",
            "last_name": "Demo",
            "role": User.Role.TICKETING_OFFICER,
            "is_email_verified": True,
        },
    )
    ticketing_officer.set_password("StrongPass123!")
    ticketing_officer.save()

    fan, _ = User.objects.get_or_create(
        email="fan-demo@example.com",
        defaults={
            "first_name": "Fan",
            "last_name": "Demo",
            "role": User.Role.FAN,
            "is_email_verified": True,
        },
    )
    fan.set_password("StrongPass123!")
    fan.save()

    union, _ = Union.objects.get_or_create(
        slug=demo["union_slug"],
        defaults={
            "name": demo["union_name"],
            "country": "Uganda",
        },
    )

    league, _ = League.objects.get_or_create(
        slug=demo["league_slug"],
        defaults={
            "union": union,
            "name": demo["league_name"],
        },
    )

    competition, _ = Competition.objects.get_or_create(
        league=league,
        slug=demo["competition_slug"],
        defaults={
            "name": demo["competition_name"],
            "season": demo["season"],
        },
    )

    home_club, _ = Club.objects.get_or_create(
        slug=demo["home_slug"],
        defaults={"name": demo["home_name"]},
    )

    away_club, _ = Club.objects.get_or_create(
        slug=demo["away_slug"],
        defaults={"name": demo["away_name"]},
    )

    match = Match.objects.filter(
        competition=competition,
        home_club=home_club,
        away_club=away_club,
    ).first()

    if match is None:
        match = Match.objects.create(
            competition=competition,
            home_club=home_club,
            away_club=away_club,
            match_date=timezone.now() + timedelta(days=7),
            venue=demo["venue"],
            status=Match.Status.SCHEDULED,
        )

    ordinary, _ = TicketType.objects.get_or_create(
        match=match,
        name="Ordinary",
        defaults={
            "description": "Ordinary match access ticket.",
            "price": Decimal(demo["ordinary_price"]),
            "currency": "UGX",
            "quantity_available": 100,
            "quantity_sold": 0,
            "status": TicketType.Status.ACTIVE,
            "created_by": ticketing_officer,
        },
    )

    vip, _ = TicketType.objects.get_or_create(
        match=match,
        name="VIP",
        defaults={
            "description": "VIP match access ticket.",
            "price": Decimal(demo["vip_price"]),
            "currency": "UGX",
            "quantity_available": 25,
            "quantity_sold": 0,
            "status": TicketType.Status.ACTIVE,
            "created_by": ticketing_officer,
        },
    )

    for ticket_type in (ordinary, vip):
        if ticket_type.status != TicketType.Status.ACTIVE:
            ticket_type.status = TicketType.Status.ACTIVE
            ticket_type.save(update_fields=["status", "updated_at"])

    return match
