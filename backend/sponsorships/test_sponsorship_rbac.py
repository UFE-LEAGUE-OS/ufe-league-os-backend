from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from sponsorships.models import SponsorAccount, SponsorAccountMember

User = get_user_model()


class SponsorshipRBACRegressionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "StrongPass123!"

    def create_fan(self, email="fan@example.com", phone_number="+256700000001"):
        return User.objects.create_user(
            email=email,
            phone_number=phone_number,
            password=self.password,
            first_name="Test",
            last_name="Fan",
            role=User.Role.FAN,
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_fan_without_sponsor_account_cannot_access_sponsor_dashboard(self):
        user = self.create_fan()
        self.authenticate(user)

        response = self.client.get("/api/dashboards/sponsor/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_fan_creates_individual_sponsor_account_and_gains_sponsor_dashboard_access(
        self,
    ):
        user = self.create_fan()
        self.authenticate(user)

        create_response = self.client.post(
            "/api/sponsorships/accounts/",
            {
                "sponsor_type": SponsorAccount.SponsorType.INDIVIDUAL,
                "name": "Test Individual Sponsor",
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        user.refresh_from_db()

        sponsor_account = SponsorAccount.objects.get(owner=user)

        self.assertEqual(user.role, User.Role.FAN)
        self.assertFalse(user.is_sponsor)
        self.assertEqual(
            sponsor_account.sponsor_type,
            SponsorAccount.SponsorType.INDIVIDUAL,
        )
        self.assertTrue(
            SponsorAccountMember.objects.filter(
                sponsor_account=sponsor_account,
                user=user,
                member_role=SponsorAccountMember.MemberRole.OWNER,
                is_active=True,
            ).exists()
        )

        dashboard_response = self.client.get("/api/dashboards/sponsor/")

        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        self.assertEqual(dashboard_response.data["role"], User.Role.FAN)
        self.assertEqual(dashboard_response.data["dashboard_role"], User.Role.SPONSOR)

        available_roles = {
            dashboard["role"]
            for dashboard in dashboard_response.data["available_dashboards"]
        }

        self.assertIn(User.Role.FAN, available_roles)
        self.assertNotIn(User.Role.SPONSOR, available_roles)
        self.assertEqual(
            dashboard_response.data["user"]["dashboard_access"],
            {
                "version": 1,
                "default_entitlement_id": "fan",
                "entitlements": [
                    {
                        "id": "fan",
                        "dashboard": "FAN",
                        "route": "/dashboard/fan",
                        "scope_type": "ACCOUNT",
                        "scope_id": user.id,
                        "workspace_role": None,
                        "permissions": [],
                    }
                ],
            },
        )

    def test_existing_user_cannot_create_duplicate_individual_sponsor_account(self):
        user = self.create_fan()
        self.authenticate(user)

        first_response = self.client.post(
            "/api/sponsorships/accounts/",
            {
                "sponsor_type": SponsorAccount.SponsorType.INDIVIDUAL,
                "name": "First Individual Sponsor",
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        duplicate_response = self.client.post(
            "/api/sponsorships/accounts/",
            {
                "sponsor_type": SponsorAccount.SponsorType.INDIVIDUAL,
                "name": "Duplicate Individual Sponsor",
            },
            format="json",
        )

        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sponsor_type", duplicate_response.data)

    def test_duplicate_corporate_brn_and_tin_are_blocked_per_country(self):
        user = self.create_fan()
        self.authenticate(user)

        first_response = self.client.post(
            "/api/sponsorships/accounts/",
            {
                "sponsor_type": SponsorAccount.SponsorType.CORPORATE,
                "name": "Nile Special",
                "registration_country": "UG",
                "brn": "BRN-TEST-001",
                "tin": "1234567890",
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        duplicate_response = self.client.post(
            "/api/sponsorships/accounts/",
            {
                "sponsor_type": SponsorAccount.SponsorType.CORPORATE,
                "name": "Duplicate Nile Special",
                "registration_country": "UG",
                "brn": "BRN-TEST-001",
                "tin": "1234567890",
            },
            format="json",
        )

        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("brn", duplicate_response.data)
        self.assertIn("tin", duplicate_response.data)

    def test_become_sponsor_shortcut_creates_real_sponsor_account(self):
        user = self.create_fan(
            email="shortcutfan@example.com",
            phone_number="+256700000002",
        )
        self.authenticate(user)

        before_response = self.client.get("/api/dashboards/sponsor/")

        self.assertEqual(before_response.status_code, status.HTTP_403_FORBIDDEN)

        become_response = self.client.post(
            "/api/accounts/become-sponsor/",
            {
                "sponsor_type": SponsorAccount.SponsorType.INDIVIDUAL,
                "name": "Shortcut Sponsor Account",
            },
            format="json",
        )

        self.assertEqual(become_response.status_code, status.HTTP_201_CREATED)
        self.assertIn("sponsor_account", become_response.data)
        self.assertIn("dashboard_routes", become_response.data)

        user.refresh_from_db()

        self.assertEqual(user.role, User.Role.FAN)
        self.assertTrue(user.is_sponsor)
        self.assertEqual(user.sponsor_type, SponsorAccount.SponsorType.INDIVIDUAL)

        sponsor_account = SponsorAccount.objects.get(owner=user)

        self.assertEqual(sponsor_account.name, "Shortcut Sponsor Account")
        self.assertEqual(
            sponsor_account.sponsor_type,
            SponsorAccount.SponsorType.INDIVIDUAL,
        )

        self.assertTrue(
            SponsorAccountMember.objects.filter(
                sponsor_account=sponsor_account,
                user=user,
                member_role=SponsorAccountMember.MemberRole.OWNER,
                is_active=True,
            ).exists()
        )

        after_response = self.client.get("/api/dashboards/sponsor/")

        self.assertEqual(after_response.status_code, status.HTTP_200_OK)
        self.assertEqual(after_response.data["dashboard_role"], User.Role.SPONSOR)

    def test_become_sponsor_shortcut_blocks_duplicate_individual_account(self):
        user = self.create_fan(
            email="duplicate-shortcut@example.com",
            phone_number="+256700000003",
        )
        self.authenticate(user)

        first_response = self.client.post(
            "/api/accounts/become-sponsor/",
            {
                "sponsor_type": SponsorAccount.SponsorType.INDIVIDUAL,
                "name": "First Shortcut Sponsor Account",
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        duplicate_response = self.client.post(
            "/api/accounts/become-sponsor/",
            {
                "sponsor_type": SponsorAccount.SponsorType.INDIVIDUAL,
                "name": "Duplicate Shortcut Sponsor Account",
            },
            format="json",
        )

        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sponsor_type", duplicate_response.data)
