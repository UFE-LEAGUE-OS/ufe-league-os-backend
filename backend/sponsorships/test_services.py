from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounts.models import User

from .models import (
    RevenueDistribution,
    RevenueShareRule,
    SponsorAccount,
    SponsorAccountMember,
    SponsorAgreement,
    SponsorCategory,
    SponsorPackage,
    SponsorPayment,
    SponsorPaymentSchedule,
    SponsorshipOwnerType,
    SponsorshipScopeType,
)
from .services.activation import (
    agreement_can_activate,
    get_activation_blocking_reason,
)
from .services.flutterwave_gateway import (
    extract_flutterwave_tx_ref,
    make_sponsor_payment_reference,
    validate_flutterwave_transaction,
)
from .services.payments import confirm_sponsor_payment
from .services.permissions import (
    can_access_sponsor_agreement,
    can_manage_sponsor_account_finance,
    can_manage_sponsor_members,
)
from .services.revenue import generate_revenue_distributions_for_payment


class SponsorshipServiceTests(TestCase):
    def setUp(self):
        self.sponsor_user = User.objects.create_user(
            email="sponsor.owner@example.com",
            password="StrongPass123!",
            first_name="Sponsor",
            last_name="Owner",
            role=User.Role.FAN,
        )

        self.admin_user = User.objects.create_user(
            email="club.admin@example.com",
            password="StrongPass123!",
            first_name="Club",
            last_name="Admin",
            role=User.Role.CLUB_ADMIN,
        )

        self.sponsor_account = SponsorAccount.objects.create(
            owner=self.sponsor_user,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="Test Corporate Sponsor Ltd",
            registration_country="UG",
            brn="TEST-BRN-001",
            status=SponsorAccount.Status.APPROVED,
        )

        SponsorAccountMember.objects.create(
            sponsor_account=self.sponsor_account,
            user=self.sponsor_user,
            member_role=SponsorAccountMember.MemberRole.OWNER,
            is_active=True,
        )

        self.sponsor_package = SponsorPackage.objects.create(
            name="Test Sponsor Package",
            description="Test package for sponsorship service tests.",
            owner_type=SponsorshipOwnerType.CLUB,
            owner_identifier="KOBS",
            owner_name="KOBS Rugby Club",
            scope_type=SponsorshipScopeType.CLUB,
            scope_identifier="KOBS",
            scope_name="KOBS Rugby Club",
            category=SponsorCategory.GENERAL,
            sponsor_type_allowed=SponsorPackage.SponsorTypeAllowed.BOTH,
            price_amount=Decimal("1000.00"),
            currency="UGX",
            status=SponsorPackage.Status.APPROVED,
            created_by=self.admin_user,
        )

        self.agreement = SponsorAgreement.objects.create(
            sponsor_account=self.sponsor_account,
            sponsor_package=self.sponsor_package,
            total_value=Decimal("1000.00"),
            currency="UGX",
            status=SponsorAgreement.Status.APPROVED,
            payment_source=SponsorAgreement.PaymentSource.PLATFORM,
            activation_rule=SponsorAgreement.ActivationRule.PAYMENT_CONFIRMED,
            platform_fee_required=False,
            platform_fee_status=SponsorAgreement.PlatformFeeStatus.NOT_REQUIRED,
            created_by=self.sponsor_user,
        )

        self.payment_schedule = SponsorPaymentSchedule.objects.create(
            agreement=self.agreement,
            schedule_type=SponsorPaymentSchedule.ScheduleType.ONE_TIME,
            sequence_number=1,
            due_date=date(2026, 6, 30),
            amount_due=Decimal("1000.00"),
            currency="UGX",
            status=SponsorPaymentSchedule.Status.PENDING,
        )

        self.payment = SponsorPayment.objects.create(
            agreement=self.agreement,
            payment_schedule=self.payment_schedule,
            amount_paid=Decimal("1000.00"),
            currency="UGX",
            payment_method=SponsorPayment.PaymentMethod.BANK_TRANSFER,
            status=SponsorPayment.Status.PENDING,
            transaction_reference="LOCAL-TEST-001",
            recorded_by=self.sponsor_user,
        )

    def test_owner_can_manage_sponsor_members(self):
        self.assertTrue(
            can_manage_sponsor_members(
                self.sponsor_user,
                self.sponsor_account,
            )
        )

    def test_owner_can_manage_sponsor_account_finance(self):
        self.assertTrue(
            can_manage_sponsor_account_finance(
                self.sponsor_user,
                self.sponsor_account,
            )
        )

    def test_sponsor_can_access_own_agreement(self):
        self.assertTrue(
            can_access_sponsor_agreement(
                self.sponsor_user,
                self.agreement,
            )
        )

    def test_agreement_cannot_activate_without_confirmed_payment(self):
        self.assertFalse(agreement_can_activate(self.agreement))
        self.assertEqual(
            get_activation_blocking_reason(self.agreement),
            "At least one sponsorship payment must be confirmed first.",
        )

    def test_confirm_sponsor_payment_updates_payment_schedule_and_agreement(self):
        payment, distributions = confirm_sponsor_payment(
            self.payment,
            actor=self.admin_user,
            note="Confirmed in service test.",
        )

        payment.refresh_from_db()
        self.payment_schedule.refresh_from_db()
        self.agreement.refresh_from_db()

        self.assertEqual(payment.status, SponsorPayment.Status.CONFIRMED)
        self.assertEqual(
            self.payment_schedule.status,
            SponsorPaymentSchedule.Status.PAID,
        )
        self.assertEqual(self.agreement.status, SponsorAgreement.Status.ACTIVE)
        self.assertEqual(distributions, [])

    def test_generate_revenue_distributions_from_percentage_rule(self):
        RevenueShareRule.objects.create(
            sponsor_package=self.sponsor_package,
            recipient_type=RevenueShareRule.RecipientType.CLUB,
            recipient_identifier="KOBS",
            recipient_name="KOBS Rugby Club",
            percentage=Decimal("10.00"),
            fixed_amount=Decimal("0.00"),
        )

        distributions = generate_revenue_distributions_for_payment(self.payment)

        self.assertEqual(len(distributions), 1)
        self.assertEqual(distributions[0].amount, Decimal("100.00"))
        self.assertEqual(distributions[0].currency, "UGX")
        self.assertEqual(
            distributions[0].status,
            RevenueDistribution.Status.ALLOCATED,
        )

    def test_make_sponsor_payment_reference_uses_agreement_id(self):
        reference = make_sponsor_payment_reference(self.agreement)

        self.assertTrue(reference.startswith(f"LOS-SPONSOR-{self.agreement.id}-"))

    def test_extract_flutterwave_tx_ref_from_nested_payload(self):
        payload = {
            "event": "charge.completed",
            "data": {
                "tx_ref": "LOS-SPONSOR-1-abc123",
            },
        }

        self.assertEqual(
            extract_flutterwave_tx_ref(payload),
            "LOS-SPONSOR-1-abc123",
        )

    def test_validate_flutterwave_transaction_success(self):
        self.payment.payment_method = SponsorPayment.PaymentMethod.FLUTTERWAVE
        self.payment.provider = SponsorPayment.PaymentProvider.FLUTTERWAVE
        self.payment.transaction_reference = "LOS-SPONSOR-1-test"
        self.payment.save(
            update_fields=[
                "payment_method",
                "provider",
                "transaction_reference",
            ]
        )

        response = {
            "data": {
                "status": "successful",
                "tx_ref": "LOS-SPONSOR-1-test",
                "currency": "UGX",
                "amount": "1000.00",
            }
        }

        is_valid, message = validate_flutterwave_transaction(
            self.payment,
            response,
        )

        self.assertTrue(is_valid)
        self.assertEqual(message, "")

    def test_validate_flutterwave_transaction_rejects_wrong_reference(self):
        response = {
            "data": {
                "status": "successful",
                "tx_ref": "WRONG-REFERENCE",
                "currency": "UGX",
                "amount": "1000.00",
            }
        }

        is_valid, message = validate_flutterwave_transaction(
            self.payment,
            response,
        )

        self.assertFalse(is_valid)
        self.assertEqual(
            message,
            "Flutterwave transaction reference does not match payment record.",
        )
