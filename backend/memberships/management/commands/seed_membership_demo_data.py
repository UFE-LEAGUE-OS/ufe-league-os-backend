from decimal import Decimal

from django.core.management.base import BaseCommand

from accounts.models import Club, User
from memberships.models import MembershipPlan


class Command(BaseCommand):
    help = "Create demo club membership plans and a demo fan for staged Flutterwave testing."

    def handle(self, *args, **options):
        fan, _ = User.objects.get_or_create(
            email="fan-demo@example.com",
            defaults={
                "username": "fan-demo",
                "first_name": "Demo",
                "last_name": "Fan",
                "role": User.Role.FAN,
                "is_email_verified": True,
            },
        )
        fan.set_password("StrongPass123!")
        fan.is_email_verified = True
        fan.save()

        club, _ = Club.objects.get_or_create(
            slug="kobs",
            defaults={"name": "KCB KOBS"},
        )

        plans = [
            ("Bronze Member", MembershipPlan.Tier.BASIC, Decimal("50000.00")),
            ("Gold Member", MembershipPlan.Tier.GOLD, Decimal("120000.00")),
            ("Platinum Member", MembershipPlan.Tier.PLATINUM, Decimal("250000.00")),
        ]

        created_plans = []

        for name, tier, price in plans:
            plan, _ = MembershipPlan.objects.update_or_create(
                club=club,
                name=name,
                defaults={
                    "description": f"{name} demo membership for KCB KOBS.",
                    "tier": tier,
                    "billing_cycle": MembershipPlan.BillingCycle.ANNUAL,
                    "price_amount": price,
                    "currency": "UGX",
                    "benefits": [
                        "Digital membership card",
                        "Club news alerts",
                        "Member ticket offers",
                    ],
                    "is_active": True,
                    "is_visible": True,
                },
            )
            created_plans.append(plan)

        self.stdout.write(self.style.SUCCESS("Demo membership data created."))
        self.stdout.write("")
        self.stdout.write("Demo fan login:")
        self.stdout.write("  email: fan-demo@example.com")
        self.stdout.write("  password: StrongPass123!")
        self.stdout.write("")
        self.stdout.write("Demo club:")
        self.stdout.write(f"  id: {club.id}")
        self.stdout.write(f"  slug: {club.slug}")
        self.stdout.write(f"  name: {club.name}")
        self.stdout.write("")
        self.stdout.write("Demo membership plans:")
        for plan in created_plans:
            self.stdout.write(
                f"  {plan.name} id: {plan.id} price: {plan.price_amount} {plan.currency}"
            )
