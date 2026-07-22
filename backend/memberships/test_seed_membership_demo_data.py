from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import Club, User
from memberships.models import MembershipPlan


class SeedMembershipDemoDataTests(TestCase):
    fan_email = "fan-demo@example.com"
    plan_names = [
        "Bronze Member",
        "Gold Member",
        "Platinum Member",
    ]

    def run_seed(self):
        output = StringIO()

        call_command(
            "seed_membership_demo_data",
            stdout=output,
        )

        return output.getvalue()

    def get_demo_plans(self, club):
        return MembershipPlan.objects.filter(
            club=club,
            name__in=self.plan_names,
        )

    def test_seed_creates_membership_fan_club_and_plans(self):
        output = self.run_seed()

        fan = User.objects.get(email=self.fan_email)
        club = Club.objects.get(slug="kobs")

        self.assertEqual(fan.first_name, "Demo")
        self.assertEqual(fan.last_name, "Fan")
        self.assertEqual(fan.role, User.Role.FAN)
        self.assertTrue(fan.is_email_verified)
        self.assertTrue(fan.check_password("StrongPass123!"))

        self.assertEqual(self.get_demo_plans(club).count(), 3)
        self.assertIn(
            "Demo membership data created.",
            output,
        )

    def test_seed_is_idempotent(self):
        self.run_seed()
        self.run_seed()

        self.assertEqual(
            User.objects.filter(
                email=self.fan_email,
            ).count(),
            1,
        )

        club = Club.objects.get(slug="kobs")

        self.assertEqual(
            Club.objects.filter(
                name="KCB KOBS",
            ).count(),
            1,
        )
        self.assertEqual(self.get_demo_plans(club).count(), 3)

    def test_seed_reuses_existing_club_with_legacy_slug(self):
        legacy_club = Club.objects.create(
            name="KCB KOBS",
            slug="kcb-kobs",
            short_name="KOBS",
            sport=Club.Sport.RUGBY,
        )

        self.run_seed()

        self.assertEqual(
            Club.objects.filter(
                name="KCB KOBS",
            ).count(),
            1,
        )
        self.assertEqual(
            self.get_demo_plans(legacy_club).count(),
            3,
        )
