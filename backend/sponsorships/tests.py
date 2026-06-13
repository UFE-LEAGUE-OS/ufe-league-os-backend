from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
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

        self.assertEqual(
            sponsor_account.sponsor_type,
            SponsorAccount.SponsorType.CORPORATE,
        )
        self.assertEqual(sponsor_account.registration_country, "UG")
        self.assertEqual(sponsor_account.brn, "BRN-API-001")
        self.assertEqual(sponsor_account.tin, "1000000001")

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
