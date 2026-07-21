"""
Unit tests for the finances app.
"""

from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Club
from memberships.models import (
    MembershipPayment,
    MembershipPlan,
    MembershipSubscription,
)
from ticketing.models import TicketOrder, TicketOrderItem, TicketType
from dashboards.models import Match, Competition, League, Union

from .models import Invoice, Receipt, FinanceAuditLog
from .services import (
    log_finance_action,
    get_financial_summary,
)

User = get_user_model()


def _get_results(response):
    """Extract results from response data, whether paginated or not."""
    if isinstance(response.data, dict) and "results" in response.data:
        return response.data["results"]
    if isinstance(response.data, list):
        return response.data
    return []


class BaseFinanceTest(TestCase):
    """Base test class with common setup."""

    def setUp(self):
        # Create users
        self.super_admin = User.objects.create_user(
            email="super@test.com",
            password="testpass123",
            role=User.Role.SUPER_ADMIN,
            first_name="Super",
            last_name="Admin",
        )

        self.club_admin = User.objects.create_user(
            email="clubadmin@test.com",
            password="testpass123",
            role=User.Role.CLUB_ADMIN,
            first_name="Club",
            last_name="Admin",
        )

        self.fan = User.objects.create_user(
            email="fan@test.com",
            password="testpass123",
            role=User.Role.FAN,
            first_name="Test",
            last_name="Fan",
        )

        # Create club
        self.club = Club.objects.create(
            name="Test Club",
            slug="test-club",
            admin=self.club_admin,
        )
        self.club_admin.club = self.club
        self.club_admin.save()

        # Create second club for cross-club testing
        self.other_club = Club.objects.create(
            name="Other Club",
            slug="other-club",
        )

        # Create membership plan
        self.plan = MembershipPlan.objects.create(
            club=self.club,
            name="Basic Plan",
            tier=MembershipPlan.Tier.BASIC,
            price_amount=Decimal("50000.00"),
            billing_cycle=MembershipPlan.BillingCycle.MONTHLY,
            is_active=True,
            is_visible=True,
        )

        # Create membership subscription
        self.subscription = MembershipSubscription.objects.create(
            user=self.fan,
            plan=self.plan,
            club=self.club,
            status=MembershipSubscription.Status.ACTIVE,
        )

        # Create membership payment
        self.membership_payment = MembershipPayment.objects.create(
            subscription=self.subscription,
            subscription_plan=self.plan,
            amount_paid=Decimal("50000.00"),
            currency="UGX",
            payment_method=MembershipPayment.PaymentMethod.MTN_MOMO,
            transaction_reference="MEM-TEST-001",
            status=MembershipPayment.Status.CONFIRMED,
            paid_at=timezone.now(),
        )

        # Create Union, League, Competition, Match for ticketing tests
        self.union = Union.objects.create(name="Test Union", slug="test-union")
        self.league = League.objects.create(
            union=self.union,
            name="Test League",
            slug="test-league",
        )
        self.competition = Competition.objects.create(
            league=self.league,
            name="Test Competition 2025",
            slug="test-competition-2025",
            season="2025/26",
        )
        self.match = Match.objects.create(
            competition=self.competition,
            home_club=self.club,
            away_club=self.other_club,
            match_date=timezone.now() + timedelta(days=7),
            status=Match.Status.SCHEDULED,
        )

        # Create ticket type
        self.ticket_type = TicketType.objects.create(
            match=self.match,
            name="VIP",
            price=Decimal("30000.00"),
            currency="UGX",
            quantity_available=100,
            status=TicketType.Status.ACTIVE,
        )

        # Create ticket order
        self.ticket_order = TicketOrder.objects.create(
            buyer=self.fan,
            total_amount=Decimal("60000.00"),
            currency="UGX",
            status=TicketOrder.Status.PAID,
            provider=TicketOrder.PaymentProvider.MANUAL,
            payment_reference="TKT-TEST-001",
            paid_at=timezone.now(),
        )

        # Create ticket order item
        self.ticket_order_item = TicketOrderItem.objects.create(
            order=self.ticket_order,
            ticket_type=self.ticket_type,
            quantity=2,
            unit_price=Decimal("30000.00"),
            total_price=Decimal("60000.00"),
        )

        # API client
        self.client = APIClient()

        # Finance API endpoints
        self.base_url = "/api/finances/"
        self.membership_payments_url = f"{self.base_url}membership-payments/"
        self.ticketing_payments_url = f"{self.base_url}ticketing-payments/"
        self.summary_url = f"{self.base_url}summary/"
        self.invoices_url = f"{self.base_url}invoices/"
        self.receipts_url = f"{self.base_url}receipts/"
        self.audit_logs_url = f"{self.base_url}audit-logs/"


