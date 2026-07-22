from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import User
from sponsorships.models import (
    SponsorAccount,
    SponsorAccountMember,
    SponsorAgreement,
    SponsorPackage,
    SponsorPayment,
    SponsorPaymentSchedule,
)


class SeedSponsorDemoDataTests(TestCase):
    password = "SponsorDemo2026!"

    def run_seed(self):
        output = StringIO()

        call_command(
            "seed_sponsor_demo_data",
            password=self.password,
            stdout=output,
        )

        return output.getvalue()

    def test_command_creates_repeatable_sponsor_demo_data(self):
        output = self.run_seed()

        expected_emails = [
            "orbimaps.sponsor.demo@leagueos.local",
            "orbimaps.finance.demo@leagueos.local",
            "nile.sponsor.demo@leagueos.local",
            "nile.admin.demo@leagueos.local",
            "keith.sponsor.demo@leagueos.local",
            "amina.sponsor.demo@leagueos.local",
        ]

        self.assertEqual(
            User.objects.filter(
                email__in=expected_emails,
            ).count(),
            6,
        )

        for email in expected_emails:
            user = User.objects.get(email=email)

            self.assertTrue(user.check_password(self.password))
            self.assertTrue(user.is_sponsor)
            self.assertTrue(user.is_email_verified)

        expected_accounts = [
            "Orbimaps Limited",
            "Nile Special Demo",
            "Keith Individual Sponsor",
            "Amina Individual Sponsor",
        ]

        self.assertEqual(
            SponsorAccount.objects.filter(
                name__in=expected_accounts,
            ).count(),
            4,
        )

        orbimaps = SponsorAccount.objects.get(
            name="Orbimaps Limited",
        )

        self.assertEqual(
            orbimaps.members.filter(
                is_active=True,
            ).count(),
            2,
        )

        self.assertTrue(
            orbimaps.members.filter(
                member_role=SponsorAccountMember.MemberRole.FINANCE,
                user__email="orbimaps.finance.demo@leagueos.local",
            ).exists()
        )

        package_names = [
            "KOBS Digital Partner",
            "Nile Special Rugby Championship Partner",
            "Player Welfare Supporter",
            "Community Sports Partner",
        ]

        self.assertEqual(
            SponsorPackage.objects.filter(
                name__in=package_names,
            ).count(),
            4,
        )

        agreement_references = [
            "DEMO-SP-ORBIMAPS-KOBS-2026",
            "DEMO-SP-ORBIMAPS-COMMUNITY-2026",
            "DEMO-SP-NILE-RUGBY-2026",
            "DEMO-SP-KEITH-WELFARE-2026",
            "DEMO-SP-AMINA-COMMUNITY-2026",
        ]

        self.assertEqual(
            SponsorAgreement.objects.filter(
                reference__in=agreement_references,
            ).count(),
            5,
        )

        self.assertEqual(
            SponsorAgreement.objects.filter(
                reference__in=agreement_references,
                status=SponsorAgreement.Status.ACTIVE,
            ).count(),
            3,
        )

        payment_references = [
            "DEMO-SP-PAY-ORBIMAPS-001",
            "DEMO-SP-PAY-NILE-001",
            "DEMO-SP-PAY-KEITH-001",
            "DEMO-SP-PAY-AMINA-PENDING",
        ]

        self.assertEqual(
            SponsorPayment.objects.filter(
                transaction_reference__in=payment_references,
            ).count(),
            4,
        )

        self.assertEqual(
            SponsorPayment.objects.filter(
                transaction_reference__in=payment_references,
                status=SponsorPayment.Status.CONFIRMED,
            ).count(),
            3,
        )

        self.assertEqual(
            SponsorPaymentSchedule.objects.filter(
                agreement__reference__in=agreement_references,
            ).count(),
            7,
        )

        self.assertIn(
            "Sponsor demo data created or updated successfully.",
            output,
        )

        counts_before = {
            "users": User.objects.filter(
                email__in=expected_emails,
            ).count(),
            "accounts": SponsorAccount.objects.filter(
                name__in=expected_accounts,
            ).count(),
            "packages": SponsorPackage.objects.filter(
                name__in=package_names,
            ).count(),
            "agreements": SponsorAgreement.objects.filter(
                reference__in=agreement_references,
            ).count(),
            "payments": SponsorPayment.objects.filter(
                transaction_reference__in=payment_references,
            ).count(),
        }

        self.run_seed()

        counts_after = {
            "users": User.objects.filter(
                email__in=expected_emails,
            ).count(),
            "accounts": SponsorAccount.objects.filter(
                name__in=expected_accounts,
            ).count(),
            "packages": SponsorPackage.objects.filter(
                name__in=package_names,
            ).count(),
            "agreements": SponsorAgreement.objects.filter(
                reference__in=agreement_references,
            ).count(),
            "payments": SponsorPayment.objects.filter(
                transaction_reference__in=payment_references,
            ).count(),
        }

        self.assertEqual(
            counts_before,
            counts_after,
        )
