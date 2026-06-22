from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import Club, User
from dashboards.models import Competition, League, Match, Union

from .models import Ticket, TicketOrder, TicketType, TicketValidationLog


class TicketingModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="fan@example.com",
            password="StrongPass123!",
            first_name="Test",
            last_name="Fan",
            role=User.Role.FAN,
        )

        self.ticketing_officer = User.objects.create_user(
            email="ticketing@example.com",
            password="StrongPass123!",
            first_name="Ticketing",
            last_name="Officer",
            role=User.Role.TICKETING_OFFICER,
        )

        self.union = Union.objects.create(
            name="Uganda Rugby Union",
            slug="uganda-rugby-union",
            country="Uganda",
        )

        self.league = League.objects.create(
            union=self.union,
            name="Nile Special Rugby League",
            slug="nile-special-rugby-league",
        )

        self.competition = Competition.objects.create(
            league=self.league,
            name="Nile Special Rugby League 2026",
            slug="nile-special-rugby-league-2026",
            season="2026",
        )

        self.home_club = Club.objects.create(
            name="KOBS Rugby Club",
            slug="kobs-rugby-club",
        )

        self.away_club = Club.objects.create(
            name="Heathens Rugby Club",
            slug="heathens-rugby-club",
        )

        self.match = Match.objects.create(
            competition=self.competition,
            home_club=self.home_club,
            away_club=self.away_club,
            match_date=timezone.now(),
            venue="Legends Rugby Grounds",
        )

        self.ticket_type = TicketType.objects.create(
            match=self.match,
            name="Ordinary",
            description="Ordinary match access ticket.",
            price=Decimal("10000.00"),
            currency="UGX",
            quantity_available=100,
            quantity_sold=0,
            status=TicketType.Status.ACTIVE,
            created_by=self.ticketing_officer,
        )

        self.order = TicketOrder.objects.create(
            buyer=self.user,
            total_amount=Decimal("10000.00"),
            currency="UGX",
            status=TicketOrder.Status.PAID,
            payment_reference="TICKET-ORDER-001",
        )

    def test_ticket_type_remaining_quantity(self):
        self.assertEqual(self.ticket_type.remaining_quantity, 100)
        self.assertFalse(self.ticket_type.is_sold_out)

    def test_ticket_type_is_sold_out_when_quantity_is_exhausted(self):
        self.ticket_type.quantity_sold = 100
        self.ticket_type.save(update_fields=["quantity_sold"])

        self.assertEqual(self.ticket_type.remaining_quantity, 0)
        self.assertTrue(self.ticket_type.is_sold_out)

    def test_ticket_has_qr_payload(self):
        ticket = Ticket.objects.create(
            order=self.order,
            ticket_type=self.ticket_type,
            match=self.match,
            owner=self.user,
        )

        self.assertEqual(ticket.qr_payload, str(ticket.ticket_code))

    def test_ticket_validation_log_records_scan_result(self):
        ticket = Ticket.objects.create(
            order=self.order,
            ticket_type=self.ticket_type,
            match=self.match,
            owner=self.user,
        )

        log = TicketValidationLog.objects.create(
            ticket=ticket,
            match=self.match,
            scanned_by=self.ticketing_officer,
            scanned_code=str(ticket.ticket_code),
            result=TicketValidationLog.Result.VALID,
            message="Ticket is valid.",
        )

        self.assertEqual(log.result, TicketValidationLog.Result.VALID)
        self.assertEqual(log.ticket, ticket)
        self.assertEqual(log.match, self.match)
        self.assertEqual(log.scanned_by, self.ticketing_officer)
