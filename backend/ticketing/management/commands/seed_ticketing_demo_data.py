from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Club, User
from dashboards.models import Competition, League, Match, Union
from ticketing.models import TicketType


class Command(BaseCommand):
    help = "Create demo ticketing data for frontend and QA testing."

    def handle(self, *args, **options):
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
            slug="uganda-rugby-union-demo",
            defaults={
                "name": "Uganda Rugby Union Demo",
                "country": "Uganda",
            },
        )

        league, _ = League.objects.get_or_create(
            slug="nile-special-rugby-league-demo",
            defaults={
                "union": union,
                "name": "Nile Special Rugby League Demo",
            },
        )

        competition, _ = Competition.objects.get_or_create(
            slug="nile-special-rugby-league-2026-demo",
            defaults={
                "league": league,
                "name": "Nile Special Rugby League 2026 Demo",
                "season": "2026",
            },
        )

        home_club, _ = Club.objects.get_or_create(
            slug="kobs-rugby-club-demo",
            defaults={"name": "KOBS Rugby Club Demo"},
        )

        away_club, _ = Club.objects.get_or_create(
            slug="heathens-rugby-club-demo",
            defaults={"name": "Heathens Rugby Club Demo"},
        )

        match, _ = Match.objects.get_or_create(
            competition=competition,
            home_club=home_club,
            away_club=away_club,
            defaults={
                "match_date": timezone.now() + timedelta(days=7),
                "venue": "Legends Rugby Grounds",
                "status": Match.Status.SCHEDULED,
            },
        )

        ordinary, _ = TicketType.objects.get_or_create(
            match=match,
            name="Ordinary",
            defaults={
                "description": "Ordinary match access ticket.",
                "price": Decimal("10000.00"),
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
                "price": Decimal("50000.00"),
                "currency": "UGX",
                "quantity_available": 25,
                "quantity_sold": 0,
                "status": TicketType.Status.ACTIVE,
                "created_by": ticketing_officer,
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo ticketing data created."))

        self.stdout.write("")
        self.stdout.write("Demo fan login:")
        self.stdout.write("  email: fan-demo@example.com")
        self.stdout.write("  password: StrongPass123!")

        self.stdout.write("")
        self.stdout.write("Demo ticketing officer login:")
        self.stdout.write("  email: ticketing-demo@example.com")
        self.stdout.write("  password: StrongPass123!")

        self.stdout.write("")
        self.stdout.write("Demo match:")
        self.stdout.write(f"  id: {match.id}")
        self.stdout.write(f"  label: {match}")

        self.stdout.write("")
        self.stdout.write("Demo ticket types:")
        self.stdout.write(f"  Ordinary id: {ordinary.id}")
        self.stdout.write(f"  VIP id: {vip.id}")
