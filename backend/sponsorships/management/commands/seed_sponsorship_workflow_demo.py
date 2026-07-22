from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from sponsorships.models import (
    SponsorAccount,
    SponsorAgreement,
    SponsorPackage,
    SponsorPayment,
    SponsorPaymentSchedule,
    SponsorshipOpportunity,
    SponsorshipScopeType,
)

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Create idempotent opportunity-linked sponsorship agreements, "
        "payment schedules and payments for marketplace workflow testing."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        # Ensure the six neutral package templates and their base
        # opportunities exist before adding richer workflow data.
        call_command(
            "seed_sponsorship_marketplace",
            verbosity=0,
        )

        today = timezone.localdate()
        now = timezone.now()

        packages = {
            "community": self._get_package(
                "Community Supporter",
            ),
            "grassroots": self._get_package(
                "Grassroots Development Partner",
            ),
            "digital": self._get_package(
                "Digital Visibility Partner",
            ),
            "matchday": self._get_package(
                "Matchday Partner",
            ),
            "competition": self._get_package(
                "Competition Partner",
            ),
            "premium": self._get_package(
                "Premium Exclusive Partner",
            ),
        }

        opportunities = self._create_opportunities(
            packages=packages,
            today=today,
        )

        accounts = {
            "orbimaps": self._get_account(
                "orbimaps.sponsor.demo@leagueos.local",
            ),
            "nile": self._get_account(
                "nile.sponsor.demo@leagueos.local",
            ),
            "keith": self._get_account(
                "keith.sponsor.demo@leagueos.local",
            ),
            "amina": self._get_account(
                "amina.sponsor.demo@leagueos.local",
            ),
        }

        approver = User.objects.filter(is_superuser=True).order_by("id").first()

        agreements = {
            "orbimaps_digital_active": self._upsert_agreement(
                reference="DEMO-MKT-ORBIMAPS-DIGITAL-ACTIVE",
                account=accounts["orbimaps"],
                package=packages["digital"],
                opportunity=opportunities["digital_network"],
                status=SponsorAgreement.Status.ACTIVE,
                payment_model=SponsorAgreement.PaymentModel.ONE_TIME,
                total_value=Decimal("3000000.00"),
                benefits_tier=SponsorAgreement.BenefitsTier.DIGITAL,
                starts_at=today - timedelta(days=15),
                ends_at=today + timedelta(days=15),
                approver=approver,
                now=now,
            ),
            "orbimaps_budo_approved": self._upsert_agreement(
                reference="DEMO-MKT-ORBIMAPS-BUDO-APPROVED",
                account=accounts["orbimaps"],
                package=packages["competition"],
                opportunity=opportunities["budo_league"],
                status=SponsorAgreement.Status.APPROVED,
                payment_model=SponsorAgreement.PaymentModel.ONE_TIME,
                total_value=Decimal("15000000.00"),
                benefits_tier=SponsorAgreement.BenefitsTier.PREMIUM,
                starts_at=today + timedelta(days=30),
                ends_at=today + timedelta(days=395),
                approver=approver,
                now=now,
            ),
            "nile_basketball_pending": self._upsert_agreement(
                reference="DEMO-MKT-NILE-BASKETBALL-PENDING",
                account=accounts["nile"],
                package=packages["premium"],
                opportunity=opportunities["basketball_league"],
                status=SponsorAgreement.Status.PENDING_PAYMENT,
                payment_model=SponsorAgreement.PaymentModel.INSTALLMENT,
                total_value=Decimal("30000000.00"),
                benefits_tier=SponsorAgreement.BenefitsTier.PREMIUM,
                starts_at=today + timedelta(days=21),
                ends_at=today + timedelta(days=386),
                approver=approver,
                now=now,
            ),
            "nile_rugby_submitted": self._upsert_agreement(
                reference="DEMO-MKT-NILE-RUGBY-SUBMITTED",
                account=accounts["nile"],
                package=packages["competition"],
                opportunity=opportunities["rugby_premiership"],
                status=SponsorAgreement.Status.SUBMITTED,
                payment_model=SponsorAgreement.PaymentModel.ONE_TIME,
                total_value=Decimal("20000000.00"),
                benefits_tier=SponsorAgreement.BenefitsTier.PREMIUM,
                starts_at=today + timedelta(days=14),
                ends_at=today + timedelta(days=379),
                approver=None,
                now=now,
            ),
            "keith_community_active": self._upsert_agreement(
                reference="DEMO-MKT-KEITH-COMMUNITY-ACTIVE",
                account=accounts["keith"],
                package=packages["community"],
                opportunity=opportunities["community_programme"],
                status=SponsorAgreement.Status.ACTIVE,
                payment_model=SponsorAgreement.PaymentModel.ONE_TIME,
                total_value=Decimal("1000000.00"),
                benefits_tier=SponsorAgreement.BenefitsTier.BASIC,
                starts_at=today - timedelta(days=10),
                ends_at=today + timedelta(days=20),
                approver=approver,
                now=now,
            ),
            "amina_matchday_pending": self._upsert_agreement(
                reference="DEMO-MKT-AMINA-MATCHDAY-PENDING",
                account=accounts["amina"],
                package=packages["matchday"],
                opportunity=opportunities["kobs_matchday"],
                status=SponsorAgreement.Status.PENDING_PAYMENT,
                payment_model=SponsorAgreement.PaymentModel.ONE_TIME,
                total_value=Decimal("4000000.00"),
                benefits_tier=SponsorAgreement.BenefitsTier.BASIC,
                starts_at=today + timedelta(days=10),
                ends_at=today + timedelta(days=10),
                approver=approver,
                now=now,
            ),
            "amina_grassroots_submitted": self._upsert_agreement(
                reference="DEMO-MKT-AMINA-GRASSROOTS-SUBMITTED",
                account=accounts["amina"],
                package=packages["grassroots"],
                opportunity=opportunities["uru_grassroots"],
                status=SponsorAgreement.Status.SUBMITTED,
                payment_model=SponsorAgreement.PaymentModel.ONE_TIME,
                total_value=Decimal("5000000.00"),
                benefits_tier=SponsorAgreement.BenefitsTier.BASIC,
                starts_at=today + timedelta(days=25),
                ends_at=today + timedelta(days=390),
                approver=None,
                now=now,
            ),
        }

        schedules = {
            "orbimaps_digital": self._upsert_schedule(
                agreement=agreements["orbimaps_digital_active"],
                sequence=1,
                schedule_type=SponsorPaymentSchedule.ScheduleType.ONE_TIME,
                due_date=today - timedelta(days=14),
                amount=Decimal("3000000.00"),
                status=SponsorPaymentSchedule.Status.PAID,
            ),
            "orbimaps_budo": self._upsert_schedule(
                agreement=agreements["orbimaps_budo_approved"],
                sequence=1,
                schedule_type=SponsorPaymentSchedule.ScheduleType.ONE_TIME,
                due_date=today + timedelta(days=7),
                amount=Decimal("15000000.00"),
                status=SponsorPaymentSchedule.Status.PENDING,
            ),
            "nile_1": self._upsert_schedule(
                agreement=agreements["nile_basketball_pending"],
                sequence=1,
                schedule_type=SponsorPaymentSchedule.ScheduleType.INSTALLMENT,
                due_date=today + timedelta(days=7),
                amount=Decimal("10000000.00"),
                status=SponsorPaymentSchedule.Status.PENDING,
            ),
            "nile_2": self._upsert_schedule(
                agreement=agreements["nile_basketball_pending"],
                sequence=2,
                schedule_type=SponsorPaymentSchedule.ScheduleType.INSTALLMENT,
                due_date=today + timedelta(days=67),
                amount=Decimal("10000000.00"),
                status=SponsorPaymentSchedule.Status.PENDING,
            ),
            "nile_3": self._upsert_schedule(
                agreement=agreements["nile_basketball_pending"],
                sequence=3,
                schedule_type=SponsorPaymentSchedule.ScheduleType.INSTALLMENT,
                due_date=today + timedelta(days=127),
                amount=Decimal("10000000.00"),
                status=SponsorPaymentSchedule.Status.PENDING,
            ),
            "keith_community": self._upsert_schedule(
                agreement=agreements["keith_community_active"],
                sequence=1,
                schedule_type=SponsorPaymentSchedule.ScheduleType.ONE_TIME,
                due_date=today - timedelta(days=9),
                amount=Decimal("1000000.00"),
                status=SponsorPaymentSchedule.Status.PAID,
            ),
            "amina_matchday": self._upsert_schedule(
                agreement=agreements["amina_matchday_pending"],
                sequence=1,
                schedule_type=SponsorPaymentSchedule.ScheduleType.ONE_TIME,
                due_date=today + timedelta(days=5),
                amount=Decimal("4000000.00"),
                status=SponsorPaymentSchedule.Status.PENDING,
            ),
        }

        self._upsert_payment(
            reference="DEMO-MKT-PAY-ORBIMAPS-DIGITAL",
            agreement=agreements["orbimaps_digital_active"],
            schedule=schedules["orbimaps_digital"],
            amount=Decimal("3000000.00"),
            recorded_by=accounts["orbimaps"].owner,
            method=SponsorPayment.PaymentMethod.BANK_TRANSFER,
            now=now,
        )

        self._upsert_payment(
            reference="DEMO-MKT-PAY-KEITH-COMMUNITY",
            agreement=agreements["keith_community_active"],
            schedule=schedules["keith_community"],
            amount=Decimal("1000000.00"),
            recorded_by=accounts["keith"].owner,
            method=SponsorPayment.PaymentMethod.MOBILE_MONEY,
            now=now,
        )

        template_count = SponsorPackage.objects.filter(
            is_template=True,
        ).count()
        opportunity_count = SponsorshipOpportunity.objects.filter(
            sponsor_package__is_template=True,
        ).count()
        agreement_count = SponsorAgreement.objects.filter(
            reference__startswith="DEMO-MKT-",
        ).count()
        schedule_count = SponsorPaymentSchedule.objects.filter(
            agreement__reference__startswith="DEMO-MKT-",
        ).count()
        payment_count = SponsorPayment.objects.filter(
            transaction_reference__startswith="DEMO-MKT-",
        ).count()

        self.stdout.write(
            self.style.SUCCESS(
                "Sponsorship marketplace workflow demo data created or updated."
            )
        )
        self.stdout.write(f"Templates: {template_count}")
        self.stdout.write(f"Marketplace opportunities: {opportunity_count}")
        self.stdout.write(f"Marketplace agreements: {agreement_count}")
        self.stdout.write(f"Marketplace schedules: {schedule_count}")
        self.stdout.write(f"Marketplace payments: {payment_count}")

    def _get_package(self, name):
        package = SponsorPackage.objects.filter(
            name=name,
            is_template=True,
        ).first()

        if package is None:
            raise CommandError(
                (
                    f"Neutral package template '{name}' was not found. "
                    "Run seed_sponsorship_marketplace first."
                )
            )

        return package

    def _get_account(self, owner_email):
        account = (
            SponsorAccount.objects.select_related("owner")
            .filter(owner__email__iexact=owner_email)
            .first()
        )

        if account is None:
            raise CommandError(
                (
                    f"Sponsor demo account for '{owner_email}' was not found. "
                    "Run seed_sponsor_demo_data first."
                )
            )

        return account

    def _create_opportunities(self, *, packages, today):
        specs = [
            {
                "key": "community_programme",
                "package": packages["community"],
                "property_type": SponsorshipScopeType.EVENT,
                "identifier": "community-sports-programme",
                "name": "Community Sports Programme",
                "sport": SponsorPackage.Sport.COMMUNITY,
                "location": "Kampala",
                "price": Decimal("1000000.00"),
                "start": -10,
                "end": 20,
            },
            {
                "key": "girls_festival",
                "package": packages["community"],
                "property_type": SponsorshipScopeType.EVENT,
                "identifier": "kampala-girls-sport-festival",
                "name": "Kampala Girls in Sport Festival",
                "sport": SponsorPackage.Sport.COMMUNITY,
                "location": "Kampala",
                "price": Decimal("1200000.00"),
                "start": 40,
                "end": 41,
            },
            {
                "key": "gulu_youth",
                "package": packages["community"],
                "property_type": SponsorshipScopeType.EVENT,
                "identifier": "gulu-youth-sports-festival",
                "name": "Gulu Youth Sports Festival",
                "sport": SponsorPackage.Sport.COMMUNITY,
                "location": "Gulu",
                "price": Decimal("1500000.00"),
                "start": 65,
                "end": 67,
            },
            {
                "key": "uru_grassroots",
                "package": packages["grassroots"],
                "property_type": SponsorshipScopeType.UNION,
                "identifier": "uru-grassroots",
                "name": "Uganda Rugby Grassroots Programme",
                "sport": SponsorPackage.Sport.RUGBY,
                "location": "Uganda",
                "price": Decimal("5000000.00"),
                "start": 25,
                "end": 390,
            },
            {
                "key": "fufa_schools",
                "package": packages["grassroots"],
                "property_type": SponsorshipScopeType.UNION,
                "identifier": "fufa-schools-football",
                "name": "FUFA Schools Football Programme",
                "sport": SponsorPackage.Sport.FOOTBALL,
                "location": "Uganda",
                "price": Decimal("6000000.00"),
                "start": 35,
                "end": 400,
            },
            {
                "key": "fuba_schools",
                "package": packages["grassroots"],
                "property_type": SponsorshipScopeType.UNION,
                "identifier": "fuba-schools-basketball",
                "name": "FUBA Schools Basketball Programme",
                "sport": SponsorPackage.Sport.BASKETBALL,
                "location": "Uganda",
                "price": Decimal("5500000.00"),
                "start": 28,
                "end": 393,
            },
            {
                "key": "women_development",
                "package": packages["grassroots"],
                "property_type": SponsorshipScopeType.EVENT,
                "identifier": "women-sport-development",
                "name": "Women in Sport Development Series",
                "sport": SponsorPackage.Sport.GENERAL,
                "location": "Uganda",
                "price": Decimal("7000000.00"),
                "start": 45,
                "end": 225,
            },
            {
                "key": "digital_network",
                "package": packages["digital"],
                "property_type": SponsorshipScopeType.PLATFORM,
                "identifier": "league-os-digital-network",
                "name": "League OS Digital Network",
                "sport": SponsorPackage.Sport.GENERAL,
                "location": "Online",
                "price": Decimal("3000000.00"),
                "start": -15,
                "end": 15,
            },
            {
                "key": "fan_dashboard_network",
                "package": packages["digital"],
                "property_type": SponsorshipScopeType.PLATFORM,
                "identifier": "league-os-fan-dashboard-network",
                "name": "League OS Fan Dashboard Network",
                "sport": SponsorPackage.Sport.GENERAL,
                "location": "Online",
                "price": Decimal("3500000.00"),
                "start": 7,
                "end": 37,
            },
            {
                "key": "competition_pages",
                "package": packages["digital"],
                "property_type": SponsorshipScopeType.PLATFORM,
                "identifier": "league-os-competition-pages",
                "name": "League OS Competition Pages",
                "sport": SponsorPackage.Sport.GENERAL,
                "location": "Online",
                "price": Decimal("4000000.00"),
                "start": 10,
                "end": 40,
            },
            {
                "key": "kobs_matchday",
                "package": packages["matchday"],
                "property_type": SponsorshipScopeType.MATCH,
                "identifier": "kobs-matchday",
                "name": "KOBS Rugby Club Matchday",
                "sport": SponsorPackage.Sport.RUGBY,
                "location": "Kampala",
                "price": Decimal("4000000.00"),
                "start": 10,
                "end": 10,
            },
            {
                "key": "basketball_matchday",
                "package": packages["matchday"],
                "property_type": SponsorshipScopeType.MATCH,
                "identifier": "basketball-matchday",
                "name": "National Basketball Matchday",
                "sport": SponsorPackage.Sport.BASKETBALL,
                "location": "Kampala",
                "price": Decimal("4500000.00"),
                "start": 18,
                "end": 18,
            },
            {
                "key": "football_matchday",
                "package": packages["matchday"],
                "property_type": SponsorshipScopeType.MATCH,
                "identifier": "fufa-premier-matchday",
                "name": "Uganda Premier League Matchday",
                "sport": SponsorPackage.Sport.FOOTBALL,
                "location": "Kampala",
                "price": Decimal("5000000.00"),
                "start": 24,
                "end": 24,
            },
            {
                "key": "rugby_sevens_matchday",
                "package": packages["matchday"],
                "property_type": SponsorshipScopeType.MATCH,
                "identifier": "rugby-sevens-matchday",
                "name": "Uganda Rugby Sevens Matchday",
                "sport": SponsorPackage.Sport.RUGBY,
                "location": "Jinja",
                "price": Decimal("5500000.00"),
                "start": 31,
                "end": 31,
            },
            {
                "key": "budo_league",
                "package": packages["competition"],
                "property_type": SponsorshipScopeType.COMPETITION,
                "identifier": "budo-league-season",
                "name": "Budo League Season",
                "sport": SponsorPackage.Sport.FOOTBALL,
                "location": "Kampala",
                "price": Decimal("15000000.00"),
                "start": 30,
                "end": 395,
            },
            {
                "key": "rugby_premiership",
                "package": packages["competition"],
                "property_type": SponsorshipScopeType.COMPETITION,
                "identifier": "national-rugby-premiership",
                "name": "National Rugby Premiership",
                "sport": SponsorPackage.Sport.RUGBY,
                "location": "Uganda",
                "price": Decimal("20000000.00"),
                "start": 14,
                "end": 379,
            },
            {
                "key": "basketball_playoffs",
                "package": packages["competition"],
                "property_type": SponsorshipScopeType.COMPETITION,
                "identifier": "national-basketball-playoffs",
                "name": "National Basketball Playoffs",
                "sport": SponsorPackage.Sport.BASKETBALL,
                "location": "Kampala",
                "price": Decimal("18000000.00"),
                "start": 75,
                "end": 105,
            },
            {
                "key": "smack_league",
                "package": packages["competition"],
                "property_type": SponsorshipScopeType.COMPETITION,
                "identifier": "smack-league-season",
                "name": "SMACK League Season",
                "sport": SponsorPackage.Sport.FOOTBALL,
                "location": "Kampala",
                "price": Decimal("14000000.00"),
                "start": 42,
                "end": 407,
            },
            {
                "key": "basketball_league",
                "package": packages["premium"],
                "property_type": SponsorshipScopeType.LEAGUE,
                "identifier": "national-basketball-league",
                "name": "National Basketball League",
                "sport": SponsorPackage.Sport.BASKETBALL,
                "location": "Uganda",
                "price": Decimal("30000000.00"),
                "start": 21,
                "end": 386,
            },
            {
                "key": "rugby_union_season",
                "package": packages["premium"],
                "property_type": SponsorshipScopeType.UNION,
                "identifier": "uganda-rugby-union-season",
                "name": "Uganda Rugby Union Season",
                "sport": SponsorPackage.Sport.RUGBY,
                "location": "Uganda",
                "price": Decimal("35000000.00"),
                "start": 20,
                "end": 385,
            },
            {
                "key": "football_federation_season",
                "package": packages["premium"],
                "property_type": SponsorshipScopeType.UNION,
                "identifier": "uganda-football-federation-season",
                "name": "Uganda Football Federation Season",
                "sport": SponsorPackage.Sport.FOOTBALL,
                "location": "Uganda",
                "price": Decimal("40000000.00"),
                "start": 20,
                "end": 385,
            },
        ]

        opportunities = {}

        for spec in specs:
            opportunity, _ = SponsorshipOpportunity.objects.update_or_create(
                sponsor_package=spec["package"],
                property_identifier=spec["identifier"],
                defaults={
                    "property_type": spec["property_type"],
                    "property_name": spec["name"],
                    "sport": spec["sport"],
                    "location": spec["location"],
                    "price_amount": spec["price"],
                    "currency": "UGX",
                    "starts_at": today + timedelta(days=spec["start"]),
                    "ends_at": today + timedelta(days=spec["end"]),
                    "status": SponsorshipOpportunity.Status.AVAILABLE,
                },
            )

            opportunities[spec["key"]] = opportunity

        return opportunities

    def _upsert_agreement(
        self,
        *,
        reference,
        account,
        package,
        opportunity,
        status,
        payment_model,
        total_value,
        benefits_tier,
        starts_at,
        ends_at,
        approver,
        now,
    ):
        approved = status in {
            SponsorAgreement.Status.APPROVED,
            SponsorAgreement.Status.PENDING_PAYMENT,
            SponsorAgreement.Status.ACTIVE,
        }

        agreement, _ = SponsorAgreement.objects.update_or_create(
            reference=reference,
            defaults={
                "sponsor_account": account,
                "sponsor_package": package,
                "opportunity": opportunity,
                "agreement_type": SponsorAgreement.AgreementType.CASH,
                "payment_source": SponsorAgreement.PaymentSource.PLATFORM,
                "payment_model": payment_model,
                "total_value": total_value,
                "currency": "UGX",
                "starts_at": starts_at,
                "ends_at": ends_at,
                "status": status,
                "platform_fee_required": False,
                "platform_fee_amount": Decimal("0.00"),
                "platform_fee_status": (
                    SponsorAgreement.PlatformFeeStatus.NOT_REQUIRED
                ),
                "platform_activation_allowed": (
                    status == SponsorAgreement.Status.ACTIVE
                ),
                "benefits_tier": benefits_tier,
                "activation_rule": (SponsorAgreement.ActivationRule.PAYMENT_CONFIRMED),
                "created_by": account.owner,
                "approved_by": approver if approved else None,
                "approved_at": now if approved else None,
                "notes": (
                    "Seeded opportunity-linked sponsorship marketplace "
                    "workflow agreement."
                ),
            },
        )

        return agreement

    def _upsert_schedule(
        self,
        *,
        agreement,
        sequence,
        schedule_type,
        due_date,
        amount,
        status,
    ):
        schedule, _ = SponsorPaymentSchedule.objects.update_or_create(
            agreement=agreement,
            sequence_number=sequence,
            defaults={
                "schedule_type": schedule_type,
                "due_date": due_date,
                "period_start": agreement.starts_at,
                "period_end": agreement.ends_at,
                "amount_due": amount,
                "currency": "UGX",
                "status": status,
            },
        )

        return schedule

    def _upsert_payment(
        self,
        *,
        reference,
        agreement,
        schedule,
        amount,
        recorded_by,
        method,
        now,
    ):
        payment, _ = SponsorPayment.objects.update_or_create(
            transaction_reference=reference,
            defaults={
                "agreement": agreement,
                "payment_schedule": schedule,
                "amount_paid": amount,
                "currency": "UGX",
                "payment_method": method,
                "provider": SponsorPayment.PaymentProvider.MANUAL,
                "provider_status": "successful",
                "provider_response": {
                    "seeded": True,
                    "workflow": "sponsorship-marketplace",
                    "reference": reference,
                },
                "paid_at": now,
                "status": SponsorPayment.Status.CONFIRMED,
                "notes": ("Seeded confirmed sponsorship marketplace payment."),
                "recorded_by": recorded_by,
                "confirmed_by": recorded_by,
                "confirmed_at": now,
            },
        )

        return payment
