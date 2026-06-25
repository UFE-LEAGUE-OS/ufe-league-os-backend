from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Club, User
from dashboards.models import Competition, League, Match, Union

from .models import Ticket, TicketOrder, TicketType, TicketValidationLog
from .services.orders import (
    create_ticket_order,
    expire_stale_ticket_reservations,
)


class TicketingTestMixin:
    def setUp(self):
        self.user = User.objects.create_user(
            email="fan@example.com",
            password="StrongPass123!",
            first_name="Test",
            last_name="Fan",
            role=User.Role.FAN,
        )

        self.other_user = User.objects.create_user(
            email="otherfan@example.com",
            password="StrongPass123!",
            first_name="Other",
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

        self.super_admin = User.objects.create_user(
            email="superadmin@example.com",
            password="StrongPass123!",
            first_name="Super",
            last_name="Admin",
            role=User.Role.SUPER_ADMIN,
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
            match_date=timezone.now() + timedelta(days=7),
            venue="Legends Rugby Grounds",
            status=Match.Status.SCHEDULED,
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
            provider=TicketOrder.PaymentProvider.FLUTTERWAVE,
            payment_reference="TICKET-ORDER-001",
            reservation_released_at=timezone.now(),
        )


@override_settings(TICKET_RESERVATION_MINUTES=10)
class TicketingModelTests(TicketingTestMixin, APITestCase):
    def test_ticket_type_remaining_quantity(self):
        self.assertEqual(self.ticket_type.remaining_quantity, 100)
        self.assertEqual(self.ticket_type.active_reserved_quantity, 0)
        self.assertFalse(self.ticket_type.is_sold_out)

    def test_ticket_type_is_sold_out_when_quantity_is_exhausted(self):
        self.ticket_type.quantity_sold = 100
        self.ticket_type.save(update_fields=["quantity_sold"])

        self.assertEqual(self.ticket_type.remaining_quantity, 0)
        self.assertTrue(self.ticket_type.is_sold_out)

    def test_create_ticket_order_creates_pending_order_item_and_reservation(self):
        order = create_ticket_order(
            buyer=self.user,
            ticket_type=self.ticket_type,
            quantity=2,
        )

        self.assertEqual(order.status, TicketOrder.Status.PENDING)
        self.assertEqual(order.total_amount, Decimal("20000.00"))
        self.assertIsNotNone(order.reservation_expires_at)
        self.assertIsNone(order.reservation_released_at)
        self.assertTrue(order.is_reservation_active)
        self.assertFalse(order.is_reservation_expired)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().quantity, 2)
        self.assertEqual(Ticket.objects.filter(order=order).count(), 0)

    def test_active_reservation_reduces_remaining_ticket_quantity(self):
        create_ticket_order(
            buyer=self.user,
            ticket_type=self.ticket_type,
            quantity=2,
        )

        self.ticket_type.refresh_from_db()

        self.assertEqual(self.ticket_type.active_reserved_quantity, 2)
        self.assertEqual(self.ticket_type.remaining_quantity, 98)

    def test_expired_reservation_does_not_reduce_remaining_ticket_quantity(self):
        order = create_ticket_order(
            buyer=self.user,
            ticket_type=self.ticket_type,
            quantity=2,
        )
        order.reservation_expires_at = timezone.now() - timedelta(minutes=1)
        order.save(update_fields=["reservation_expires_at"])

        self.ticket_type.refresh_from_db()

        self.assertEqual(self.ticket_type.active_reserved_quantity, 0)
        self.assertEqual(self.ticket_type.remaining_quantity, 100)
        self.assertTrue(order.is_reservation_expired)

    def test_expire_stale_ticket_reservations_cancels_expired_pending_order(self):
        order = create_ticket_order(
            buyer=self.user,
            ticket_type=self.ticket_type,
            quantity=2,
        )
        order.reservation_expires_at = timezone.now() - timedelta(minutes=1)
        order.save(update_fields=["reservation_expires_at"])

        expired_count = expire_stale_ticket_reservations()

        order.refresh_from_db()
        self.ticket_type.refresh_from_db()

        self.assertEqual(expired_count, 1)
        self.assertEqual(order.status, TicketOrder.Status.CANCELLED)
        self.assertIsNotNone(order.reservation_released_at)
        self.assertEqual(self.ticket_type.remaining_quantity, 100)

    def test_ticket_has_qr_payload(self):
        ticket = Ticket.objects.create(
            order=self.order,
            ticket_type=self.ticket_type,
            match=self.match,
            owner=self.user,
        )

        self.assertEqual(ticket.qr_payload, str(ticket.ticket_code))


