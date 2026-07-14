from django.core.management import call_command
from django.test import TestCase

from sponsorships.models import (
    SponsorAgreement,
    SponsorPackage,
    SponsorPayment,
    SponsorPaymentSchedule,
    SponsorshipOpportunity,
)


class SeedSponsorshipWorkflowDemoTests(TestCase):
    def test_command_creates_idempotent_marketplace_workflow_data(self):
        call_command(
            "seed_sponsor_demo_data",
            password="DemoPass123!",
            verbosity=0,
        )

        call_command(
            "seed_sponsorship_workflow_demo",
            verbosity=0,
        )

        self.assertEqual(
            SponsorPackage.objects.filter(
                is_template=True,
            ).count(),
            6,
        )
        self.assertEqual(
            SponsorshipOpportunity.objects.filter(
                sponsor_package__is_template=True,
            ).count(),
            21,
        )
        self.assertEqual(
            SponsorAgreement.objects.filter(
                reference__startswith="DEMO-MKT-",
            ).count(),
            7,
        )
        self.assertEqual(
            SponsorAgreement.objects.filter(
                reference__startswith="DEMO-MKT-",
                opportunity__isnull=False,
            ).count(),
            7,
        )
        self.assertEqual(
            SponsorAgreement.objects.filter(
                reference__startswith="DEMO-MKT-",
                status=SponsorAgreement.Status.ACTIVE,
            ).count(),
            2,
        )
        self.assertEqual(
            SponsorAgreement.objects.filter(
                reference__startswith="DEMO-MKT-",
                status=SponsorAgreement.Status.APPROVED,
            ).count(),
            1,
        )
        self.assertEqual(
            SponsorAgreement.objects.filter(
                reference__startswith="DEMO-MKT-",
                status=SponsorAgreement.Status.PENDING_PAYMENT,
            ).count(),
            2,
        )
        self.assertEqual(
            SponsorAgreement.objects.filter(
                reference__startswith="DEMO-MKT-",
                status=SponsorAgreement.Status.SUBMITTED,
            ).count(),
            2,
        )
        self.assertEqual(
            SponsorPaymentSchedule.objects.filter(
                agreement__reference__startswith="DEMO-MKT-",
            ).count(),
            7,
        )
        self.assertEqual(
            SponsorPayment.objects.filter(
                transaction_reference__startswith="DEMO-MKT-",
            ).count(),
            2,
        )

        call_command(
            "seed_sponsorship_workflow_demo",
            verbosity=0,
        )

        self.assertEqual(
            SponsorshipOpportunity.objects.filter(
                sponsor_package__is_template=True,
            ).count(),
            21,
        )
        self.assertEqual(
            SponsorAgreement.objects.filter(
                reference__startswith="DEMO-MKT-",
            ).count(),
            7,
        )
        self.assertEqual(
            SponsorPaymentSchedule.objects.filter(
                agreement__reference__startswith="DEMO-MKT-",
            ).count(),
            7,
        )
        self.assertEqual(
            SponsorPayment.objects.filter(
                transaction_reference__startswith="DEMO-MKT-",
            ).count(),
            2,
        )
