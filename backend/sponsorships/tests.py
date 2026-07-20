from unittest.mock import patch
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from .flutterwave import FlutterwaveError, build_checkout_payload
from .models import (
    RevenueDistribution,
    RevenueShareRule,
    SponsorAgreement,
    SponsorBenefit,
    SponsorPackage,
    SponsorPayment,
    SponsorPaymentSchedule,
    SponsorWorkflowEvent,
)

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from .models import SponsorAccount, SponsorAccountMember

# Create your tests here.

User = get_user_model()


class SponsorAccountModelTests(TestCase):
    def create_user(self, email="sponsor-owner@example.com"):
        return User.objects.create_user(
            email=email,
            phone_number=None,
            password="StrongPass123",
            first_name="Sponsor",
            last_name="Owner",
        )

    def test_existing_fan_can_own_individual_sponsor_account(self):
        user = self.create_user()

        sponsor_account = SponsorAccount.objects.create(
            owner=user,
            sponsor_type=SponsorAccount.SponsorType.INDIVIDUAL,
            name=user.full_name,
        )

        SponsorAccountMember.objects.create(
            sponsor_account=sponsor_account,
            user=user,
            member_role=SponsorAccountMember.MemberRole.OWNER,
        )

        user.refresh_from_db()

        self.assertEqual(user.role, User.Role.FAN)
        self.assertEqual(
            sponsor_account.sponsor_type,
            SponsorAccount.SponsorType.INDIVIDUAL,
        )
        self.assertTrue(sponsor_account.is_individual)
        self.assertFalse(sponsor_account.is_corporate)
        self.assertTrue(user.sponsor_memberships.filter(is_active=True).exists())

    def test_corporate_sponsor_account_can_store_business_details(self):
        user = self.create_user("corporate-owner@example.com")

        sponsor_account = SponsorAccount.objects.create(
            owner=user,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="KCB Bank Uganda",
            registration_country="UG",
            brn="BRN-12345",
            tin="TIN-12345",
        )

        self.assertEqual(sponsor_account.name, "KCB Bank Uganda")
        self.assertEqual(sponsor_account.registration_country, "UG")
        self.assertEqual(sponsor_account.brn, "BRN-12345")
        self.assertEqual(sponsor_account.tin, "TIN-12345")
        self.assertTrue(sponsor_account.is_corporate)
        self.assertFalse(sponsor_account.is_individual)

    def test_sponsor_account_status_defaults_to_pending(self):
        user = self.create_user("pending-owner@example.com")

        sponsor_account = SponsorAccount.objects.create(
            owner=user,
            sponsor_type=SponsorAccount.SponsorType.INDIVIDUAL,
            name=user.full_name,
        )

        self.assertEqual(sponsor_account.status, SponsorAccount.Status.PENDING)

    def test_sponsor_account_owner_can_have_owner_membership(self):
        user = self.create_user("member-owner@example.com")

        sponsor_account = SponsorAccount.objects.create(
            owner=user,
            sponsor_type=SponsorAccount.SponsorType.INDIVIDUAL,
            name=user.full_name,
        )

        member = SponsorAccountMember.objects.create(
            sponsor_account=sponsor_account,
            user=user,
            member_role=SponsorAccountMember.MemberRole.OWNER,
        )

        self.assertEqual(member.user, user)
        self.assertEqual(member.sponsor_account, sponsor_account)
        self.assertEqual(member.member_role, SponsorAccountMember.MemberRole.OWNER)
        self.assertTrue(member.is_active)

    def test_same_user_cannot_be_added_twice_to_same_sponsor_account(self):
        user = self.create_user("unique-member@example.com")

        sponsor_account = SponsorAccount.objects.create(
            owner=user,
            sponsor_type=SponsorAccount.SponsorType.INDIVIDUAL,
            name=user.full_name,
        )

        SponsorAccountMember.objects.create(
            sponsor_account=sponsor_account,
            user=user,
            member_role=SponsorAccountMember.MemberRole.OWNER,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SponsorAccountMember.objects.create(
                    sponsor_account=sponsor_account,
                    user=user,
                    member_role=SponsorAccountMember.MemberRole.ADMIN,
                )

    def test_corporate_sponsor_can_have_multiple_members(self):
        owner = self.create_user("corporate-owner-2@example.com")

        admin_user = User.objects.create_user(
            email="corporate-admin@example.com",
            phone_number=None,
            password="StrongPass123",
            first_name="Corporate",
            last_name="Admin",
        )

        sponsor_account = SponsorAccount.objects.create(
            owner=owner,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="Nile Special",
            registration_country="UG",
            brn="BRN-67890",
            tin="TIN-67890",
        )

        SponsorAccountMember.objects.create(
            sponsor_account=sponsor_account,
            user=owner,
            member_role=SponsorAccountMember.MemberRole.OWNER,
        )

        SponsorAccountMember.objects.create(
            sponsor_account=sponsor_account,
            user=admin_user,
            member_role=SponsorAccountMember.MemberRole.ADMIN,
        )

        self.assertEqual(sponsor_account.members.count(), 2)
        self.assertTrue(
            sponsor_account.members.filter(
                user=admin_user,
                member_role=SponsorAccountMember.MemberRole.ADMIN,
            ).exists()
        )

    def test_corporate_sponsor_brn_must_be_unique_within_same_country(self):
        owner_one = self.create_user("brn-owner-one@example.com")
        owner_two = self.create_user("brn-owner-two@example.com")

        SponsorAccount.objects.create(
            owner=owner_one,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="Corporate One",
            registration_country="UG",
            brn="BRN-12345",
            tin="TIN-11111",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SponsorAccount.objects.create(
                    owner=owner_two,
                    sponsor_type=SponsorAccount.SponsorType.CORPORATE,
                    name="Corporate Two",
                    registration_country="UG",
                    brn="BRN-12345",
                    tin="TIN-22222",
                )

    def test_corporate_sponsor_tin_must_be_unique_within_same_country(self):
        owner_one = self.create_user("tin-owner-one@example.com")
        owner_two = self.create_user("tin-owner-two@example.com")

        SponsorAccount.objects.create(
            owner=owner_one,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="Corporate One",
            registration_country="UG",
            brn="BRN-11111",
            tin="TIN-12345",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SponsorAccount.objects.create(
                    owner=owner_two,
                    sponsor_type=SponsorAccount.SponsorType.CORPORATE,
                    name="Corporate Two",
                    registration_country="UG",
                    brn="BRN-22222",
                    tin="TIN-12345",
                )

    def test_same_corporate_identifier_can_exist_in_different_countries(self):
        owner_one = self.create_user("ug-owner@example.com")
        owner_two = self.create_user("ke-owner@example.com")

        SponsorAccount.objects.create(
            owner=owner_one,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="Uganda Corporate",
            registration_country="UG",
            brn="BRN-12345",
            tin="TIN-12345",
        )

        sponsor_account = SponsorAccount.objects.create(
            owner=owner_two,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="Kenya Corporate",
            registration_country="KE",
            brn="BRN-12345",
            tin="TIN-12345",
        )

        self.assertEqual(sponsor_account.registration_country, "KE")
        self.assertEqual(sponsor_account.brn, "BRN-12345")
        self.assertEqual(sponsor_account.tin, "TIN-12345")

    def test_corporate_sponsor_requires_brn_or_tin(self):
        owner = self.create_user("missing-id-owner@example.com")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SponsorAccount.objects.create(
                    owner=owner,
                    sponsor_type=SponsorAccount.SponsorType.CORPORATE,
                    name="No Identifier Corporate",
                    registration_country="UG",
                )

    def test_corporate_sponsor_identifiers_are_normalized_on_save(self):
        owner = self.create_user("normalized-owner@example.com")

        sponsor_account = SponsorAccount.objects.create(
            owner=owner,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="Normalized Corporate",
            registration_country=" ug ",
            brn=" brn-12345 ",
            tin=" tin-12345 ",
        )

        self.assertEqual(sponsor_account.registration_country, "UG")
        self.assertEqual(sponsor_account.brn, "BRN-12345")
        self.assertEqual(sponsor_account.tin, "TIN-12345")


class SponsorshipAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "StrongPass123"

    def create_user(self, email="sponsor-api-user@example.com"):
        return User.objects.create_user(
            email=email,
            phone_number=None,
            password=self.password,
            first_name="Sponsor",
            last_name="User",
        )

    def authenticate(self, user):
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

        login_response = self.client.post(
            "/api/accounts/login/",
            {
                "identifier": user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(login_response.status_code, 200)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}",
        )

    def test_individual_sponsor_can_register_directly(self):
        response = self.client.post(
            "/api/sponsorships/register/",
            {
                "sponsor_type": "INDIVIDUAL",
                "email": "direct-individual@example.com",
                "phone_number": "0702000101",
                "first_name": "Direct",
                "last_name": "Sponsor",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        user = User.objects.get(email="direct-individual@example.com")

        self.assertEqual(user.role, User.Role.FAN)
        self.assertTrue(user.is_sponsor)
        self.assertEqual(user.sponsor_type, SponsorAccount.SponsorType.INDIVIDUAL)
        self.assertTrue(response.data["user"]["is_sponsor"])
        self.assertTrue(user.sponsor_memberships.filter(is_active=True).exists())
        self.assertEqual(
            response.data["sponsor_account"]["sponsor_type"],
            SponsorAccount.SponsorType.INDIVIDUAL,
        )

    def test_corporate_sponsor_can_register_directly(self):
        response = self.client.post(
            "/api/sponsorships/register/",
            {
                "sponsor_type": "CORPORATE",
                "company_name": "KCB Bank Uganda",
                "registration_country": "UG",
                "brn": "BRN-API-001",
                "tin": "1000000001",
                "email": "kcb-api-owner@example.com",
                "phone_number": "0702000102",
                "first_name": "KCB",
                "last_name": "Owner",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        sponsor_account = SponsorAccount.objects.get(name="KCB Bank Uganda")
        user = User.objects.get(email="kcb-api-owner@example.com")

        self.assertEqual(
            sponsor_account.sponsor_type,
            SponsorAccount.SponsorType.CORPORATE,
        )
        self.assertTrue(user.is_sponsor)
        self.assertEqual(user.sponsor_type, SponsorAccount.SponsorType.CORPORATE)
        self.assertTrue(response.data["user"]["is_sponsor"])
        self.assertEqual(
            response.data["user"]["sponsor_type"],
            SponsorAccount.SponsorType.CORPORATE,
        )

    def test_corporate_sponsor_registration_rejects_duplicate_brn(self):
        owner = self.create_user("existing-brn-owner@example.com")

        SponsorAccount.objects.create(
            owner=owner,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="Existing Corporate",
            registration_country="UG",
            brn="BRN-DUP-001",
            tin="1000000002",
        )

        response = self.client.post(
            "/api/sponsorships/register/",
            {
                "sponsor_type": "CORPORATE",
                "company_name": "Duplicate Corporate",
                "registration_country": "UG",
                "brn": "BRN-DUP-001",
                "tin": "1000000003",
                "email": "duplicate-brn@example.com",
                "phone_number": "0702000103",
                "first_name": "Duplicate",
                "last_name": "Owner",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("brn", response.data)

    def test_existing_fan_can_create_individual_sponsor_account(self):
        user = self.create_user("fan-upgrade-api@example.com")
        self.authenticate(user)

        response = self.client.post(
            "/api/sponsorships/accounts/",
            {
                "sponsor_type": "INDIVIDUAL",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        user.refresh_from_db()

        self.assertEqual(user.role, User.Role.FAN)
        self.assertTrue(user.sponsor_memberships.filter(is_active=True).exists())

    def test_authenticated_user_can_list_own_sponsor_accounts(self):
        user = self.create_user("list-sponsors@example.com")

        sponsor_account = SponsorAccount.objects.create(
            owner=user,
            sponsor_type=SponsorAccount.SponsorType.INDIVIDUAL,
            name=user.full_name,
        )

        SponsorAccountMember.objects.create(
            sponsor_account=sponsor_account,
            user=user,
            member_role=SponsorAccountMember.MemberRole.OWNER,
        )

        self.authenticate(user)

        response = self.client.get("/api/sponsorships/accounts/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_corporate_sponsor_owner_can_add_member(self):
        owner = self.create_user("corporate-owner-api@example.com")
        member_user = self.create_user("corporate-member-api@example.com")

        sponsor_account = SponsorAccount.objects.create(
            owner=owner,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="Corporate Member Test",
            registration_country="UG",
            brn="BRN-MEMBER-001",
            tin="1000000004",
        )

        SponsorAccountMember.objects.create(
            sponsor_account=sponsor_account,
            user=owner,
            member_role=SponsorAccountMember.MemberRole.OWNER,
        )

        self.authenticate(owner)

        response = self.client.post(
            f"/api/sponsorships/accounts/{sponsor_account.id}/members/",
            {
                "email": member_user.email,
                "member_role": "ADMIN",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        self.assertTrue(
            SponsorAccountMember.objects.filter(
                sponsor_account=sponsor_account,
                user=member_user,
                member_role=SponsorAccountMember.MemberRole.ADMIN,
            ).exists()
        )

    def test_fan_with_sponsor_membership_can_access_sponsor_dashboard(self):
        user = self.create_user("sponsor-dashboard-api@example.com")

        sponsor_account = SponsorAccount.objects.create(
            owner=user,
            sponsor_type=SponsorAccount.SponsorType.INDIVIDUAL,
            name=user.full_name,
            status=SponsorAccount.Status.APPROVED,
        )

        SponsorAccountMember.objects.create(
            sponsor_account=sponsor_account,
            user=user,
            member_role=SponsorAccountMember.MemberRole.OWNER,
        )

        self.authenticate(user)

        response = self.client.get("/api/dashboards/sponsor/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["dashboard_role"], User.Role.SPONSOR)
        self.assertEqual(response.data["dashboard"]["title"], "Sponsor Dashboard")

    def test_fan_without_sponsor_membership_cannot_access_sponsor_dashboard(self):
        user = self.create_user("normal-fan-api@example.com")
        self.authenticate(user)

        response = self.client.get("/api/dashboards/sponsor/")

        self.assertEqual(response.status_code, 403)


class SponsorHubCoreModelTests(TestCase):
    def create_sponsor_owner(self, email="hub-owner@example.com"):
        return User.objects.create_user(
            email=email,
            phone_number=None,
            password="StrongPass123",
            first_name="Hub",
            last_name="Owner",
        )

    def create_sponsor_account(self, owner=None):
        owner = owner or self.create_sponsor_owner()

        sponsor_account = SponsorAccount.objects.create(
            owner=owner,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="KCB Bank Uganda",
            registration_country="UG",
            brn="KCB-BRN-001",
            tin="KCB-TIN-001",
            status=SponsorAccount.Status.APPROVED,
        )

        SponsorAccountMember.objects.create(
            sponsor_account=sponsor_account,
            user=owner,
            member_role=SponsorAccountMember.MemberRole.OWNER,
        )

        return sponsor_account

    def create_package(self, created_by=None):
        created_by = created_by or self.create_sponsor_owner(
            "package-owner@example.com"
        )

        return SponsorPackage.objects.create(
            name="Elgon Cup Matchday Sponsor",
            description="Sponsor visibility for a national team matchday.",
            owner_type="UNION",
            owner_identifier="uru",
            owner_name="Uganda Rugby Union",
            scope_type="EVENT",
            scope_identifier="elgon-cup-2026",
            scope_name="Elgon Cup 2026",
            sponsor_type_allowed=SponsorPackage.SponsorTypeAllowed.BOTH,
            category="BANKING",
            price_amount=Decimal("5000000.00"),
            currency="UGX",
            is_exclusive=True,
            requires_platform_fee=True,
            platform_fee_amount=Decimal("500000.00"),
            activation_rule=SponsorPackage.ActivationRule.AFTER_PLATFORM_FEE,
            status=SponsorPackage.Status.APPROVED,
            created_by=created_by,
        )

    def test_sponsor_package_can_define_owner_scope_and_platform_fee(self):
        sponsor_package = self.create_package()

        self.assertEqual(sponsor_package.owner_type, "UNION")
        self.assertEqual(sponsor_package.scope_type, "EVENT")
        self.assertEqual(sponsor_package.scope_name, "Elgon Cup 2026")
        self.assertTrue(sponsor_package.is_exclusive)
        self.assertTrue(sponsor_package.requires_platform_fee)
        self.assertEqual(sponsor_package.platform_fee_amount, Decimal("500000.00"))

    def test_sponsor_package_can_have_platform_controlled_benefits(self):
        sponsor_package = self.create_package()

        benefit = SponsorBenefit.objects.create(
            sponsor_package=sponsor_package,
            benefit_type=SponsorBenefit.BenefitType.FAN_DASHBOARD_AD,
            name="Fan Dashboard Placement",
            description="Sponsor logo appears on the fan dashboard.",
            quantity=1,
            is_platform_controlled=True,
            requires_payment_confirmation=True,
        )

        self.assertEqual(benefit.sponsor_package, sponsor_package)
        self.assertTrue(benefit.is_platform_controlled)
        self.assertTrue(benefit.requires_payment_confirmation)

    def test_existing_off_platform_sponsorship_can_be_recorded(self):
        sponsor_account = self.create_sponsor_account()
        sponsor_package = self.create_package()

        agreement = SponsorAgreement.objects.create(
            sponsor_account=sponsor_account,
            sponsor_package=sponsor_package,
            agreement_type=SponsorAgreement.AgreementType.EXISTING_CONTRACT,
            payment_source=SponsorAgreement.PaymentSource.EXISTING_CONTRACT,
            payment_model=SponsorAgreement.PaymentModel.EXTERNAL,
            total_value=Decimal("10000000.00"),
            currency="UGX",
            starts_at=date.today(),
            ends_at=date.today() + timedelta(days=365),
            status=SponsorAgreement.Status.APPROVED,
            platform_fee_required=True,
            platform_fee_amount=Decimal("500000.00"),
            platform_fee_status=SponsorAgreement.PlatformFeeStatus.PENDING,
            benefits_tier=SponsorAgreement.BenefitsTier.BASIC,
            activation_rule=SponsorAgreement.ActivationRule.PLATFORM_FEE_CONFIRMED,
            proof_reference="Existing URU sponsorship contract reference",
            created_by=sponsor_account.owner,
        )

        self.assertEqual(
            agreement.payment_source,
            SponsorAgreement.PaymentSource.EXISTING_CONTRACT,
        )
        self.assertEqual(
            agreement.payment_model,
            SponsorAgreement.PaymentModel.EXTERNAL,
        )
        self.assertEqual(
            agreement.platform_fee_status,
            SponsorAgreement.PlatformFeeStatus.PENDING,
        )

    def test_one_time_payment_schedule_and_payment_can_be_recorded(self):
        sponsor_account = self.create_sponsor_account()
        sponsor_package = self.create_package()

        agreement = SponsorAgreement.objects.create(
            sponsor_account=sponsor_account,
            sponsor_package=sponsor_package,
            payment_model=SponsorAgreement.PaymentModel.ONE_TIME,
            total_value=Decimal("5000000.00"),
            currency="UGX",
            status=SponsorAgreement.Status.PENDING_PAYMENT,
            created_by=sponsor_account.owner,
        )

        schedule = SponsorPaymentSchedule.objects.create(
            agreement=agreement,
            schedule_type=SponsorPaymentSchedule.ScheduleType.ONE_TIME,
            sequence_number=1,
            due_date=date.today(),
            amount_due=Decimal("5000000.00"),
            currency="UGX",
        )

        payment = SponsorPayment.objects.create(
            agreement=agreement,
            payment_schedule=schedule,
            amount_paid=Decimal("5000000.00"),
            currency="UGX",
            payment_method=SponsorPayment.PaymentMethod.BANK_TRANSFER,
            transaction_reference="BANK-REF-001",
            paid_at=timezone.now(),
            status=SponsorPayment.Status.CONFIRMED,
            recorded_by=sponsor_account.owner,
            confirmed_by=sponsor_account.owner,
            confirmed_at=timezone.now(),
        )

        self.assertEqual(payment.agreement, agreement)
        self.assertEqual(payment.payment_schedule, schedule)
        self.assertEqual(payment.status, SponsorPayment.Status.CONFIRMED)

    def test_recurring_agreement_can_have_multiple_payment_schedules(self):
        sponsor_account = self.create_sponsor_account()
        sponsor_package = self.create_package()

        agreement = SponsorAgreement.objects.create(
            sponsor_account=sponsor_account,
            sponsor_package=sponsor_package,
            payment_model=SponsorAgreement.PaymentModel.RECURRING,
            total_value=Decimal("1500000.00"),
            currency="UGX",
            status=SponsorAgreement.Status.PENDING_PAYMENT,
            created_by=sponsor_account.owner,
        )

        today = date.today()

        for index in range(1, 4):
            SponsorPaymentSchedule.objects.create(
                agreement=agreement,
                schedule_type=SponsorPaymentSchedule.ScheduleType.RECURRING,
                sequence_number=index,
                due_date=today + timedelta(days=30 * (index - 1)),
                period_start=today + timedelta(days=30 * (index - 1)),
                period_end=today + timedelta(days=(30 * index) - 1),
                amount_due=Decimal("500000.00"),
                currency="UGX",
            )

        self.assertEqual(agreement.payment_schedules.count(), 3)

    def test_revenue_share_rules_and_distributions_can_be_recorded(self):
        sponsor_account = self.create_sponsor_account()
        sponsor_package = self.create_package()

        agreement = SponsorAgreement.objects.create(
            sponsor_account=sponsor_account,
            sponsor_package=sponsor_package,
            payment_model=SponsorAgreement.PaymentModel.ONE_TIME,
            total_value=Decimal("1000000.00"),
            currency="UGX",
            status=SponsorAgreement.Status.ACTIVE,
            created_by=sponsor_account.owner,
        )

        payment = SponsorPayment.objects.create(
            agreement=agreement,
            amount_paid=Decimal("1000000.00"),
            currency="UGX",
            payment_method=SponsorPayment.PaymentMethod.MOBILE_MONEY,
            transaction_reference="MM-001",
            paid_at=timezone.now(),
            status=SponsorPayment.Status.CONFIRMED,
            recorded_by=sponsor_account.owner,
            confirmed_by=sponsor_account.owner,
            confirmed_at=timezone.now(),
        )

        RevenueShareRule.objects.create(
            sponsor_package=sponsor_package,
            recipient_type=RevenueShareRule.RecipientType.UNION,
            recipient_identifier="uru",
            recipient_name="Uganda Rugby Union",
            percentage=Decimal("85.00"),
        )

        RevenueShareRule.objects.create(
            sponsor_package=sponsor_package,
            recipient_type=RevenueShareRule.RecipientType.PLATFORM,
            recipient_identifier="league-os",
            recipient_name="League OS Platform",
            percentage=Decimal("15.00"),
            is_platform_share=True,
        )

        RevenueDistribution.objects.create(
            payment=payment,
            agreement=agreement,
            recipient_type=RevenueShareRule.RecipientType.UNION,
            recipient_identifier="uru",
            recipient_name="Uganda Rugby Union",
            amount=Decimal("850000.00"),
            currency="UGX",
            status=RevenueDistribution.Status.ALLOCATED,
        )

        RevenueDistribution.objects.create(
            payment=payment,
            agreement=agreement,
            recipient_type=RevenueShareRule.RecipientType.PLATFORM,
            recipient_identifier="league-os",
            recipient_name="League OS Platform",
            amount=Decimal("150000.00"),
            currency="UGX",
            status=RevenueDistribution.Status.ALLOCATED,
        )

        self.assertEqual(sponsor_package.revenue_share_rules.count(), 2)
        self.assertEqual(payment.revenue_distributions.count(), 2)

    def test_sponsor_workflow_event_records_audit_trail(self):
        sponsor_account = self.create_sponsor_account()
        sponsor_package = self.create_package()

        agreement = SponsorAgreement.objects.create(
            sponsor_account=sponsor_account,
            sponsor_package=sponsor_package,
            total_value=Decimal("1000000.00"),
            currency="UGX",
            status=SponsorAgreement.Status.SUBMITTED,
            created_by=sponsor_account.owner,
        )

        event = SponsorWorkflowEvent.objects.create(
            sponsor_package=sponsor_package,
            agreement=agreement,
            actor=sponsor_account.owner,
            event_type=SponsorWorkflowEvent.EventType.AGREEMENT_SUBMITTED,
            from_status=SponsorAgreement.Status.DRAFT,
            to_status=SponsorAgreement.Status.SUBMITTED,
            note="Sponsor submitted agreement for approval.",
        )

        self.assertEqual(event.agreement, agreement)
        self.assertEqual(
            event.event_type,
            SponsorWorkflowEvent.EventType.AGREEMENT_SUBMITTED,
        )
        self.assertEqual(event.actor, sponsor_account.owner)


class SponsorPackageAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "StrongPass123"

    def create_user(self, email, role=User.Role.FAN):
        return User.objects.create_user(
            email=email,
            phone_number=None,
            password=self.password,
            first_name="Sponsor",
            last_name="Tester",
            role=role,
        )

    def authenticate(self, user):
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

        login_response = self.client.post(
            "/api/accounts/login/",
            {
                "identifier": user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(login_response.status_code, 200)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}",
        )

    def package_payload(self):
        return {
            "name": "Elgon Cup Matchday Sponsor",
            "description": "Sponsor visibility for a national team matchday.",
            "owner_type": "UNION",
            "owner_identifier": "uru",
            "owner_name": "Uganda Rugby Union",
            "scope_type": "EVENT",
            "scope_identifier": "elgon-cup-2026",
            "scope_name": "Elgon Cup 2026",
            "sponsor_type_allowed": "BOTH",
            "category": "BANKING",
            "price_amount": "5000000.00",
            "currency": "UGX",
            "is_exclusive": True,
            "requires_platform_fee": True,
            "platform_fee_amount": "500000.00",
            "activation_rule": "AFTER_PLATFORM_FEE",
            "status": "DRAFT",
        }

    def create_package(self, created_by=None, status="DRAFT"):
        created_by = created_by or self.create_user(
            "package-creator@example.com",
            User.Role.UNION_ADMIN,
        )

        return SponsorPackage.objects.create(
            name="Elgon Cup Matchday Sponsor",
            description="Sponsor visibility for a national team matchday.",
            owner_type="UNION",
            owner_identifier="uru",
            owner_name="Uganda Rugby Union",
            scope_type="EVENT",
            scope_identifier="elgon-cup-2026",
            scope_name="Elgon Cup 2026",
            sponsor_type_allowed=SponsorPackage.SponsorTypeAllowed.BOTH,
            category="BANKING",
            price_amount=Decimal("5000000.00"),
            currency="UGX",
            is_exclusive=True,
            requires_platform_fee=True,
            platform_fee_amount=Decimal("500000.00"),
            activation_rule=SponsorPackage.ActivationRule.AFTER_PLATFORM_FEE,
            status=status,
            created_by=created_by,
        )

    def test_sponsor_hub_admin_can_create_package(self):
        user = self.create_user(
            "union-admin-package@example.com",
            User.Role.UNION_ADMIN,
        )
        self.authenticate(user)

        response = self.client.post(
            "/api/sponsorships/packages/",
            self.package_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["package"]["name"], "Elgon Cup Matchday Sponsor")

        sponsor_package = SponsorPackage.objects.get(name="Elgon Cup Matchday Sponsor")

        self.assertEqual(sponsor_package.created_by, user)
        self.assertEqual(sponsor_package.owner_type, "UNION")
        self.assertTrue(
            SponsorWorkflowEvent.objects.filter(
                sponsor_package=sponsor_package,
                event_type=SponsorWorkflowEvent.EventType.PACKAGE_CREATED,
                actor=user,
            ).exists()
        )

    def test_fan_cannot_create_sponsor_package(self):
        user = self.create_user("normal-fan-package@example.com", User.Role.FAN)
        self.authenticate(user)

        response = self.client.post(
            "/api/sponsorships/packages/",
            self.package_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_non_admin_can_only_list_approved_or_active_packages(self):
        user = self.create_user("package-list-fan@example.com", User.Role.FAN)

        self.create_package(
            created_by=self.create_user(
                "draft-package-owner@example.com",
                User.Role.UNION_ADMIN,
            ),
            status=SponsorPackage.Status.DRAFT,
        )

        approved_package = self.create_package(
            created_by=self.create_user(
                "approved-package-owner@example.com",
                User.Role.UNION_ADMIN,
            ),
            status=SponsorPackage.Status.APPROVED,
        )
        approved_package.name = "Approved Elgon Cup Package"
        approved_package.save(update_fields=["name"])

        self.authenticate(user)

        response = self.client.get("/api/sponsorships/packages/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["name"],
            "Approved Elgon Cup Package",
        )

    def test_package_owner_admin_can_approve_package(self):
        user = self.create_user(
            "union-admin-approve-package@example.com",
            User.Role.UNION_ADMIN,
        )
        sponsor_package = self.create_package(created_by=user)

        self.authenticate(user)

        response = self.client.post(
            f"/api/sponsorships/packages/{sponsor_package.id}/approve/",
            {"note": "Package approved for Elgon Cup."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        sponsor_package.refresh_from_db()

        self.assertEqual(sponsor_package.status, SponsorPackage.Status.APPROVED)
        self.assertEqual(sponsor_package.approved_by, user)
        self.assertIsNotNone(sponsor_package.approved_at)
        self.assertTrue(
            SponsorWorkflowEvent.objects.filter(
                sponsor_package=sponsor_package,
                event_type=SponsorWorkflowEvent.EventType.PACKAGE_APPROVED,
                actor=user,
            ).exists()
        )

    def test_package_owner_admin_can_reject_package(self):
        user = self.create_user(
            "union-admin-reject-package@example.com",
            User.Role.UNION_ADMIN,
        )
        sponsor_package = self.create_package(created_by=user)

        self.authenticate(user)

        response = self.client.post(
            f"/api/sponsorships/packages/{sponsor_package.id}/reject/",
            {"note": "Package requires commercial review."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        sponsor_package.refresh_from_db()

        self.assertEqual(sponsor_package.status, SponsorPackage.Status.REJECTED)
        self.assertTrue(
            SponsorWorkflowEvent.objects.filter(
                sponsor_package=sponsor_package,
                event_type=SponsorWorkflowEvent.EventType.PACKAGE_REJECTED,
                actor=user,
            ).exists()
        )

    def test_package_owner_admin_can_add_benefit(self):
        user = self.create_user(
            "union-admin-benefit@example.com",
            User.Role.UNION_ADMIN,
        )
        sponsor_package = self.create_package(
            created_by=user,
            status=SponsorPackage.Status.APPROVED,
        )

        self.authenticate(user)

        response = self.client.post(
            f"/api/sponsorships/packages/{sponsor_package.id}/benefits/",
            {
                "benefit_type": "FAN_DASHBOARD_AD",
                "name": "Fan Dashboard Placement",
                "description": "Sponsor logo appears on the fan dashboard.",
                "quantity": 1,
                "discount_percentage": "0.00",
                "value_amount": "0.00",
                "requires_payment_confirmation": True,
                "is_platform_controlled": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            SponsorBenefit.objects.filter(
                sponsor_package=sponsor_package,
                benefit_type=SponsorBenefit.BenefitType.FAN_DASHBOARD_AD,
            ).exists()
        )

    def test_package_owner_admin_can_add_revenue_share_rule(self):
        user = self.create_user(
            "union-admin-revenue-share@example.com",
            User.Role.UNION_ADMIN,
        )
        sponsor_package = self.create_package(
            created_by=user,
            status=SponsorPackage.Status.APPROVED,
        )

        self.authenticate(user)

        response = self.client.post(
            f"/api/sponsorships/packages/{sponsor_package.id}/revenue-share-rules/",
            {
                "recipient_type": "UNION",
                "recipient_identifier": "uru",
                "recipient_name": "Uganda Rugby Union",
                "percentage": "85.00",
                "fixed_amount": "0.00",
                "is_platform_share": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            RevenueShareRule.objects.filter(
                sponsor_package=sponsor_package,
                recipient_type=RevenueShareRule.RecipientType.UNION,
                percentage=Decimal("85.00"),
            ).exists()
        )

    def test_fan_cannot_add_benefit_to_package(self):
        admin_user = self.create_user(
            "benefit-package-owner@example.com",
            User.Role.UNION_ADMIN,
        )
        fan_user = self.create_user("fan-cannot-add-benefit@example.com", User.Role.FAN)

        sponsor_package = self.create_package(
            created_by=admin_user,
            status=SponsorPackage.Status.APPROVED,
        )

        self.authenticate(fan_user)

        response = self.client.post(
            f"/api/sponsorships/packages/{sponsor_package.id}/benefits/",
            {
                "benefit_type": "FAN_DASHBOARD_AD",
                "name": "Fan Dashboard Placement",
                "quantity": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)


class SponsorAgreementPaymentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "StrongPass123"

    def create_user(self, email, role=User.Role.FAN):
        return User.objects.create_user(
            email=email,
            phone_number=None,
            password=self.password,
            first_name="Test",
            last_name="User",
            role=role,
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def create_sponsor_account(self, owner=None):
        owner = owner or self.create_user("phase13-sponsor@example.com")
        sponsor_account = SponsorAccount.objects.create(
            owner=owner,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="Phase 13 Sponsor",
            registration_country="UG",
            brn="BRN-PHASE13",
            tin="1234567899",
            status=SponsorAccount.Status.APPROVED,
        )
        SponsorAccountMember.objects.create(
            sponsor_account=sponsor_account,
            user=owner,
            member_role=SponsorAccountMember.MemberRole.OWNER,
        )
        return sponsor_account

    def create_sponsor_package(self, created_by=None):
        created_by = created_by or self.create_user(
            "phase13-union@example.com",
            role=User.Role.UNION_ADMIN,
        )
        return SponsorPackage.objects.create(
            name="Phase 13 Matchday Sponsorship",
            description="Matchday sponsorship package for API tests.",
            owner_type="UNION",
            owner_identifier="URU",
            owner_name="Uganda Rugby Union",
            scope_type="EVENT",
            scope_identifier="ELGON-2026",
            scope_name="Elgon Cup 2026",
            sponsor_type_allowed=SponsorPackage.SponsorTypeAllowed.BOTH,
            category="BEVERAGE",
            price_amount=Decimal("3000000.00"),
            currency="UGX",
            status=SponsorPackage.Status.APPROVED,
            created_by=created_by,
        )

    def create_approved_agreement(self, sponsor_account=None, sponsor_package=None):
        sponsor_account = sponsor_account or self.create_sponsor_account()
        sponsor_package = sponsor_package or self.create_sponsor_package()
        return SponsorAgreement.objects.create(
            sponsor_account=sponsor_account,
            sponsor_package=sponsor_package,
            agreement_type=SponsorAgreement.AgreementType.CASH,
            payment_source=SponsorAgreement.PaymentSource.PLATFORM,
            payment_model=SponsorAgreement.PaymentModel.ONE_TIME,
            total_value=Decimal("3000000.00"),
            currency="UGX",
            status=SponsorAgreement.Status.APPROVED,
            activation_rule=SponsorAgreement.ActivationRule.PAYMENT_CONFIRMED,
        )

    def test_sponsor_owner_can_create_agreement_for_approved_package(self):
        sponsor_owner = self.create_user("agreement-owner@example.com")
        sponsor_account = self.create_sponsor_account(owner=sponsor_owner)
        sponsor_package = self.create_sponsor_package()
        self.authenticate(sponsor_owner)

        response = self.client.post(
            "/api/sponsorships/agreements/",
            {
                "sponsor_account": sponsor_account.id,
                "sponsor_package": sponsor_package.id,
                "agreement_type": SponsorAgreement.AgreementType.CASH,
                "payment_source": SponsorAgreement.PaymentSource.PLATFORM,
                "payment_model": SponsorAgreement.PaymentModel.ONE_TIME,
                "total_value": "3000000.00",
                "currency": "UGX",
                "activation_rule": SponsorAgreement.ActivationRule.PAYMENT_CONFIRMED,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SponsorAgreement.objects.count(), 1)
        self.assertTrue(
            SponsorWorkflowEvent.objects.filter(
                event_type=SponsorWorkflowEvent.EventType.AGREEMENT_CREATED,
            ).exists()
        )

    def test_unrelated_fan_cannot_create_agreement_for_sponsor_account(self):
        sponsor_account = self.create_sponsor_account()
        sponsor_package = self.create_sponsor_package()
        unrelated_fan = self.create_user("unrelated-fan@example.com")
        self.authenticate(unrelated_fan)

        response = self.client.post(
            "/api/sponsorships/agreements/",
            {
                "sponsor_account": sponsor_account.id,
                "sponsor_package": sponsor_package.id,
                "total_value": "3000000.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_union_admin_can_approve_agreement(self):
        union_admin = self.create_user(
            "approve-agreement@example.com",
            role=User.Role.UNION_ADMIN,
        )
        sponsor_package = self.create_sponsor_package(created_by=union_admin)
        agreement = self.create_approved_agreement(sponsor_package=sponsor_package)
        agreement.status = SponsorAgreement.Status.SUBMITTED
        agreement.save(update_fields=["status"])
        self.authenticate(union_admin)

        response = self.client.post(
            f"/api/sponsorships/agreements/{agreement.id}/approve/",
            {"note": "Approved for Phase 13 test."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        agreement.refresh_from_db()
        self.assertEqual(agreement.status, SponsorAgreement.Status.APPROVED)
        self.assertEqual(agreement.approved_by, union_admin)

    def test_payment_confirmation_creates_revenue_distribution_and_activates_agreement(
        self,
    ):
        sponsor_owner = self.create_user("payment-sponsor@example.com")
        union_admin = self.create_user(
            "payment-union@example.com",
            role=User.Role.UNION_ADMIN,
        )
        sponsor_account = self.create_sponsor_account(owner=sponsor_owner)
        sponsor_package = self.create_sponsor_package(created_by=union_admin)
        agreement = self.create_approved_agreement(
            sponsor_account=sponsor_account,
            sponsor_package=sponsor_package,
        )
        RevenueShareRule.objects.create(
            sponsor_package=sponsor_package,
            recipient_type=RevenueShareRule.RecipientType.UNION,
            recipient_identifier="URU",
            recipient_name="Uganda Rugby Union",
            percentage=Decimal("10.00"),
        )
        payment_schedule = SponsorPaymentSchedule.objects.create(
            agreement=agreement,
            schedule_type=SponsorPaymentSchedule.ScheduleType.ONE_TIME,
            sequence_number=1,
            due_date=date.today(),
            amount_due=Decimal("3000000.00"),
            currency="UGX",
        )

        self.authenticate(sponsor_owner)
        payment_response = self.client.post(
            f"/api/sponsorships/agreements/{agreement.id}/payments/",
            {
                "payment_schedule": payment_schedule.id,
                "amount_paid": "3000000.00",
                "currency": "UGX",
                "payment_method": SponsorPayment.PaymentMethod.BANK_TRANSFER,
                "transaction_reference": "TXN-PHASE13-001",
            },
            format="json",
        )

        self.assertEqual(payment_response.status_code, status.HTTP_201_CREATED)
        payment_id = payment_response.data["payment"]["id"]

        self.authenticate(union_admin)
        confirm_response = self.client.post(
            f"/api/sponsorships/payments/{payment_id}/confirm/",
            {"note": "Payment received."},
            format="json",
        )

        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        payment = SponsorPayment.objects.get(id=payment_id)
        agreement.refresh_from_db()
        payment_schedule.refresh_from_db()

        self.assertEqual(payment.status, SponsorPayment.Status.CONFIRMED)
        self.assertEqual(payment.confirmed_by, union_admin)
        self.assertEqual(payment_schedule.status, SponsorPaymentSchedule.Status.PAID)
        self.assertEqual(agreement.status, SponsorAgreement.Status.ACTIVE)
        self.assertTrue(
            RevenueDistribution.objects.filter(
                payment=payment,
                agreement=agreement,
                recipient_name="Uganda Rugby Union",
                amount=Decimal("300000.00"),
            ).exists()
        )


@override_settings(
    FLUTTERWAVE_SECRET_KEY="FLWSECK_TEST-test-key",
    FLUTTERWAVE_SECRET_HASH="test-webhook-secret",
    FLUTTERWAVE_REDIRECT_URL="http://localhost:5173/sponsor/payment/processing",
)
class FlutterwaveSponsorPaymentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "StrongPass123"

    def create_user(self, email, role=User.Role.FAN):
        return User.objects.create_user(
            email=email,
            phone_number=None,
            password=self.password,
            first_name="Flutterwave",
            last_name="Tester",
            role=role,
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def create_sponsor_account(self, owner=None):
        owner = owner or self.create_user("flutterwave-sponsor@example.com")

        sponsor_account = SponsorAccount.objects.create(
            owner=owner,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="Flutterwave Test Sponsor",
            registration_country="UG",
            brn="BRN-FLW-001",
            tin="1234567890",
            status=SponsorAccount.Status.APPROVED,
        )

        SponsorAccountMember.objects.create(
            sponsor_account=sponsor_account,
            user=owner,
            member_role=SponsorAccountMember.MemberRole.OWNER,
        )

        return sponsor_account

    def create_sponsor_package(self, created_by=None):
        created_by = created_by or self.create_user(
            "flutterwave-union@example.com",
            role=User.Role.UNION_ADMIN,
        )

        sponsor_package = SponsorPackage.objects.create(
            name="Flutterwave Matchday Sponsorship",
            description="Flutterwave checkout test sponsorship package.",
            owner_type="UNION",
            owner_identifier="URU",
            owner_name="Uganda Rugby Union",
            scope_type="EVENT",
            scope_identifier="ELGON-2026",
            scope_name="Elgon Cup 2026",
            sponsor_type_allowed=SponsorPackage.SponsorTypeAllowed.BOTH,
            category="BANKING",
            price_amount=Decimal("3000000.00"),
            currency="UGX",
            status=SponsorPackage.Status.APPROVED,
            created_by=created_by,
        )

        RevenueShareRule.objects.create(
            sponsor_package=sponsor_package,
            recipient_type=RevenueShareRule.RecipientType.UNION,
            recipient_identifier="URU",
            recipient_name="Uganda Rugby Union",
            percentage=Decimal("10.00"),
        )

        return sponsor_package

    def create_approved_agreement(self):
        sponsor_owner = self.create_user("flutterwave-owner@example.com")
        sponsor_account = self.create_sponsor_account(owner=sponsor_owner)
        sponsor_package = self.create_sponsor_package()

        agreement = SponsorAgreement.objects.create(
            sponsor_account=sponsor_account,
            sponsor_package=sponsor_package,
            agreement_type=SponsorAgreement.AgreementType.CASH,
            payment_source=SponsorAgreement.PaymentSource.PLATFORM,
            payment_model=SponsorAgreement.PaymentModel.ONE_TIME,
            total_value=Decimal("3000000.00"),
            currency="UGX",
            status=SponsorAgreement.Status.APPROVED,
            activation_rule=SponsorAgreement.ActivationRule.PAYMENT_CONFIRMED,
            created_by=sponsor_owner,
        )

        payment_schedule = SponsorPaymentSchedule.objects.create(
            agreement=agreement,
            schedule_type=SponsorPaymentSchedule.ScheduleType.ONE_TIME,
            sequence_number=1,
            due_date=date.today(),
            amount_due=Decimal("3000000.00"),
            currency="UGX",
        )

        return sponsor_owner, agreement, payment_schedule

    def test_checkout_payload_uses_frontend_payment_processing_route(self):
        sponsor_owner, agreement, payment_schedule = self.create_approved_agreement()

        payment = SponsorPayment.objects.create(
            agreement=agreement,
            payment_schedule=payment_schedule,
            amount_paid=Decimal("3000000.00"),
            currency="UGX",
            payment_method=SponsorPayment.PaymentMethod.FLUTTERWAVE,
            provider=SponsorPayment.PaymentProvider.FLUTTERWAVE,
            transaction_reference="LOS-SPONSOR-REDIRECT-001",
            recorded_by=sponsor_owner,
        )

        payload = build_checkout_payload(payment)

        self.assertEqual(
            payload["redirect_url"],
            "http://localhost:5173/sponsor/payment/processing",
        )

    @override_settings(FLUTTERWAVE_REDIRECT_URL="")
    def test_checkout_payload_rejects_missing_frontend_redirect(self):
        sponsor_owner, agreement, payment_schedule = self.create_approved_agreement()

        payment = SponsorPayment.objects.create(
            agreement=agreement,
            payment_schedule=payment_schedule,
            amount_paid=Decimal("3000000.00"),
            currency="UGX",
            payment_method=SponsorPayment.PaymentMethod.FLUTTERWAVE,
            provider=SponsorPayment.PaymentProvider.FLUTTERWAVE,
            transaction_reference="LOS-SPONSOR-NO-REDIRECT-001",
            recorded_by=sponsor_owner,
        )

        with self.assertRaisesMessage(
            FlutterwaveError,
            "FLUTTERWAVE_REDIRECT_URL must point to the frontend "
            "sponsor payment processing page.",
        ):
            build_checkout_payload(payment)

    @patch("sponsorships.views.initialize_flutterwave_payment")
    def test_sponsor_owner_can_initialize_flutterwave_payment(
        self,
        mock_initialize_flutterwave_payment,
    ):
        sponsor_owner, agreement, payment_schedule = self.create_approved_agreement()
        self.authenticate(sponsor_owner)

        mock_initialize_flutterwave_payment.return_value = {
            "status": "success",
            "message": "Hosted Link",
            "data": {
                "link": "https://checkout.flutterwave.com/v3/hosted/pay/test-link"
            },
        }

        response = self.client.post(
            f"/api/sponsorships/agreements/{agreement.id}/flutterwave/initialize/",
            {"payment_schedule": payment_schedule.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("checkout_url", response.data)
        self.assertIn("tx_ref", response.data)

        payment = SponsorPayment.objects.get(id=response.data["payment"]["id"])

        self.assertEqual(payment.provider, SponsorPayment.PaymentProvider.FLUTTERWAVE)
        self.assertEqual(
            payment.payment_method, SponsorPayment.PaymentMethod.FLUTTERWAVE
        )
        self.assertEqual(payment.status, SponsorPayment.Status.PENDING)
        self.assertEqual(
            payment.checkout_url,
            "https://checkout.flutterwave.com/v3/hosted/pay/test-link",
        )
        self.assertTrue(payment.transaction_reference.startswith("LOS-SPONSOR-"))

    @override_settings(FLUTTERWAVE_SECRET_KEY="")
    def test_initialize_flutterwave_payment_requires_configuration(self):
        sponsor_owner, agreement, payment_schedule = self.create_approved_agreement()
        self.authenticate(sponsor_owner)

        response = self.client.post(
            f"/api/sponsorships/agreements/{agreement.id}/flutterwave/initialize/",
            {"payment_schedule": payment_schedule.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @patch("sponsorships.views.verify_flutterwave_transaction")
    def test_verify_flutterwave_payment_confirms_payment_and_activates_agreement(
        self,
        mock_verify_flutterwave_transaction,
    ):
        sponsor_owner, agreement, payment_schedule = self.create_approved_agreement()

        payment = SponsorPayment.objects.create(
            agreement=agreement,
            payment_schedule=payment_schedule,
            amount_paid=Decimal("3000000.00"),
            currency="UGX",
            payment_method=SponsorPayment.PaymentMethod.FLUTTERWAVE,
            provider=SponsorPayment.PaymentProvider.FLUTTERWAVE,
            transaction_reference="LOS-SPONSOR-VERIFY-001",
            recorded_by=sponsor_owner,
        )

        mock_verify_flutterwave_transaction.return_value = {
            "status": "success",
            "message": "Transaction fetched successfully",
            "data": {
                "id": 123456789,
                "status": "successful",
                "tx_ref": payment.transaction_reference,
                "amount": 3000000,
                "currency": "UGX",
            },
        }

        response = self.client.get(
            "/api/sponsorships/flutterwave/verify/",
            {"tx_ref": payment.transaction_reference},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        payment.refresh_from_db()
        agreement.refresh_from_db()
        payment_schedule.refresh_from_db()

        self.assertEqual(payment.status, SponsorPayment.Status.CONFIRMED)
        self.assertEqual(payment.provider_status, "successful")
        self.assertEqual(payment.provider_transaction_id, "123456789")
        self.assertEqual(agreement.status, SponsorAgreement.Status.ACTIVE)
        self.assertEqual(payment_schedule.status, SponsorPaymentSchedule.Status.PAID)
        self.assertTrue(
            RevenueDistribution.objects.filter(
                payment=payment,
                agreement=agreement,
                recipient_name="Uganda Rugby Union",
                amount=Decimal("300000.00"),
            ).exists()
        )

    @patch("sponsorships.views.verify_flutterwave_transaction")
    def test_verify_flutterwave_payment_marks_invalid_payment_as_failed(
        self,
        mock_verify_flutterwave_transaction,
    ):
        sponsor_owner, agreement, payment_schedule = self.create_approved_agreement()

        payment = SponsorPayment.objects.create(
            agreement=agreement,
            payment_schedule=payment_schedule,
            amount_paid=Decimal("3000000.00"),
            currency="UGX",
            payment_method=SponsorPayment.PaymentMethod.FLUTTERWAVE,
            provider=SponsorPayment.PaymentProvider.FLUTTERWAVE,
            transaction_reference="LOS-SPONSOR-VERIFY-FAILED",
            recorded_by=sponsor_owner,
        )

        mock_verify_flutterwave_transaction.return_value = {
            "status": "success",
            "message": "Transaction fetched successfully",
            "data": {
                "id": 123456789,
                "status": "failed",
                "tx_ref": payment.transaction_reference,
                "amount": 3000000,
                "currency": "UGX",
            },
        }

        response = self.client.get(
            "/api/sponsorships/flutterwave/verify/",
            {"tx_ref": payment.transaction_reference},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        payment.refresh_from_db()
        agreement.refresh_from_db()

        self.assertEqual(payment.status, SponsorPayment.Status.FAILED)
        self.assertNotEqual(agreement.status, SponsorAgreement.Status.ACTIVE)

    def test_flutterwave_webhook_rejects_invalid_signature(self):
        response = self.client.post(
            "/api/sponsorships/flutterwave/webhook/",
            {
                "data": {
                    "tx_ref": "LOS-SPONSOR-WEBHOOK-001",
                    "status": "successful",
                }
            },
            format="json",
            HTTP_VERIF_HASH="wrong-secret",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("sponsorships.views.verify_flutterwave_transaction")
    def test_flutterwave_webhook_confirms_payment_with_valid_signature(
        self,
        mock_verify_flutterwave_transaction,
    ):
        sponsor_owner, agreement, payment_schedule = self.create_approved_agreement()

        payment = SponsorPayment.objects.create(
            agreement=agreement,
            payment_schedule=payment_schedule,
            amount_paid=Decimal("3000000.00"),
            currency="UGX",
            payment_method=SponsorPayment.PaymentMethod.FLUTTERWAVE,
            provider=SponsorPayment.PaymentProvider.FLUTTERWAVE,
            transaction_reference="LOS-SPONSOR-WEBHOOK-001",
            recorded_by=sponsor_owner,
        )

        mock_verify_flutterwave_transaction.return_value = {
            "status": "success",
            "message": "Transaction fetched successfully",
            "data": {
                "id": 987654321,
                "status": "successful",
                "tx_ref": payment.transaction_reference,
                "amount": 3000000,
                "currency": "UGX",
            },
        }

        response = self.client.post(
            "/api/sponsorships/flutterwave/webhook/",
            {
                "event": "charge.completed",
                "data": {
                    "tx_ref": payment.transaction_reference,
                    "status": "successful",
                },
            },
            format="json",
            HTTP_VERIF_HASH="test-webhook-secret",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        payment.refresh_from_db()
        agreement.refresh_from_db()

        self.assertEqual(payment.status, SponsorPayment.Status.CONFIRMED)
        self.assertEqual(agreement.status, SponsorAgreement.Status.ACTIVE)
