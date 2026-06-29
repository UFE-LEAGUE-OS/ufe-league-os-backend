from decimal import Decimal

from django.conf import settings

from accounts.models import Club
from memberships.models import MembershipPlan

CLUBS = {
    "kobs": ("kobs", "KCB KOBS"),
    "villa": ("sc-villa", "SC Villa"),
    "oilers": ("city-oilers", "City Oilers"),
    "vipers": ("vipers-sc", "Vipers SC"),
    "pirates": ("black-pirates", "Black Pirates"),
    "kcca": ("kcca-fc", "KCCA FC"),
    "impis": ("impis-rfc", "IMPIS RFC"),
    "heathens": ("platinum-heathens", "Platinum Credit Heathens"),
    "blazers": ("namuwongo-blazers", "Namuwongo Blazers"),
}

PLAN_OVERRIDES = {
    "kobs-bronze": ("Bronze Member", MembershipPlan.Tier.BASIC, "50000.00"),
    "kobs-gold": ("Gold Member", MembershipPlan.Tier.GOLD, "120000.00"),
    "kobs-platinum": ("Platinum Member", MembershipPlan.Tier.PLATINUM, "250000.00"),
    "villa-bronze": ("Bronze Member", MembershipPlan.Tier.BASIC, "40000.00"),
    "villa-silver": ("Silver Member", MembershipPlan.Tier.SILVER, "80000.00"),
    "villa-gold": ("Gold Member", MembershipPlan.Tier.GOLD, "160000.00"),
    "oilers-fan": ("Fan Member", MembershipPlan.Tier.BASIC, "70000.00"),
    "oilers-courtside": ("Courtside Member", MembershipPlan.Tier.GOLD, "150000.00"),
    "vipers-fan": ("Fan Member", MembershipPlan.Tier.BASIC, "60000.00"),
    "vipers-premium": ("Premium Member", MembershipPlan.Tier.GOLD, "130000.00"),
    "pirates-bronze": ("Bronze Member", MembershipPlan.Tier.BASIC, "50000.00"),
    "pirates-gold": ("Gold Member", MembershipPlan.Tier.GOLD, "120000.00"),
    "kcca-fan": ("Fan Member", MembershipPlan.Tier.BASIC, "55000.00"),
    "kcca-family": ("Family Member", MembershipPlan.Tier.SILVER, "100000.00"),
    "impis-fan": ("Fan Member", MembershipPlan.Tier.BASIC, "40000.00"),
    "heathens-gold": ("Gold Member", MembershipPlan.Tier.GOLD, "120000.00"),
    "blazers-fan": ("Fan Member", MembershipPlan.Tier.BASIC, "60000.00"),
}


def demo_membership_checkout_is_enabled():
    return (
        getattr(settings, "MEMBERSHIP_DEMO_CHECKOUT_ENABLED", False)
        and getattr(settings, "FLUTTERWAVE_MODE", "test") == "test"
    )


def ensure_presentation_demo_membership_plan(demo_plan_code):
    code = str(demo_plan_code or "kobs-gold").strip()
    club_key = code.split("-")[0]

    club_slug, club_name = CLUBS.get(club_key, CLUBS["kobs"])
    plan_name, tier, price = PLAN_OVERRIDES.get(
        code,
        ("Gold Member", MembershipPlan.Tier.GOLD, "120000.00"),
    )

    club, _ = Club.objects.get_or_create(
        slug=club_slug,
        defaults={"name": club_name},
    )

    plan, _ = MembershipPlan.objects.update_or_create(
        club=club,
        name=plan_name,
        defaults={
            "description": f"{plan_name} presentation demo membership for {club.name}.",
            "tier": tier,
            "billing_cycle": MembershipPlan.BillingCycle.ANNUAL,
            "price_amount": Decimal(price),
            "currency": "UGX",
            "benefits": [
                "Digital membership card",
                "Club news alerts",
                "Member ticket offers",
                "Presentation demo checkout",
            ],
            "is_active": True,
            "is_visible": True,
        },
    )

    return plan