class MembershipPaymentReportTests(BaseFinanceTest):
    """Tests for Membership Payments Report API."""

    def test_unauthorized_access(self):
        """Test that unauthenticated users cannot access the endpoint."""
        response = self.client.get(self.membership_payments_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_fan_access_denied(self):
        """Test that regular fans cannot access the endpoint."""
        self.client.force_authenticate(user=self.fan)
        response = self.client.get(self.membership_payments_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_club_admin_successful_request(self):
        """Test that club admin can access membership payments."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.membership_payments_url,
            {"club": self.club.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)

    def test_super_admin_successful_request(self):
        """Test that super admin can access membership payments."""
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(
            self.membership_payments_url,
            {"club": self.club.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)

    def test_filter_by_status(self):
        """Test filtering by payment status."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.membership_payments_url,
            {"club": self.club.id, "status": MembershipPayment.Status.CONFIRMED},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)

        response = self.client.get(
            self.membership_payments_url,
            {"club": self.club.id, "status": MembershipPayment.Status.FAILED},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 0)

    def test_filter_by_tier(self):
        """Test filtering by membership tier."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.membership_payments_url,
            {"club": self.club.id, "tier": MembershipPlan.Tier.BASIC},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)

        response = self.client.get(
            self.membership_payments_url,
            {"club": self.club.id, "tier": MembershipPlan.Tier.GOLD},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 0)

    def test_search_by_member_name(self):
        """Test searching by member name."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.membership_payments_url,
            {"club": self.club.id, "search": "Test"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)

        response = self.client.get(
            self.membership_payments_url,
            {"club": self.club.id, "search": "NonExistent"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 0)

    def test_summary_statistics(self):
        """Test summary endpoint returns correct stats."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            f"{self.membership_payments_url}summary/",
            {"club": self.club.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_payments"], 1)
        self.assertEqual(response.data["total_revenue"], "50000.00")
        self.assertEqual(response.data["paid_count"], 1)
        self.assertEqual(response.data["pending_count"], 0)
        self.assertEqual(response.data["failed_count"], 0)

    def test_ordering(self):
        """Test ordering by payment date."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.membership_payments_url,
            {"club": self.club.id, "ordering": "-paid_at"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TicketingPaymentReportTests(BaseFinanceTest):
    """Tests for Ticketing Payments Report API."""

    def test_unauthorized_access(self):
        """Test that unauthenticated users cannot access the endpoint."""
        response = self.client.get(self.ticketing_payments_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_club_admin_successful_request(self):
        """Test that club admin can access ticketing payments."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.ticketing_payments_url,
            {"club": self.club.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)

    def test_summary_statistics(self):
        """Test summary endpoint for ticketing."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            f"{self.ticketing_payments_url}summary/",
            {"club": self.club.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tickets_sold"], 2)
        self.assertEqual(response.data["gross_revenue"], "60000.00")
        self.assertEqual(response.data["average_ticket_value"], "30000.00")
        self.assertEqual(response.data["successful_payments"], 1)
        self.assertEqual(response.data["failed_payments"], 0)

    def test_filter_by_match(self):
        """Test filtering by match."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.ticketing_payments_url,
            {"club": self.club.id, "match": self.match.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_filter_by_status(self):
        """Test filtering by payment status."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.ticketing_payments_url,
            {"club": self.club.id, "status": TicketOrder.Status.PAID},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class FinancialSummaryTests(BaseFinanceTest):
    """Tests for Financial Summary API."""

    def test_unauthorized_access(self):
        """Test that unauthenticated users cannot access."""
        response = self.client.get(self.summary_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_club_admin_successful_request(self):
        """Test club admin can access financial summary."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.summary_url,
            {"club": self.club.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("membership_income", response.data)
        self.assertIn("ticketing_income", response.data)
        self.assertIn("total_income", response.data)
        self.assertIn("net_balance", response.data)

    def test_summary_includes_all_income_types(self):
        """Test that summary includes all income types."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.summary_url,
            {"club": self.club.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(Decimal(response.data["membership_income"]), Decimal("0"))
        self.assertIn("sponsorship_income", response.data)
        self.assertIn("other_income", response.data)
        self.assertIn("club_expenses", response.data)

    def test_monthly_period_filter(self):
        """Test monthly period filtering."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.summary_url,
            {"club": self.club.id, "period": "monthly"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_yearly_period_filter(self):
        """Test yearly period filtering."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.summary_url,
            {"club": self.club.id, "period": "yearly"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_quarterly_period_filter(self):
        """Test quarterly period filtering."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.summary_url,
            {"club": self.club.id, "period": "quarterly"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_custom_date_range(self):
        """Test custom date range filtering."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.summary_url,
            {
                "club": self.club.id,
                "date_from": (timezone.now() - timedelta(days=30)).isoformat(),
                "date_to": timezone.now().isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_financial_summary_function(self):
        """Test the get_financial_summary service function."""
        summary = get_financial_summary(club_id=self.club.id)
        self.assertIn("membership_income", summary)
        self.assertIn("ticketing_income", summary)
        self.assertIn("sponsorship_income", summary)
        self.assertIn("total_income", summary)
        self.assertIn("net_balance", summary)
        self.assertGreater(summary["membership_income"], Decimal("0"))


class InvoiceAPITests(BaseFinanceTest):
    """Tests for Invoice API."""

    def test_create_invoice(self):
        """Test creating an invoice."""
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.post(
            self.invoices_url,
            {
                "club": self.club.id,
                "payment_type": Invoice.PaymentType.MEMBERSHIP_FEE,
                "amount": "50000.00",
                "currency": "UGX",
                "buyer_name": "Test Fan",
                "buyer_email": "fan@test.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("invoice_number", response.data)
        self.assertTrue(response.data["invoice_number"].startswith("INV-"))

    def test_retrieve_invoice(self):
        """Test retrieving a single invoice."""
        invoice = Invoice.objects.create(
            club=self.club,
            payment_type=Invoice.PaymentType.MEMBERSHIP_FEE,
            amount=Decimal("50000.00"),
            currency="UGX",
            status=Invoice.Status.ISSUED,
            member=self.fan,
            created_by=self.club_admin,
        )

        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(f"{self.invoices_url}{invoice.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["invoice_number"], invoice.invoice_number)

    def test_list_invoices(self):
        """Test listing invoices."""
        Invoice.objects.create(
            club=self.club,
            payment_type=Invoice.PaymentType.MEMBERSHIP_FEE,
            amount=Decimal("50000.00"),
            currency="UGX",
            status=Invoice.Status.ISSUED,
            created_by=self.club_admin,
        )

        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.invoices_url,
            {"club": self.club.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)

    def test_invoice_auto_generates_number(self):
        """Test that invoice number is auto-generated."""
        invoice = Invoice.objects.create(
            club=self.club,
            payment_type=Invoice.PaymentType.MEMBERSHIP_FEE,
            amount=Decimal("50000.00"),
            currency="UGX",
        )
        self.assertTrue(invoice.invoice_number.startswith("INV-"))

    def test_generate_receipt_from_invoice(self):
        """Test generating a receipt from an invoice."""
        invoice = Invoice.objects.create(
            club=self.club,
            payment_type=Invoice.PaymentType.MEMBERSHIP_FEE,
            amount=Decimal("50000.00"),
            currency="UGX",
            status=Invoice.Status.PAID,
            member=self.fan,
            created_by=self.club_admin,
            paid_date=timezone.now(),
        )

        self.client.force_authenticate(user=self.club_admin)
        response = self.client.post(
            f"{self.invoices_url}{invoice.id}/generate_receipt/",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("receipt_number", response.data["receipt"])
        self.assertTrue(response.data["receipt"]["receipt_number"].startswith("RCT-"))

    def test_draft_invoice_cannot_generate_receipt(self):
        """Test that draft invoices cannot generate receipts."""
        invoice = Invoice.objects.create(
            club=self.club,
            payment_type=Invoice.PaymentType.MEMBERSHIP_FEE,
            amount=Decimal("50000.00"),
            currency="UGX",
            status=Invoice.Status.DRAFT,
            created_by=self.club_admin,
        )

        self.client.force_authenticate(user=self.club_admin)
        response = self.client.post(
            f"{self.invoices_url}{invoice.id}/generate_receipt/",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ReceiptAPITests(BaseFinanceTest):
    """Tests for Receipt API."""

    def test_list_receipts(self):
        """Test listing receipts."""
        invoice = Invoice.objects.create(
            club=self.club,
            payment_type=Invoice.PaymentType.MEMBERSHIP_FEE,
            amount=Decimal("50000.00"),
            currency="UGX",
            status=Invoice.Status.PAID,
            created_by=self.club_admin,
        )
        Receipt.objects.create(
            club=self.club,
            payment_type=Receipt.PaymentType.MEMBERSHIP_FEE,
            invoice=invoice,
            amount=Decimal("50000.00"),
            currency="UGX",
            created_by=self.club_admin,
        )

        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.receipts_url,
            {"club": self.club.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)

    def test_retrieve_receipt(self):
        """Test retrieving a single receipt."""
        invoice = Invoice.objects.create(
            club=self.club,
            payment_type=Invoice.PaymentType.MEMBERSHIP_FEE,
            amount=Decimal("50000.00"),
            currency="UGX",
            status=Invoice.Status.PAID,
            created_by=self.club_admin,
        )
        receipt = Receipt.objects.create(
            club=self.club,
            payment_type=Receipt.PaymentType.MEMBERSHIP_FEE,
            invoice=invoice,
            amount=Decimal("50000.00"),
            currency="UGX",
            created_by=self.club_admin,
        )

        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(f"{self.receipts_url}{receipt.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["receipt_number"], receipt.receipt_number)

    def test_receipt_auto_generates_number(self):
        """Test that receipt number is auto-generated."""
        receipt = Receipt.objects.create(
            club=self.club,
            payment_type=Receipt.PaymentType.MEMBERSHIP_FEE,
            amount=Decimal("50000.00"),
            currency="UGX",
        )
        self.assertTrue(receipt.receipt_number.startswith("RCT-"))


class FinanceAuditLogTests(BaseFinanceTest):
    """Tests for Finance Audit Log API."""

    def test_log_finance_action(self):
        """Test that log_finance_action creates a log entry."""
        log = log_finance_action(
            club=self.club,
            actor=self.club_admin,
            action=FinanceAuditLog.Action.INVOICE_CREATED,
            target_type="Invoice",
            target_id=1,
            target_repr="Invoice INV-TEST-001",
            description="Test audit log entry",
        )
        self.assertIsNotNone(log)
        self.assertEqual(log.action, FinanceAuditLog.Action.INVOICE_CREATED)
        self.assertEqual(log.club, self.club)
        self.assertEqual(log.actor, self.club_admin)

    def test_audit_log_list(self):
        """Test listing audit logs."""
        log_finance_action(
            club=self.club,
            actor=self.club_admin,
            action=FinanceAuditLog.Action.INVOICE_CREATED,
            description="Test log",
        )

        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.audit_logs_url,
            {"club": self.club.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)

    def test_audit_log_unauthorized_access(self):
        """Test that unauthorized users cannot access audit logs."""
        response = self.client.get(self.audit_logs_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_audit_log_fan_access_denied(self):
        """Test that regular fans cannot access audit logs."""
        self.client.force_authenticate(user=self.fan)
        response = self.client.get(self.audit_logs_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_audit_log_filter_by_action(self):
        """Test filtering audit logs by action."""
        log_finance_action(
            club=self.club,
            actor=self.club_admin,
            action=FinanceAuditLog.Action.INVOICE_CREATED,
            description="Test invoice",
        )
        log_finance_action(
            club=self.club,
            actor=self.club_admin,
            action=FinanceAuditLog.Action.REPORT_VIEWED,
            description="Test report",
        )

        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.audit_logs_url,
            {
                "club": self.club.id,
                "action": FinanceAuditLog.Action.INVOICE_CREATED,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)

    def test_audit_log_filter_by_date(self):
        """Test filtering audit logs by date."""
        log_finance_action(
            club=self.club,
            actor=self.club_admin,
            action=FinanceAuditLog.Action.INVOICE_CREATED,
            description="Test log",
        )

        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.audit_logs_url,
            {
                "club": self.club.id,
                "date_from": (timezone.now() - timedelta(days=1)).isoformat(),
                "date_to": (timezone.now() + timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)

    def test_audit_log_search(self):
        """Test searching audit logs."""
        log_finance_action(
            club=self.club,
            actor=self.club_admin,
            action=FinanceAuditLog.Action.INVOICE_CREATED,
            description="Unique searchable description",
        )

        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.audit_logs_url,
            {
                "club": self.club.id,
                "search": "Unique searchable",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)

    def test_audit_log_filter_by_user(self):
        """Test filtering audit logs by user."""
        log_finance_action(
            club=self.club,
            actor=self.club_admin,
            action=FinanceAuditLog.Action.INVOICE_CREATED,
            description="Test log",
        )

        self.client.force_authenticate(user=self.club_admin)
        response = self.client.get(
            self.audit_logs_url,
            {
                "club": self.club.id,
                "actor_id": self.club_admin.id,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = _get_results(response)
        self.assertEqual(len(results), 1)