@override_settings(
    FLUTTERWAVE_SECRET_KEY="FLWSECK_TEST-test-key",
    FLUTTERWAVE_SECRET_HASH="test-webhook-secret",
    FLUTTERWAVE_TICKET_REDIRECT_URL=(
        "http://localhost:8000/api/ticketing/flutterwave/verify/"
    ),
    FLUTTERWAVE_TICKET_PAYMENT_TITLE="League OS Match Ticket Payment",
    TICKET_RESERVATION_MINUTES=10,
)
class TicketingAPITests(TicketingTestMixin, APITestCase):
    def flutterwave_initialize_response(self):
        return {
            "status": "success",
            "message": "Hosted Link",
            "data": {
                "link": "https://checkout.flutterwave.com/test-ticket-checkout",
            },
        }

    def flutterwave_verify_response(self, tx_ref, amount="20000.00"):
        return {
            "status": "success",
            "message": "Transaction fetched successfully",
            "data": {
                "id": 123456789,
                "status": "successful",
                "tx_ref": tx_ref,
                "amount": amount,
                "currency": "UGX",
                "flw_ref": "FLW-MOCK-001",
            },
        }

    def test_public_match_ticket_types_endpoint_lists_ticket_types(self):
        response = self.client.get(
            f"/api/ticketing/matches/{self.match.id}/ticket-types/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["ticket_types"][0]["name"], "Ordinary")
        self.assertEqual(response.data["ticket_types"][0]["remaining_quantity"], 100)
        self.assertEqual(
            response.data["ticket_types"][0]["active_reserved_quantity"],
            0,
        )

    def test_public_match_ticket_types_endpoint_shows_reserved_quantity(self):
        create_ticket_order(
            buyer=self.user,
            ticket_type=self.ticket_type,
            quantity=2,
        )

        response = self.client.get(
            f"/api/ticketing/matches/{self.match.id}/ticket-types/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["ticket_types"][0]["active_reserved_quantity"],
            2,
        )
        self.assertEqual(response.data["ticket_types"][0]["remaining_quantity"], 98)

    def test_anonymous_user_cannot_initialize_checkout(self):
        response = self.client.post(
            "/api/ticketing/orders/flutterwave/initialize/",
            {
                "ticket_type_id": self.ticket_type.id,
                "quantity": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    @patch("ticketing.views.initialize_ticket_flutterwave_payment")
    def test_initialize_flutterwave_ticket_checkout_creates_pending_order(
        self,
        mock_initialize,
    ):
        mock_initialize.return_value = self.flutterwave_initialize_response()
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/ticketing/orders/flutterwave/initialize/",
            {
                "ticket_type_id": self.ticket_type.id,
                "quantity": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["checkout_url"],
            mock_initialize.return_value["data"]["link"],
        )
        self.assertTrue(response.data["tx_ref"].startswith("LOS-TICKET-"))

        order = TicketOrder.objects.get(id=response.data["order"]["id"])

        self.assertEqual(order.status, TicketOrder.Status.PENDING)
        self.assertEqual(order.total_amount, Decimal("20000.00"))
        self.assertEqual(order.provider, TicketOrder.PaymentProvider.FLUTTERWAVE)
        self.assertIsNotNone(order.reservation_expires_at)
        self.assertIsNone(order.reservation_released_at)
        self.assertTrue(order.is_reservation_active)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().quantity, 2)
        self.assertEqual(Ticket.objects.filter(order=order).count(), 0)

    def test_initialize_rejects_quantity_above_remaining_stock(self):
        self.ticket_type.quantity_available = 1
        self.ticket_type.save(update_fields=["quantity_available"])
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/ticketing/orders/flutterwave/initialize/",
            {
                "ticket_type_id": self.ticket_type.id,
                "quantity": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("quantity", response.data)

    def test_initialize_rejects_quantity_reserved_by_other_pending_order(self):
        create_ticket_order(
            buyer=self.other_user,
            ticket_type=self.ticket_type,
            quantity=100,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/ticketing/orders/flutterwave/initialize/",
            {
                "ticket_type_id": self.ticket_type.id,
                "quantity": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("quantity", response.data)

    @patch("ticketing.views.verify_flutterwave_transaction")
    def test_verify_flutterwave_payment_issues_tickets_and_updates_stock(
        self,
        mock_verify,
    ):
        pending_order = create_ticket_order(
            buyer=self.user,
            ticket_type=self.ticket_type,
            quantity=2,
        )
        mock_verify.return_value = self.flutterwave_verify_response(
            pending_order.payment_reference
        )

        response = self.client.get(
            "/api/ticketing/flutterwave/verify/",
            {"tx_ref": pending_order.payment_reference},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["tickets"]), 2)

        pending_order.refresh_from_db()
        self.ticket_type.refresh_from_db()

        self.assertEqual(pending_order.status, TicketOrder.Status.PAID)
        self.assertIsNotNone(pending_order.paid_at)
        self.assertIsNotNone(pending_order.reservation_released_at)
        self.assertEqual(self.ticket_type.quantity_sold, 2)
        self.assertEqual(self.ticket_type.active_reserved_quantity, 0)
        self.assertEqual(self.ticket_type.remaining_quantity, 98)
        self.assertEqual(Ticket.objects.filter(order=pending_order).count(), 2)

    @patch("ticketing.views.verify_flutterwave_transaction")
    def test_verify_is_idempotent_for_already_paid_order(self, mock_verify):
        paid_order = create_ticket_order(
            buyer=self.user,
            ticket_type=self.ticket_type,
            quantity=1,
        )
        mock_verify.return_value = self.flutterwave_verify_response(
            paid_order.payment_reference,
            amount="10000.00",
        )

        first_response = self.client.get(
            "/api/ticketing/flutterwave/verify/",
            {"tx_ref": paid_order.payment_reference},
        )
        second_response = self.client.get(
            "/api/ticketing/flutterwave/verify/",
            {"tx_ref": paid_order.payment_reference},
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(Ticket.objects.filter(order=paid_order).count(), 1)

    @patch("ticketing.views.verify_flutterwave_transaction")
    def test_expired_reservation_cannot_be_confirmed(self, mock_verify):
        pending_order = create_ticket_order(
            buyer=self.user,
            ticket_type=self.ticket_type,
            quantity=1,
        )
        pending_order.reservation_expires_at = timezone.now() - timedelta(minutes=1)
        pending_order.save(update_fields=["reservation_expires_at"])

        mock_verify.return_value = self.flutterwave_verify_response(
            pending_order.payment_reference,
            amount="10000.00",
        )

        response = self.client.get(
            "/api/ticketing/flutterwave/verify/",
            {"tx_ref": pending_order.payment_reference},
        )

        self.assertEqual(response.status_code, 400)

        pending_order.refresh_from_db()
        self.ticket_type.refresh_from_db()

        self.assertEqual(pending_order.status, TicketOrder.Status.CANCELLED)
        self.assertIsNotNone(pending_order.reservation_released_at)
        self.assertEqual(Ticket.objects.filter(order=pending_order).count(), 0)
        self.assertEqual(self.ticket_type.remaining_quantity, 100)

    @patch("ticketing.views.verify_flutterwave_transaction")
    def test_failed_flutterwave_verification_does_not_issue_tickets(self, mock_verify):
        pending_order = create_ticket_order(
            buyer=self.user,
            ticket_type=self.ticket_type,
            quantity=1,
        )
        mock_verify.return_value = {
            "status": "success",
            "data": {
                "id": 999,
                "status": "failed",
                "tx_ref": pending_order.payment_reference,
                "amount": "10000.00",
                "currency": "UGX",
            },
        }

        response = self.client.get(
            "/api/ticketing/flutterwave/verify/",
            {"tx_ref": pending_order.payment_reference},
        )

        self.assertEqual(response.status_code, 400)
        pending_order.refresh_from_db()
        self.ticket_type.refresh_from_db()

        self.assertEqual(pending_order.status, TicketOrder.Status.FAILED)
        self.assertIsNotNone(pending_order.reservation_released_at)
        self.assertEqual(Ticket.objects.filter(order=pending_order).count(), 0)
        self.assertEqual(self.ticket_type.remaining_quantity, 100)

    def test_my_tickets_endpoint_returns_owned_tickets_only(self):
        ticket = Ticket.objects.create(
            order=self.order,
            ticket_type=self.ticket_type,
            match=self.match,
            owner=self.user,
        )
        other_order = TicketOrder.objects.create(
            buyer=self.other_user,
            total_amount=Decimal("10000.00"),
            currency="UGX",
            status=TicketOrder.Status.PAID,
            provider=TicketOrder.PaymentProvider.FLUTTERWAVE,
            payment_reference="OTHER-TICKET-ORDER-001",
            reservation_released_at=timezone.now(),
        )
        Ticket.objects.create(
            order=other_order,
            ticket_type=self.ticket_type,
            match=self.match,
            owner=self.other_user,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/ticketing/tickets/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["tickets"][0]["ticket_code"],
            str(ticket.ticket_code),
        )

    def test_ticketing_officer_can_validate_ticket_once(self):
        ticket = Ticket.objects.create(
            order=self.order,
            ticket_type=self.ticket_type,
            match=self.match,
            owner=self.user,
        )
        self.client.force_authenticate(user=self.ticketing_officer)

        response = self.client.post(
            "/api/ticketing/validate/",
            {
                "scanned_code": str(ticket.ticket_code),
                "match_id": self.match.id,
            },
            format="json",
        )
        second_response = self.client.post(
            "/api/ticketing/validate/",
            {
                "scanned_code": str(ticket.ticket_code),
                "match_id": self.match.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], TicketValidationLog.Result.VALID)
        self.assertEqual(second_response.status_code, 400)
        self.assertEqual(
            second_response.data["result"],
            TicketValidationLog.Result.ALREADY_USED,
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.USED)
        self.assertEqual(ticket.checked_in_by, self.ticketing_officer)

    def test_fan_cannot_validate_ticket(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/ticketing/validate/",
            {
                "scanned_code": "not-a-ticket",
                "match_id": self.match.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_super_admin_can_expire_stale_reservations_from_endpoint(self):
        order = create_ticket_order(
            buyer=self.user,
            ticket_type=self.ticket_type,
            quantity=2,
        )
        order.reservation_expires_at = timezone.now() - timedelta(minutes=1)
        order.save(update_fields=["reservation_expires_at"])

        self.client.force_authenticate(user=self.super_admin)

        response = self.client.post(
            "/api/ticketing/reservations/expire/",
            {"dry_run": False},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["expired_count"], 1)

        order.refresh_from_db()
        self.assertEqual(order.status, TicketOrder.Status.CANCELLED)
        self.assertIsNotNone(order.reservation_released_at)

    def test_fan_cannot_expire_stale_reservations_from_endpoint(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/ticketing/reservations/expire/",
            {"dry_run": True},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_expire_ticket_reservations_management_command_dry_run(self):
        order = create_ticket_order(
            buyer=self.user,
            ticket_type=self.ticket_type,
            quantity=2,
        )
        order.reservation_expires_at = timezone.now() - timedelta(minutes=1)
        order.save(update_fields=["reservation_expires_at"])

        call_command("expire_ticket_reservations", "--dry-run")

        order.refresh_from_db()
        self.assertEqual(order.status, TicketOrder.Status.PENDING)
        self.assertIsNone(order.reservation_released_at)

    def test_expire_ticket_reservations_management_command(self):
        order = create_ticket_order(
            buyer=self.user,
            ticket_type=self.ticket_type,
            quantity=2,
        )
        order.reservation_expires_at = timezone.now() - timedelta(minutes=1)
        order.save(update_fields=["reservation_expires_at"])

        call_command("expire_ticket_reservations")

        order.refresh_from_db()
        self.assertEqual(order.status, TicketOrder.Status.CANCELLED)
        self.assertIsNotNone(order.reservation_released_at)
