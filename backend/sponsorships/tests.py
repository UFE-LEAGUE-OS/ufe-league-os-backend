from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

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
