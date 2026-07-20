from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from sponsorships.models import SponsorAccount, SponsorAccountMember

User = get_user_model()


class SponsorDashboardContractTests(TestCase):
    password = "ValidSponsorPass123!"

    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            email="pending-sponsor@example.com",
            password=self.password,
            first_name="Pending",
            last_name="Sponsor",
            role=User.Role.FAN,
            is_email_verified=True,
            is_sponsor=True,
            sponsor_type=User.SponsorType.INDIVIDUAL,
        )

        self.account = SponsorAccount.objects.create(
            owner=self.user,
            sponsor_type=SponsorAccount.SponsorType.INDIVIDUAL,
            name=self.user.full_name,
            status=SponsorAccount.Status.PENDING,
        )

        SponsorAccountMember.objects.create(
            sponsor_account=self.account,
            user=self.user,
            member_role=SponsorAccountMember.MemberRole.OWNER,
        )

    def assert_pending_sponsor_access(self, dashboard_access):
        sponsor_entitlement = next(
            entitlement
            for entitlement in dashboard_access["entitlements"]
            if entitlement["dashboard"] == "SPONSOR"
        )

        self.assertEqual(
            sponsor_entitlement["route"],
            "/sponsor/dashboard",
        )
        self.assertEqual(
            sponsor_entitlement["scope_type"],
            "INDIVIDUAL_SPONSOR_ACCOUNT",
        )
        self.assertEqual(
            sponsor_entitlement["scope_id"],
            self.account.id,
        )
        self.assertEqual(
            sponsor_entitlement["workspace_role"],
            "OWNER",
        )
        self.assertIn(
            "sponsor.dashboard.view",
            sponsor_entitlement["permissions"],
        )
        self.assertEqual(
            dashboard_access["default_entitlement_id"],
            sponsor_entitlement["id"],
        )

    def test_login_google_and_me_return_the_same_sponsor_contract(self):
        login_response = self.client.post(
            "/api/accounts/login/",
            {
                "identifier": self.user.email,
                "password": self.password,
            },
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)

        self.client.force_authenticate(self.user)

        me_response = self.client.get("/api/accounts/me/")
        self.assertEqual(me_response.status_code, 200)

        self.client.force_authenticate(user=None)

        with patch(
            "accounts.serializers.verify_google_id_token",
            return_value={
                "email": self.user.email,
                "given_name": self.user.first_name,
                "family_name": self.user.last_name,
            },
        ):
            google_response = self.client.post(
                "/api/accounts/google/",
                {"id_token": "test-google-token"},
                format="json",
            )

        self.assertEqual(google_response.status_code, 200)

        login_access = login_response.data["user"]["dashboard_access"]
        me_access = me_response.data["dashboard_access"]
        google_access = google_response.data["user"]["dashboard_access"]

        self.assert_pending_sponsor_access(login_access)
        self.assert_pending_sponsor_access(me_access)
        self.assert_pending_sponsor_access(google_access)

        self.assertEqual(login_access, me_access)
        self.assertEqual(me_access, google_access)

        self.assertEqual(
            login_response.data["frontend_dashboard_route"],
            "/sponsor/dashboard",
        )
        self.assertEqual(
            google_response.data["frontend_dashboard_route"],
            "/sponsor/dashboard",
        )

    def test_duplicate_individual_application_keeps_expected_message(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            "/api/accounts/become-sponsor/",
            {
                "sponsor_type": SponsorAccount.SponsorType.INDIVIDUAL,
                "name": self.user.full_name,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["sponsor_type"][0],
            "You already have an individual sponsor account.",
        )

    def test_duplicate_corporate_application_has_expected_message(self):
        corporate_user = User.objects.create_user(
            email="corporate-sponsor@example.com",
            password=self.password,
            first_name="Corporate",
            last_name="Sponsor",
            role=User.Role.FAN,
            is_email_verified=True,
        )

        corporate_account = SponsorAccount.objects.create(
            owner=corporate_user,
            sponsor_type=SponsorAccount.SponsorType.CORPORATE,
            name="Existing Corporate Sponsor",
            registration_country="UG",
            tin="1000000001",
            status=SponsorAccount.Status.PENDING,
        )

        SponsorAccountMember.objects.create(
            sponsor_account=corporate_account,
            user=corporate_user,
            member_role=SponsorAccountMember.MemberRole.OWNER,
        )

        self.client.force_authenticate(corporate_user)

        response = self.client.post(
            "/api/accounts/become-sponsor/",
            {
                "sponsor_type": SponsorAccount.SponsorType.CORPORATE,
                "name": "Second Corporate Sponsor",
                "registration_country": "UG",
                "tin": "1000000002",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["sponsor_type"][0],
            "You already have a corporate sponsor account.",
        )

    def test_rejected_account_does_not_receive_sponsor_entitlement(self):
        SponsorAccount.objects.filter(pk=self.account.pk).update(
            status=SponsorAccount.Status.REJECTED,
        )

        self.client.force_authenticate(self.user)

        response = self.client.get("/api/accounts/me/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            any(
                entitlement["dashboard"] == "SPONSOR"
                for entitlement in response.data["dashboard_access"]["entitlements"]
            )
        )
