from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from sponsorships.models import (
    SponsorAccount,
    SponsorAccountMember,
    SponsorAgreement,
    SponsorPackage,
    SponsorshipOpportunity,
    SponsorshipOwnerType,
    SponsorshipScopeType,
)

User = get_user_model()


class SponsorshipMarketplaceWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            email="marketplace-sponsor@example.com",
            password="StrongPass123",
            first_name="Marketplace",
            last_name="Sponsor",
            role=User.Role.FAN,
            is_sponsor=True,
            sponsor_type=User.SponsorType.INDIVIDUAL,
        )

        self.account = SponsorAccount.objects.create(
            owner=self.user,
            sponsor_type=SponsorAccount.SponsorType.INDIVIDUAL,
            name="Marketplace Sponsor",
            status=SponsorAccount.Status.APPROVED,
        )

        SponsorAccountMember.objects.create(
            sponsor_account=self.account,
            user=self.user,
            member_role=SponsorAccountMember.MemberRole.OWNER,
        )

        self.package = SponsorPackage.objects.create(
            name="Digital Visibility Partner",
            description="Neutral digital package.",
            is_template=True,
            objective=SponsorPackage.Objective.VISIBILITY,
            duration_type=SponsorPackage.DurationType.MONTHLY,
            sport=SponsorPackage.Sport.GENERAL,
            owner_type=SponsorshipOwnerType.PLATFORM,
            owner_identifier="league-os-marketplace",
            owner_name="League OS Marketplace",
            scope_type=SponsorshipScopeType.PLATFORM,
            scope_identifier="choose-property",
            scope_name="Choose a sports property",
            sponsor_type_allowed=SponsorPackage.SponsorTypeAllowed.BOTH,
            price_amount=Decimal("3000000.00"),
            currency="UGX",
            status=SponsorPackage.Status.ACTIVE,
        )

        self.opportunity = SponsorshipOpportunity.objects.create(
            sponsor_package=self.package,
            property_type=SponsorshipScopeType.PLATFORM,
            property_identifier="league-os-digital",
            property_name="League OS Digital Network",
            sport=SponsorPackage.Sport.GENERAL,
            location="Online",
            price_amount=Decimal("3500000.00"),
            currency="UGX",
        )

        self.client.force_authenticate(user=self.user)

    def test_package_api_filters_neutral_templates(self):
        response = self.client.get(
            "/api/sponsorships/packages/",
            {
                "is_template": "true",
                "objective": "VISIBILITY",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

        package = response.data["results"][0]

        self.assertEqual(package["name"], "Digital Visibility Partner")
        self.assertTrue(package["is_template"])
        self.assertEqual(package["objective"], "VISIBILITY")
        self.assertEqual(len(package["opportunities"]), 1)

    def test_opportunity_endpoint_lists_available_properties(self):
        response = self.client.get(
            (f"/api/sponsorships/packages/" f"{self.package.id}/opportunities/")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["property_name"],
            "League OS Digital Network",
        )

    def test_creating_opportunity_request_submits_agreement(self):
        response = self.client.post(
            "/api/sponsorships/agreements/",
            {
                "sponsor_account": self.account.id,
                "sponsor_package": self.package.id,
                "opportunity": self.opportunity.id,
                "agreement_type": "CASH",
                "payment_source": "PLATFORM",
                "payment_model": "ONE_TIME",
                "notes": "Request platform visibility.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        agreement = SponsorAgreement.objects.get(
            id=response.data["agreement"]["id"],
        )

        self.assertEqual(
            agreement.status,
            SponsorAgreement.Status.SUBMITTED,
        )
        self.assertEqual(
            agreement.opportunity,
            self.opportunity,
        )
        self.assertEqual(
            agreement.total_value,
            Decimal("3500000.00"),
        )
