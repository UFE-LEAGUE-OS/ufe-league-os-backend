from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from sponsorships.models import (
    SponsorBenefit,
    SponsorPackage,
    SponsorshipOpportunity,
    SponsorshipOwnerType,
    SponsorshipScopeType,
)


class Command(BaseCommand):
    help = (
        "Create neutral sponsorship package templates and "
        "sports-property opportunities."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()

        templates = [
            {
                "key": "community",
                "name": "Community Supporter",
                "description": (
                    "Entry-level support for community sport, local events "
                    "and recognised sporting programmes."
                ),
                "objective": SponsorPackage.Objective.COMMUNITY_IMPACT,
                "duration": SponsorPackage.DurationType.ONE_EVENT,
                "sport": SponsorPackage.Sport.COMMUNITY,
                "price": Decimal("1000000.00"),
                "allowed": SponsorPackage.SponsorTypeAllowed.BOTH,
                "exclusive": False,
                "benefits": [
                    (
                        SponsorBenefit.BenefitType.PUBLIC_RECOGNITION,
                        "Public sponsor recognition",
                    ),
                    (
                        SponsorBenefit.BenefitType.DIGITAL_BADGE,
                        "League OS supporter badge",
                    ),
                    (
                        SponsorBenefit.BenefitType.FREE_TICKETS,
                        "Complimentary ticket allocation",
                    ),
                ],
            },
            {
                "key": "grassroots",
                "name": "Grassroots Development Partner",
                "description": (
                    "Support youth, schools, women’s sport, equipment, "
                    "training and player-development programmes."
                ),
                "objective": SponsorPackage.Objective.GRASSROOTS,
                "duration": SponsorPackage.DurationType.SEASON,
                "sport": SponsorPackage.Sport.GENERAL,
                "price": Decimal("5000000.00"),
                "allowed": SponsorPackage.SponsorTypeAllowed.BOTH,
                "exclusive": False,
                "benefits": [
                    (
                        SponsorBenefit.BenefitType.PUBLIC_RECOGNITION,
                        "Development programme recognition",
                    ),
                    (
                        SponsorBenefit.BenefitType.LOGO_PLACEMENT,
                        "Programme page logo placement",
                    ),
                    (
                        SponsorBenefit.BenefitType.CAMPAIGN_ANALYTICS,
                        "Community impact summary",
                    ),
                ],
            },
            {
                "key": "digital",
                "name": "Digital Visibility Partner",
                "description": (
                    "League OS-controlled digital placements with measurable "
                    "page impressions, unique viewers and sponsor-link clicks."
                ),
                "objective": SponsorPackage.Objective.VISIBILITY,
                "duration": SponsorPackage.DurationType.MONTHLY,
                "sport": SponsorPackage.Sport.GENERAL,
                "price": Decimal("3000000.00"),
                "allowed": SponsorPackage.SponsorTypeAllowed.CORPORATE,
                "exclusive": False,
                "benefits": [
                    (
                        SponsorBenefit.BenefitType.HOMEPAGE_AD,
                        "League OS page placement",
                    ),
                    (
                        SponsorBenefit.BenefitType.FAN_DASHBOARD_AD,
                        "Fan dashboard placement",
                    ),
                    (
                        SponsorBenefit.BenefitType.CAMPAIGN_ANALYTICS,
                        "Platform-measured performance report",
                    ),
                ],
            },
            {
                "key": "matchday",
                "name": "Matchday Partner",
                "description": (
                    "A focused single-match partnership covering match-centre, "
                    "ticketing, hospitality and sponsor recognition."
                ),
                "objective": SponsorPackage.Objective.FAN_ENGAGEMENT,
                "duration": SponsorPackage.DurationType.ONE_MATCH,
                "sport": SponsorPackage.Sport.GENERAL,
                "price": Decimal("4000000.00"),
                "allowed": SponsorPackage.SponsorTypeAllowed.BOTH,
                "exclusive": False,
                "benefits": [
                    (
                        SponsorBenefit.BenefitType.LOGO_PLACEMENT,
                        "Match-centre branding",
                    ),
                    (
                        SponsorBenefit.BenefitType.VIP_ACCESS,
                        "Matchday hospitality allocation",
                    ),
                    (
                        SponsorBenefit.BenefitType.CAMPAIGN_ANALYTICS,
                        "Matchday delivery report",
                    ),
                ],
            },
            {
                "key": "competition",
                "name": "Competition Partner",
                "description": (
                    "Season or tournament visibility across fixtures, results, "
                    "standings and competition content."
                ),
                "objective": SponsorPackage.Objective.VISIBILITY,
                "duration": SponsorPackage.DurationType.SEASON,
                "sport": SponsorPackage.Sport.GENERAL,
                "price": Decimal("15000000.00"),
                "allowed": SponsorPackage.SponsorTypeAllowed.CORPORATE,
                "exclusive": False,
                "benefits": [
                    (
                        SponsorBenefit.BenefitType.LOGO_PLACEMENT,
                        "Competition page branding",
                    ),
                    (
                        SponsorBenefit.BenefitType.VIP_ACCESS,
                        "Competition hospitality allocation",
                    ),
                    (
                        SponsorBenefit.BenefitType.CAMPAIGN_ANALYTICS,
                        "Competition delivery report",
                    ),
                ],
            },
            {
                "key": "premium",
                "name": "Premium Exclusive Partner",
                "description": (
                    "A negotiated premium partnership with category "
                    "exclusivity and a custom activation plan."
                ),
                "objective": SponsorPackage.Objective.HOSPITALITY,
                "duration": SponsorPackage.DurationType.SEASON,
                "sport": SponsorPackage.Sport.GENERAL,
                "price": Decimal("30000000.00"),
                "allowed": SponsorPackage.SponsorTypeAllowed.CORPORATE,
                "exclusive": True,
                "benefits": [
                    (
                        SponsorBenefit.BenefitType.LOGO_PLACEMENT,
                        "Priority branding placement",
                    ),
                    (
                        SponsorBenefit.BenefitType.VIP_ACCESS,
                        "Premium hospitality",
                    ),
                    (
                        SponsorBenefit.BenefitType.CAMPAIGN_ANALYTICS,
                        "Detailed benefit-delivery report",
                    ),
                ],
            },
        ]

        packages = {}

        for spec in templates:
            package, _ = SponsorPackage.objects.update_or_create(
                name=spec["name"],
                is_template=True,
                defaults={
                    "description": spec["description"],
                    "objective": spec["objective"],
                    "duration_type": spec["duration"],
                    "sport": spec["sport"],
                    "owner_type": SponsorshipOwnerType.PLATFORM,
                    "owner_identifier": "league-os-marketplace",
                    "owner_name": "League OS Marketplace",
                    "scope_type": SponsorshipScopeType.PLATFORM,
                    "scope_identifier": "choose-sports-property",
                    "scope_name": "Choose a sports property",
                    "sponsor_type_allowed": spec["allowed"],
                    "category": "GENERAL",
                    "price_amount": spec["price"],
                    "currency": "UGX",
                    "is_exclusive": spec["exclusive"],
                    "requires_platform_fee": False,
                    "platform_fee_amount": Decimal("0.00"),
                    "activation_rule": (
                        SponsorPackage.ActivationRule.AFTER_FIRST_PAYMENT
                    ),
                    "status": SponsorPackage.Status.ACTIVE,
                    "approved_at": now,
                },
            )

            packages[spec["key"]] = package

            expected_benefits = []

            for benefit_type, name in spec["benefits"]:
                expected_benefits.append(name)

                SponsorBenefit.objects.update_or_create(
                    sponsor_package=package,
                    name=name,
                    defaults={
                        "benefit_type": benefit_type,
                        "description": name,
                        "quantity": 1,
                        "discount_percentage": Decimal("0.00"),
                        "value_amount": Decimal("0.00"),
                        "requires_payment_confirmation": True,
                        "is_platform_controlled": (
                            benefit_type
                            in {
                                SponsorBenefit.BenefitType.HOMEPAGE_AD,
                                SponsorBenefit.BenefitType.FAN_DASHBOARD_AD,
                                SponsorBenefit.BenefitType.CAMPAIGN_ANALYTICS,
                            }
                        ),
                    },
                )

            package.benefits.exclude(
                name__in=expected_benefits,
            ).delete()

        opportunities = [
            {
                "package": packages["community"],
                "property_type": SponsorshipScopeType.EVENT,
                "identifier": "community-sports-programme",
                "name": "Community Sports Programme",
                "sport": SponsorPackage.Sport.COMMUNITY,
                "location": "Kampala",
                "price": Decimal("1000000.00"),
            },
            {
                "package": packages["grassroots"],
                "property_type": SponsorshipScopeType.UNION,
                "identifier": "uru-grassroots",
                "name": "Uganda Rugby Grassroots Programme",
                "sport": SponsorPackage.Sport.RUGBY,
                "location": "Uganda",
                "price": Decimal("5000000.00"),
            },
            {
                "package": packages["digital"],
                "property_type": SponsorshipScopeType.PLATFORM,
                "identifier": "league-os-digital-network",
                "name": "League OS Digital Network",
                "sport": SponsorPackage.Sport.GENERAL,
                "location": "Online",
                "price": Decimal("3000000.00"),
            },
            {
                "package": packages["matchday"],
                "property_type": SponsorshipScopeType.MATCH,
                "identifier": "kobs-matchday",
                "name": "KOBS Rugby Club Matchday",
                "sport": SponsorPackage.Sport.RUGBY,
                "location": "Kampala",
                "price": Decimal("4000000.00"),
            },
            {
                "package": packages["matchday"],
                "property_type": SponsorshipScopeType.MATCH,
                "identifier": "basketball-matchday",
                "name": "National Basketball Matchday",
                "sport": SponsorPackage.Sport.BASKETBALL,
                "location": "Kampala",
                "price": Decimal("4500000.00"),
            },
            {
                "package": packages["competition"],
                "property_type": SponsorshipScopeType.COMPETITION,
                "identifier": "budo-league-season",
                "name": "Budo League Season",
                "sport": SponsorPackage.Sport.FOOTBALL,
                "location": "Kampala",
                "price": Decimal("15000000.00"),
            },
            {
                "package": packages["competition"],
                "property_type": SponsorshipScopeType.COMPETITION,
                "identifier": "national-rugby-premiership",
                "name": "National Rugby Premiership",
                "sport": SponsorPackage.Sport.RUGBY,
                "location": "Uganda",
                "price": Decimal("20000000.00"),
            },
            {
                "package": packages["premium"],
                "property_type": SponsorshipScopeType.LEAGUE,
                "identifier": "national-basketball-league",
                "name": "National Basketball League",
                "sport": SponsorPackage.Sport.BASKETBALL,
                "location": "Uganda",
                "price": Decimal("30000000.00"),
            },
        ]

        for spec in opportunities:
            SponsorshipOpportunity.objects.update_or_create(
                sponsor_package=spec["package"],
                property_identifier=spec["identifier"],
                defaults={
                    "property_type": spec["property_type"],
                    "property_name": spec["name"],
                    "sport": spec["sport"],
                    "location": spec["location"],
                    "price_amount": spec["price"],
                    "currency": "UGX",
                    "status": SponsorshipOpportunity.Status.AVAILABLE,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Created 6 neutral templates and sponsorship opportunities."
            )
        )
