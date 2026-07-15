from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Club, User
from .models import MembershipPlan, MembershipSubscription


class MembershipClubAdminAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "StrongPass123"

    def create_user(self, email, role):
        return User.objects.create_user(
            email=email,
            phone_number=None,
            password=self.password,
            first_name="Test",
            last_name="Admin",
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

        access_token = login_response.data["access"]

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

    def test_club_admin_can_create_category(self):
        user = self.create_user(
            "club-admin-membership@example.com", User.Role.CLUB_ADMIN
        )
        self.authenticate(user)

        club = Club.objects.create(
            name="Test FC",
            slug="test-fc",
            sport="FOOTBALL",
        )

        response = self.client.post(
            "/api/memberships/club-admin/categories/",
            {
                "club": club.id,
                "name": "Gold Membership",
                "tier": MembershipPlan.Tier.GOLD,
                "billing_cycle": MembershipPlan.BillingCycle.ANNUAL,
                "price_amount": 150000,
                "currency": "UGX",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["plan"]["name"], "Gold Membership")
        self.assertEqual(response.data["plan"]["tier"], MembershipPlan.Tier.GOLD)

    def test_club_admin_can_list_and_filter_members(self):
        user = self.create_user("club-admin-filter@example.com", User.Role.CLUB_ADMIN)
        self.authenticate(user)

        club = Club.objects.create(
            name="Filter FC",
            slug="filter-fc",
            sport="FOOTBALL",
        )
        plan = MembershipPlan.objects.create(
            club=club,
            name="Basic Plan",
            tier=MembershipPlan.Tier.BASIC,
            billing_cycle=MembershipPlan.BillingCycle.MONTHLY,
            price_amount=25000,
        )

        active_user = User.objects.create_user(
            email="active-member@example.com",
            phone_number=None,
            password="StrongPass123",
            first_name="Active",
            last_name="Member",
            role=User.Role.FAN,
        )
        expired_user = User.objects.create_user(
            email="expired-member@example.com",
            phone_number=None,
            password="StrongPass123",
            first_name="Expired",
            last_name="Member",
            role=User.Role.FAN,
        )

        MembershipSubscription.objects.create(
            user=active_user,
            plan=plan,
            club=club,
            status=MembershipSubscription.Status.ACTIVE,
        )
        MembershipSubscription.objects.create(
            user=expired_user,
            plan=plan,
            club=club,
            status=MembershipSubscription.Status.EXPIRED,
        )

        response = self.client.get(
            "/api/memberships/club-admin/members/directory/",
            {"club": club.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

        active_response = self.client.get(
            "/api/memberships/club-admin/members/directory/",
            {"club": club.id, "status": MembershipSubscription.Status.ACTIVE},
        )

        self.assertEqual(active_response.status_code, status.HTTP_200_OK)
        self.assertEqual(active_response.data["count"], 1)

    def test_club_admin_can_approve_and_reject_requests(self):
        user = self.create_user("club-admin-requests@example.com", User.Role.CLUB_ADMIN)
        self.authenticate(user)

        club = Club.objects.create(
            name="Requests FC",
            slug="requests-fc",
            sport="FOOTBALL",
        )
        plan = MembershipPlan.objects.create(
            club=club,
            name="Standard Plan",
            tier=MembershipPlan.Tier.SILVER,
            billing_cycle=MembershipPlan.BillingCycle.MONTHLY,
            price_amount=50000,
        )
        requester = User.objects.create_user(
            email="requester@example.com",
            phone_number=None,
            password="StrongPass123",
            first_name="Requester",
            last_name="User",
            role=User.Role.FAN,
        )

        subscription = MembershipSubscription.objects.create(
            user=requester,
            plan=plan,
            club=club,
            status=MembershipSubscription.Status.PENDING_PAYMENT,
        )

        approve_response = self.client.post(
            "/api/memberships/club-admin/requests/",
            {
                "subscription_id": subscription.id,
                "action": "approve",
                "reason": "",
            },
            format="json",
        )

        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, MembershipSubscription.Status.ACTIVE)

        reject_response = self.client.post(
            "/api/memberships/club-admin/requests/",
            {
                "subscription_id": subscription.id,
                "action": "reject",
                "reason": "Missing documents",
            },
            format="json",
        )

        self.assertEqual(reject_response.status_code, status.HTTP_200_OK)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, MembershipSubscription.Status.CANCELLED)

    def test_club_admin_can_update_membership_category(self):
        user = self.create_user("club-admin-category@example.com", User.Role.CLUB_ADMIN)
        self.authenticate(user)

        club = Club.objects.create(
            name="Category FC",
            slug="category-fc",
            sport="FOOTBALL",
        )
        plan = MembershipPlan.objects.create(
            club=club,
            name="Old Name",
            tier=MembershipPlan.Tier.BASIC,
            billing_cycle=MembershipPlan.BillingCycle.MONTHLY,
            price_amount=25000,
        )

        response = self.client.patch(
            f"/api/memberships/club-admin/categories/{plan.id}/",
            {"price_amount": 35000, "name": "New Name"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        plan.refresh_from_db()
        self.assertEqual(plan.price_amount, 35000)
        self.assertEqual(plan.name, "New Name")

    def test_membership_reports_export_csv(self):
        user = self.create_user("club-admin-reports@example.com", User.Role.CLUB_ADMIN)
        self.authenticate(user)

        club = Club.objects.create(
            name="Reports FC",
            slug="reports-fc",
            sport="FOOTBALL",
        )
        plan = MembershipPlan.objects.create(
            club=club,
            name="Standard Plan",
            tier=MembershipPlan.Tier.SILVER,
            billing_cycle=MembershipPlan.BillingCycle.MONTHLY,
            price_amount=50000,
        )
        subscriber = User.objects.create_user(
            email="subscriber@example.com",
            phone_number=None,
            password="StrongPass123",
            first_name="Subscriber",
            last_name="User",
            role=User.Role.FAN,
        )
        MembershipSubscription.objects.create(
            user=subscriber,
            plan=plan,
            club=club,
            status=MembershipSubscription.Status.ACTIVE,
            starts_at=timezone.now() - timedelta(days=30),
            ends_at=timezone.now() + timedelta(days=30),
        )

        response = self.client.get(
            "/api/memberships/club-admin/reports/export/",
            {"club": club.id, "format": "csv"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("membership-report.csv", response["Content-Disposition"])
