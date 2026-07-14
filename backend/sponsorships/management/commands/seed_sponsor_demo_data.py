from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from sponsorships.models import (
    SponsorAccount,
    SponsorAccountMember,
    SponsorAgreement,
    SponsorBenefit,
    SponsorCategory,
    SponsorPackage,
    SponsorPayment,
    SponsorPaymentSchedule,
    SponsorshipOwnerType,
    SponsorshipScopeType,
)


class Command(BaseCommand):
    help = (
        "Create idempotent individual and corporate sponsor demo data "
        "for frontend, QA, and staging environments."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            required=True,
            help="Password assigned to every generated demo login.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]

        if len(password) < 8:
            raise CommandError("The demo password must contain at least 8 characters.")

        today = timezone.localdate()
        now = timezone.now()

        users = self._create_users(password)

        accounts = {
            "orbimaps": self._upsert_account(
                owner=users["orbimaps_owner"],
                sponsor_type=SponsorAccount.SponsorType.CORPORATE,
                name="Orbimaps Limited",
                brn="DEMO-ORBIMAPS-BRN-2026",
                tin="DEMO-ORBIMAPS-TIN-2026",
            ),
            "nile": self._upsert_account(
                owner=users["nile_owner"],
                sponsor_type=SponsorAccount.SponsorType.CORPORATE,
                name="Nile Special Demo",
                brn="DEMO-NILE-BRN-2026",
                tin="DEMO-NILE-TIN-2026",
            ),
            "keith": self._upsert_account(
                owner=users["keith_owner"],
                sponsor_type=SponsorAccount.SponsorType.INDIVIDUAL,
                name="Keith Individual Sponsor",
            ),
            "amina": self._upsert_account(
                owner=users["amina_owner"],
                sponsor_type=SponsorAccount.SponsorType.INDIVIDUAL,
                name="Amina Individual Sponsor",
            ),
        }

        self._upsert_member(
            account=accounts["orbimaps"],
            user=users["orbimaps_finance"],
            role=SponsorAccountMember.MemberRole.FINANCE,
        )
        self._upsert_member(
            account=accounts["nile"],
            user=users["nile_admin"],
            role=SponsorAccountMember.MemberRole.ADMIN,
        )

        packages = self._create_packages(now)

        agreements = {
            "orbimaps_active": self._upsert_agreement(
                reference="DEMO-SP-ORBIMAPS-KOBS-2026",
                account=accounts["orbimaps"],
                package=packages["kobs"],
                created_by=users["orbimaps_owner"],
                total_value=Decimal("8000000.00"),
                payment_model=SponsorAgreement.PaymentModel.ONE_TIME,
                status=SponsorAgreement.Status.ACTIVE,
                benefits_tier=SponsorAgreement.BenefitsTier.DIGITAL,
                activation_rule=SponsorAgreement.ActivationRule.PAYMENT_CONFIRMED,
                starts_at=today - timedelta(days=30),
                ends_at=today + timedelta(days=335),
                approved_at=now,
            ),
            "orbimaps_submitted": self._upsert_agreement(
                reference="DEMO-SP-ORBIMAPS-COMMUNITY-2026",
                account=accounts["orbimaps"],
                package=packages["community"],
                created_by=users["orbimaps_owner"],
                total_value=Decimal("6000000.00"),
                payment_model=SponsorAgreement.PaymentModel.ONE_TIME,
                status=SponsorAgreement.Status.SUBMITTED,
                benefits_tier=SponsorAgreement.BenefitsTier.DIGITAL,
                activation_rule=SponsorAgreement.ActivationRule.ADMIN_APPROVAL,
                starts_at=today + timedelta(days=30),
                ends_at=today + timedelta(days=395),
            ),
            "nile_active": self._upsert_agreement(
                reference="DEMO-SP-NILE-RUGBY-2026",
                account=accounts["nile"],
                package=packages["rugby"],
                created_by=users["nile_owner"],
                total_value=Decimal("30000000.00"),
                payment_model=SponsorAgreement.PaymentModel.INSTALLMENT,
                status=SponsorAgreement.Status.ACTIVE,
                benefits_tier=SponsorAgreement.BenefitsTier.PREMIUM,
                activation_rule=SponsorAgreement.ActivationRule.PAYMENT_CONFIRMED,
                starts_at=today - timedelta(days=60),
                ends_at=today + timedelta(days=305),
                approved_at=now,
            ),
            "keith_active": self._upsert_agreement(
                reference="DEMO-SP-KEITH-WELFARE-2026",
                account=accounts["keith"],
                package=packages["player_welfare"],
                created_by=users["keith_owner"],
                total_value=Decimal("1500000.00"),
                payment_model=SponsorAgreement.PaymentModel.ONE_TIME,
                status=SponsorAgreement.Status.ACTIVE,
                benefits_tier=SponsorAgreement.BenefitsTier.BASIC,
                activation_rule=SponsorAgreement.ActivationRule.PAYMENT_CONFIRMED,
                starts_at=today - timedelta(days=14),
                ends_at=today + timedelta(days=351),
                approved_at=now,
            ),
            "amina_pending": self._upsert_agreement(
                reference="DEMO-SP-AMINA-COMMUNITY-2026",
                account=accounts["amina"],
                package=packages["community"],
                created_by=users["amina_owner"],
                total_value=Decimal("2000000.00"),
                payment_model=SponsorAgreement.PaymentModel.ONE_TIME,
                status=SponsorAgreement.Status.PENDING_PAYMENT,
                benefits_tier=SponsorAgreement.BenefitsTier.BASIC,
                activation_rule=SponsorAgreement.ActivationRule.PAYMENT_CONFIRMED,
                starts_at=today + timedelta(days=14),
                ends_at=today + timedelta(days=379),
                approved_at=now,
            ),
        }

        schedules = self._create_schedules(
            agreements=agreements,
            today=today,
        )

        self._create_payments(
            agreements=agreements,
            schedules=schedules,
            users=users,
            now=now,
        )

        self.stdout.write(
            self.style.SUCCESS("Sponsor demo data created or updated successfully.")
        )
        self.stdout.write("")
        self.stdout.write("Corporate sponsor owners:")
        self.stdout.write("  orbimaps.sponsor.demo@leagueos.local")
        self.stdout.write("  nile.sponsor.demo@leagueos.local")
        self.stdout.write("")
        self.stdout.write("Individual sponsors:")
        self.stdout.write("  keith.sponsor.demo@leagueos.local")
        self.stdout.write("  amina.sponsor.demo@leagueos.local")
        self.stdout.write("")
        self.stdout.write("Corporate team members:")
        self.stdout.write("  orbimaps.finance.demo@leagueos.local")
        self.stdout.write("  nile.admin.demo@leagueos.local")
        self.stdout.write("")
        self.stdout.write(
            "All generated accounts use the password supplied with --password."
        )

    def _create_users(self, password):
        user_specs = {
            "orbimaps_owner": {
                "email": "orbimaps.sponsor.demo@leagueos.local",
                "first_name": "Orbimaps",
                "last_name": "Sponsor",
                "phone_number": "+256799900101",
                "sponsor_type": User.SponsorType.CORPORATE,
            },
            "orbimaps_finance": {
                "email": "orbimaps.finance.demo@leagueos.local",
                "first_name": "Orbimaps",
                "last_name": "Finance",
                "phone_number": "+256799900102",
                "sponsor_type": User.SponsorType.CORPORATE,
            },
            "nile_owner": {
                "email": "nile.sponsor.demo@leagueos.local",
                "first_name": "Nile",
                "last_name": "Sponsor",
                "phone_number": "+256799900103",
                "sponsor_type": User.SponsorType.CORPORATE,
            },
            "nile_admin": {
                "email": "nile.admin.demo@leagueos.local",
                "first_name": "Nile",
                "last_name": "Administrator",
                "phone_number": "+256799900104",
                "sponsor_type": User.SponsorType.CORPORATE,
            },
            "keith_owner": {
                "email": "keith.sponsor.demo@leagueos.local",
                "first_name": "Keith",
                "last_name": "Sponsor",
                "phone_number": "+256799900105",
                "sponsor_type": User.SponsorType.INDIVIDUAL,
            },
            "amina_owner": {
                "email": "amina.sponsor.demo@leagueos.local",
                "first_name": "Amina",
                "last_name": "Sponsor",
                "phone_number": "+256799900106",
                "sponsor_type": User.SponsorType.INDIVIDUAL,
            },
        }

        users = {}

        for key, spec in user_specs.items():
            user, _ = User.objects.get_or_create(
                email=spec["email"],
            )

            user.first_name = spec["first_name"]
            user.last_name = spec["last_name"]
            user.phone_number = spec["phone_number"]
            user.role = User.Role.FAN
            user.is_sponsor = True
            user.sponsor_type = spec["sponsor_type"]
            user.is_email_verified = True
            user.is_phone_verified = True
            user.is_active = True
            user.set_password(password)
            user.save()

            users[key] = user

        return users

    def _upsert_account(
        self,
        *,
        owner,
        sponsor_type,
        name,
        brn=None,
        tin=None,
    ):
        account, _ = SponsorAccount.objects.update_or_create(
            owner=owner,
            name=name,
            defaults={
                "sponsor_type": sponsor_type,
                "registration_country": "UG",
                "brn": brn,
                "tin": tin,
                "status": SponsorAccount.Status.APPROVED,
            },
        )

        self._upsert_member(
            account=account,
            user=owner,
            role=SponsorAccountMember.MemberRole.OWNER,
        )

        return account

    def _upsert_member(self, *, account, user, role):
        SponsorAccountMember.objects.update_or_create(
            sponsor_account=account,
            user=user,
            defaults={
                "member_role": role,
                "is_active": True,
            },
        )

    def _create_packages(self, approved_at):
        packages = {
            "kobs": self._upsert_package(
                name="KOBS Digital Partner",
                description=(
                    "Digital visibility across KOBS club pages, "
                    "match content, and sponsor recognition areas."
                ),
                owner_type=SponsorshipOwnerType.CLUB,
                owner_identifier="kobs-rugby-club",
                owner_name="KOBS Rugby Club",
                scope_type=SponsorshipScopeType.CLUB,
                scope_identifier="kobs-rugby-club",
                scope_name="KOBS Rugby Club",
                allowed=SponsorPackage.SponsorTypeAllowed.BOTH,
                category=SponsorCategory.GENERAL,
                price=Decimal("8000000.00"),
                exclusive=False,
                activation_rule=SponsorPackage.ActivationRule.AFTER_FIRST_PAYMENT,
                approved_at=approved_at,
            ),
            "rugby": self._upsert_package(
                name="Nile Special Rugby Championship Partner",
                description=(
                    "Premium corporate partnership for national "
                    "rugby competition visibility and activations."
                ),
                owner_type=SponsorshipOwnerType.LEAGUE,
                owner_identifier="nile-special-rugby-demo",
                owner_name="Nile Special Rugby Championship",
                scope_type=SponsorshipScopeType.COMPETITION,
                scope_identifier="nile-special-rugby-demo",
                scope_name="Nile Special Rugby Championship",
                allowed=SponsorPackage.SponsorTypeAllowed.CORPORATE,
                category=SponsorCategory.BEVERAGE,
                price=Decimal("30000000.00"),
                exclusive=True,
                activation_rule=SponsorPackage.ActivationRule.AFTER_FIRST_PAYMENT,
                approved_at=approved_at,
            ),
            "player_welfare": self._upsert_package(
                name="Player Welfare Supporter",
                description=(
                    "Individual sponsorship supporting player welfare, "
                    "medical care, and development activities."
                ),
                owner_type=SponsorshipOwnerType.UNION,
                owner_identifier="uganda-rugby-union-demo",
                owner_name="Uganda Rugby Union",
                scope_type=SponsorshipScopeType.PLAYER,
                scope_identifier="rugby-player-welfare-demo",
                scope_name="Rugby Player Welfare Programme",
                allowed=SponsorPackage.SponsorTypeAllowed.INDIVIDUAL,
                category=SponsorCategory.HEALTHCARE,
                price=Decimal("1500000.00"),
                exclusive=False,
                activation_rule=SponsorPackage.ActivationRule.AFTER_FULL_PAYMENT,
                approved_at=approved_at,
            ),
            "community": self._upsert_package(
                name="Community Sports Partner",
                description=(
                    "Support community sport programmes, youth engagement, "
                    "and local competition activities."
                ),
                owner_type=SponsorshipOwnerType.PLATFORM,
                owner_identifier="league-os-community-demo",
                owner_name="League OS Community Sport",
                scope_type=SponsorshipScopeType.EVENT,
                scope_identifier="community-sport-demo",
                scope_name="Community Sports Programme",
                allowed=SponsorPackage.SponsorTypeAllowed.BOTH,
                category=SponsorCategory.EDUCATION,
                price=Decimal("6000000.00"),
                exclusive=False,
                activation_rule=SponsorPackage.ActivationRule.AFTER_ADMIN_APPROVAL,
                approved_at=approved_at,
            ),
        }

        self._upsert_benefits(
            packages["kobs"],
            [
                (
                    SponsorBenefit.BenefitType.LOGO_PLACEMENT,
                    "Digital logo placement",
                    "Logo placement across KOBS club and match pages.",
                ),
                (
                    SponsorBenefit.BenefitType.PUBLIC_RECOGNITION,
                    "Sponsor recognition",
                    "Recognition on club sponsor listings and content.",
                ),
                (
                    SponsorBenefit.BenefitType.CAMPAIGN_ANALYTICS,
                    "Campaign analytics",
                    "Access to digital sponsorship performance summaries.",
                ),
            ],
        )

        self._upsert_benefits(
            packages["rugby"],
            [
                (
                    SponsorBenefit.BenefitType.LOGO_PLACEMENT,
                    "Championship logo placement",
                    "Premium logo placement on competition pages.",
                ),
                (
                    SponsorBenefit.BenefitType.VIP_ACCESS,
                    "VIP match access",
                    "VIP access allocation for selected fixtures.",
                ),
                (
                    SponsorBenefit.BenefitType.EMAIL_CAMPAIGN,
                    "Supporter email campaign",
                    "Approved sponsor communication to supporters.",
                ),
                (
                    SponsorBenefit.BenefitType.CAMPAIGN_ANALYTICS,
                    "Advanced campaign analytics",
                    "Competition reach and engagement reporting.",
                ),
            ],
        )

        self._upsert_benefits(
            packages["player_welfare"],
            [
                (
                    SponsorBenefit.BenefitType.DIGITAL_BADGE,
                    "Player welfare supporter badge",
                    "A supporter badge displayed on the sponsor profile.",
                ),
                (
                    SponsorBenefit.BenefitType.PUBLIC_RECOGNITION,
                    "Programme recognition",
                    "Recognition as a player welfare supporter.",
                ),
            ],
        )

        self._upsert_benefits(
            packages["community"],
            [
                (
                    SponsorBenefit.BenefitType.PUBLIC_RECOGNITION,
                    "Community partner recognition",
                    "Recognition across supported community programmes.",
                ),
                (
                    SponsorBenefit.BenefitType.FREE_TICKETS,
                    "Community event tickets",
                    "Ticket allocation for selected community events.",
                ),
            ],
        )

        return packages

    def _upsert_package(
        self,
        *,
        name,
        description,
        owner_type,
        owner_identifier,
        owner_name,
        scope_type,
        scope_identifier,
        scope_name,
        allowed,
        category,
        price,
        exclusive,
        activation_rule,
        approved_at,
    ):
        package, _ = SponsorPackage.objects.update_or_create(
            owner_identifier=owner_identifier,
            name=name,
            defaults={
                "description": description,
                "owner_type": owner_type,
                "owner_name": owner_name,
                "scope_type": scope_type,
                "scope_identifier": scope_identifier,
                "scope_name": scope_name,
                "sponsor_type_allowed": allowed,
                "category": category,
                "price_amount": price,
                "currency": "UGX",
                "is_exclusive": exclusive,
                "requires_platform_fee": False,
                "platform_fee_amount": Decimal("0.00"),
                "activation_rule": activation_rule,
                "status": SponsorPackage.Status.ACTIVE,
                "approved_at": approved_at,
            },
        )

        return package

    def _upsert_benefits(self, package, benefits):
        expected_names = []

        for benefit_type, name, description in benefits:
            expected_names.append(name)

            SponsorBenefit.objects.update_or_create(
                sponsor_package=package,
                name=name,
                defaults={
                    "benefit_type": benefit_type,
                    "description": description,
                    "quantity": 1,
                    "discount_percentage": Decimal("0.00"),
                    "value_amount": Decimal("0.00"),
                    "requires_payment_confirmation": True,
                    "is_platform_controlled": False,
                },
            )

        package.benefits.exclude(
            name__in=expected_names,
        ).delete()

    def _upsert_agreement(
        self,
        *,
        reference,
        account,
        package,
        created_by,
        total_value,
        payment_model,
        status,
        benefits_tier,
        activation_rule,
        starts_at,
        ends_at,
        approved_at=None,
    ):
        agreement, _ = SponsorAgreement.objects.update_or_create(
            reference=reference,
            defaults={
                "sponsor_account": account,
                "sponsor_package": package,
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
                "activation_rule": activation_rule,
                "created_by": created_by,
                "approved_at": approved_at,
                "notes": "Seeded sponsor demonstration agreement.",
            },
        )

        return agreement

    def _create_schedules(self, *, agreements, today):
        schedules = {}

        schedules["orbimaps_active"] = self._upsert_schedule(
            agreement=agreements["orbimaps_active"],
            sequence=1,
            schedule_type=SponsorPaymentSchedule.ScheduleType.ONE_TIME,
            due_date=today - timedelta(days=20),
            amount=Decimal("8000000.00"),
            status=SponsorPaymentSchedule.Status.PARTIALLY_PAID,
        )

        schedules["orbimaps_submitted"] = self._upsert_schedule(
            agreement=agreements["orbimaps_submitted"],
            sequence=1,
            schedule_type=SponsorPaymentSchedule.ScheduleType.ONE_TIME,
            due_date=today + timedelta(days=14),
            amount=Decimal("6000000.00"),
            status=SponsorPaymentSchedule.Status.PENDING,
        )

        schedules["nile_1"] = self._upsert_schedule(
            agreement=agreements["nile_active"],
            sequence=1,
            schedule_type=SponsorPaymentSchedule.ScheduleType.INSTALLMENT,
            due_date=today - timedelta(days=30),
            amount=Decimal("10000000.00"),
            status=SponsorPaymentSchedule.Status.PAID,
        )
        schedules["nile_2"] = self._upsert_schedule(
            agreement=agreements["nile_active"],
            sequence=2,
            schedule_type=SponsorPaymentSchedule.ScheduleType.INSTALLMENT,
            due_date=today + timedelta(days=30),
            amount=Decimal("10000000.00"),
            status=SponsorPaymentSchedule.Status.PENDING,
        )
        schedules["nile_3"] = self._upsert_schedule(
            agreement=agreements["nile_active"],
            sequence=3,
            schedule_type=SponsorPaymentSchedule.ScheduleType.INSTALLMENT,
            due_date=today + timedelta(days=90),
            amount=Decimal("10000000.00"),
            status=SponsorPaymentSchedule.Status.PENDING,
        )

        schedules["keith_active"] = self._upsert_schedule(
            agreement=agreements["keith_active"],
            sequence=1,
            schedule_type=SponsorPaymentSchedule.ScheduleType.ONE_TIME,
            due_date=today - timedelta(days=10),
            amount=Decimal("1500000.00"),
            status=SponsorPaymentSchedule.Status.PAID,
        )

        schedules["amina_pending"] = self._upsert_schedule(
            agreement=agreements["amina_pending"],
            sequence=1,
            schedule_type=SponsorPaymentSchedule.ScheduleType.ONE_TIME,
            due_date=today + timedelta(days=7),
            amount=Decimal("2000000.00"),
            status=SponsorPaymentSchedule.Status.PENDING,
        )

        return schedules

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
                "amount_due": amount,
                "currency": "UGX",
                "status": status,
            },
        )

        return schedule

    def _create_payments(
        self,
        *,
        agreements,
        schedules,
        users,
        now,
    ):
        self._upsert_payment(
            reference="DEMO-SP-PAY-ORBIMAPS-001",
            agreement=agreements["orbimaps_active"],
            schedule=schedules["orbimaps_active"],
            amount=Decimal("3000000.00"),
            user=users["orbimaps_owner"],
            status=SponsorPayment.Status.CONFIRMED,
            payment_method=SponsorPayment.PaymentMethod.BANK_TRANSFER,
            provider=SponsorPayment.PaymentProvider.MANUAL,
            now=now,
        )

        self._upsert_payment(
            reference="DEMO-SP-PAY-NILE-001",
            agreement=agreements["nile_active"],
            schedule=schedules["nile_1"],
            amount=Decimal("10000000.00"),
            user=users["nile_owner"],
            status=SponsorPayment.Status.CONFIRMED,
            payment_method=SponsorPayment.PaymentMethod.BANK_TRANSFER,
            provider=SponsorPayment.PaymentProvider.MANUAL,
            now=now,
        )

        self._upsert_payment(
            reference="DEMO-SP-PAY-KEITH-001",
            agreement=agreements["keith_active"],
            schedule=schedules["keith_active"],
            amount=Decimal("1500000.00"),
            user=users["keith_owner"],
            status=SponsorPayment.Status.CONFIRMED,
            payment_method=SponsorPayment.PaymentMethod.MOBILE_MONEY,
            provider=SponsorPayment.PaymentProvider.MANUAL,
            now=now,
        )

        self._upsert_payment(
            reference="DEMO-SP-PAY-AMINA-PENDING",
            agreement=agreements["amina_pending"],
            schedule=schedules["amina_pending"],
            amount=Decimal("2000000.00"),
            user=users["amina_owner"],
            status=SponsorPayment.Status.PENDING,
            payment_method=SponsorPayment.PaymentMethod.FLUTTERWAVE,
            provider=SponsorPayment.PaymentProvider.FLUTTERWAVE,
            now=now,
        )

    def _upsert_payment(
        self,
        *,
        reference,
        agreement,
        schedule,
        amount,
        user,
        status,
        payment_method,
        provider,
        now,
    ):
        confirmed = status == SponsorPayment.Status.CONFIRMED

        SponsorPayment.objects.update_or_create(
            transaction_reference=reference,
            defaults={
                "agreement": agreement,
                "payment_schedule": schedule,
                "amount_paid": amount,
                "currency": "UGX",
                "payment_method": payment_method,
                "provider": provider,
                "provider_status": ("successful" if confirmed else "pending"),
                "provider_response": {
                    "seeded": True,
                    "reference": reference,
                },
                "paid_at": now if confirmed else None,
                "status": status,
                "notes": "Seeded sponsor demonstration payment.",
                "recorded_by": user,
                "confirmed_by": user if confirmed else None,
                "confirmed_at": now if confirmed else None,
            },
        )
