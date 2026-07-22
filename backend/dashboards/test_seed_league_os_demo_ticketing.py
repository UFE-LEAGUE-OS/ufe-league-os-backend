from decimal import Decimal
from io import StringIO

from django.test import TestCase
from django.utils import timezone

from accounts.models import Club, User
from dashboards.management.commands.seed_league_os_demo import (
    Command,
)
from dashboards.models import (
    Competition,
    League,
    Match,
    Union,
)
from ticketing.models import TicketOrder, TicketType


class SeedLeagueOsDemoTicketingTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            email="ticket-buyer@leagueos.test",
            password="StrongPass123!",
            role=User.Role.FAN,
        )
        self.officer = User.objects.create_user(
            email="ticket-officer@leagueos.test",
            password="StrongPass123!",
            role=User.Role.TICKETING_OFFICER,
        )

        union = Union.objects.create(
            name="Ticket Seed Union",
            slug="ticket-seed-union",
        )
        league = League.objects.create(
            union=union,
            name="Ticket Seed League",
            slug="ticket-seed-league",
        )
        competition = Competition.objects.create(
            league=league,
            name="Ticket Seed Competition",
            slug="ticket-seed-competition",
            season="2026",
        )
        home_club = Club.objects.create(
            name="Ticket Seed Home",
            slug="ticket-seed-home",
            sport=Club.Sport.RUGBY,
        )
        away_club = Club.objects.create(
            name="Ticket Seed Away",
            slug="ticket-seed-away",
            sport=Club.Sport.RUGBY,
        )
        match = Match.objects.create(
            competition=competition,
            home_club=home_club,
            away_club=away_club,
            match_date=timezone.now(),
        )

        self.regular = TicketType.objects.create(
            match=match,
            name="Regular",
            price=Decimal("20000.00"),
            quantity_available=100,
            status=TicketType.Status.ACTIVE,
            created_by=self.officer,
        )
        self.vip = TicketType.objects.create(
            match=match,
            name="VIP",
            price=Decimal("60000.00"),
            quantity_available=50,
            status=TicketType.Status.ACTIVE,
            created_by=self.officer,
        )

    def test_demo_order_replaces_stale_item_and_ticket(self):
        command = Command(
            stdout=StringIO(),
        )
        command.main_user = self.buyer
        command.ticketing_officer = self.officer

        command.upsert_demo_ticket_order(
            reference="DEMO-TICKET-ORDER-001",
            ticket_type=self.regular,
            index=1,
        )
        command.upsert_demo_ticket_order(
            reference="DEMO-TICKET-ORDER-001",
            ticket_type=self.vip,
            index=1,
        )

        order = TicketOrder.objects.get(payment_reference="DEMO-TICKET-ORDER-001")

        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.tickets.count(), 1)
        self.assertEqual(
            order.items.get().ticket_type,
            self.vip,
        )
        self.assertEqual(
            order.tickets.get().ticket_type,
            self.vip,
        )
        self.assertEqual(
            order.tickets.get().match,
            self.vip.match,
        )
