from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from dashboards.models import UnionWorkspace, UnionWorkspaceMembership
from monitoring.models import PaymentAudit, TransactionReconciliation

User = get_user_model()

DEMO_KEY = "union_finance_demo"


class Command(BaseCommand):
    help = "Seed realistic union finance demo data for all active union/federation workspaces."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-reset",
            action="store_true",
            help="Do not delete existing demo finance records before seeding.",
        )

    def handle(self, *args, **options):
        reset = not options["no_reset"]

        workspaces = UnionWorkspace.objects.filter(
            status=UnionWorkspace.Status.ACTIVE,
        ).order_by("acronym")

        if not workspaces.exists():
            self.stdout.write(self.style.WARNING("No active union workspaces found."))
            return

        total_audits = 0
        total_reconciliations = 0

        for workspace_index, workspace in enumerate(workspaces, start=1):
            if reset:
                PaymentAudit.objects.filter(
                    metadata__demo_key=DEMO_KEY,
                    metadata__workspace_slug=workspace.slug,
                ).delete()

                TransactionReconciliation.objects.filter(
                    metadata__demo_key=DEMO_KEY,
                    metadata__workspace_slug=workspace.slug,
                ).delete()

            actor = self._get_actor(workspace)

            amount_multiplier = Decimal(str(1 + (workspace_index * 0.13)))

            payment_rows = [
                {
                    "source": PaymentAudit.PaymentSource.TICKETING,
                    "event": PaymentAudit.EventType.COMPLETED,
                    "stream": "Ticketing",
                    "label": f"{workspace.acronym} match ticket sales",
                    "amount": Decimal("7600000.00") * amount_multiplier,
                    "status": "SETTLED",
                    "days_ago": 2,
                },
                {
                    "source": PaymentAudit.PaymentSource.MEMBERSHIP,
                    "event": PaymentAudit.EventType.COMPLETED,
                    "stream": "Memberships",
                    "label": f"{workspace.acronym} club membership payments",
                    "amount": Decimal("4800000.00") * amount_multiplier,
                    "status": "SETTLED",
                    "days_ago": 7,
                },
                {
                    "source": PaymentAudit.PaymentSource.SPONSORSHIP,
                    "event": PaymentAudit.EventType.INITIATED,
                    "stream": "Sponsorships",
                    "label": f"{workspace.acronym} sponsor campaign payment",
                    "amount": Decimal("5100000.00") * amount_multiplier,
                    "status": "PENDING_REVIEW",
                    "days_ago": 12,
                },
                {
                    "source": PaymentAudit.PaymentSource.WALLET,
                    "event": PaymentAudit.EventType.COMPLETED,
                    "stream": "Registrations",
                    "label": f"{workspace.acronym} player registration fees",
                    "amount": Decimal("900000.00") * amount_multiplier,
                    "status": "RECONCILE",
                    "days_ago": 20,
                },
                {
                    "source": PaymentAudit.PaymentSource.TICKETING,
                    "event": PaymentAudit.EventType.FAILED,
                    "stream": "Ticketing",
                    "label": f"{workspace.acronym} failed checkout",
                    "amount": Decimal("320000.00") * amount_multiplier,
                    "status": "FAILED",
                    "days_ago": 29,
                },
                {
                    "source": PaymentAudit.PaymentSource.SPONSORSHIP,
                    "event": PaymentAudit.EventType.COMPLETED,
                    "stream": "Sponsorships",
                    "label": f"{workspace.acronym} package settlement",
                    "amount": Decimal("2500000.00") * amount_multiplier,
                    "status": "SETTLED",
                    "days_ago": 42,
                },
            ]

            for row_index, row in enumerate(payment_rows, start=1):
                reference = f"UFIN-{workspace.acronym}-{row_index:03d}"

                audit = PaymentAudit.objects.create(
                    user=actor,
                    payment_source=row["source"],
                    event_type=row["event"],
                    amount=row["amount"].quantize(Decimal("0.01")),
                    currency="UGX",
                    reference=reference,
                    provider="Flutterwave",
                    provider_reference=f"FLW-{workspace.acronym}-{row_index:04d}",
                    status=row["status"],
                    metadata={
                        "demo_key": DEMO_KEY,
                        "workspace_slug": workspace.slug,
                        "workspace_acronym": workspace.acronym,
                        "workspace_name": workspace.name,
                        "revenue_stream": row["stream"],
                        "source_label": row["label"],
                    },
                )

                PaymentAudit.objects.filter(pk=audit.pk).update(
                    created_at=timezone.now() - timedelta(days=row["days_ago"])
                )

                total_audits += 1

            payout_rows = [
                {
                    "beneficiary": workspace.name,
                    "category": "Union share",
                    "amount": Decimal("1600000.00") * amount_multiplier,
                    "status": TransactionReconciliation.Status.MATCHED,
                    "notes": "Ready for payout confirmation.",
                    "days_ago": 1,
                },
                {
                    "beneficiary": f"{workspace.acronym} Club Pool",
                    "category": "Ticket settlement",
                    "amount": Decimal("620000.00") * amount_multiplier,
                    "status": TransactionReconciliation.Status.PENDING,
                    "notes": "Club beneficiary split awaiting review.",
                    "days_ago": 3,
                },
                {
                    "beneficiary": f"{workspace.acronym} Match Officials Pool",
                    "category": "Allowances",
                    "amount": Decimal("580000.00") * amount_multiplier,
                    "status": TransactionReconciliation.Status.PENDING,
                    "notes": "Match official allowance batch awaiting finance review.",
                    "days_ago": 5,
                },
            ]

            for row_index, row in enumerate(payout_rows, start=1):
                reference = f"UPAY-{workspace.acronym}-{row_index:03d}"

                TransactionReconciliation.objects.create(
                    transaction_date=timezone.localdate()
                    - timedelta(days=row["days_ago"]),
                    source_system="UNION_FINANCE",
                    external_reference=f"EXT-{reference}",
                    internal_reference=reference,
                    amount=row["amount"].quantize(Decimal("0.01")),
                    currency="UGX",
                    status=row["status"],
                    is_verified=row["status"]
                    == TransactionReconciliation.Status.MATCHED,
                    verified_by=(
                        actor
                        if row["status"] == TransactionReconciliation.Status.MATCHED
                        else None
                    ),
                    notes=row["notes"],
                    metadata={
                        "demo_key": DEMO_KEY,
                        "workspace_slug": workspace.slug,
                        "workspace_acronym": workspace.acronym,
                        "workspace_name": workspace.name,
                        "beneficiary": row["beneficiary"],
                        "category": row["category"],
                        "payout_status": row["status"],
                    },
                )

                total_reconciliations += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {total_audits} finance audit records and "
                f"{total_reconciliations} payout/reconciliation records."
            )
        )

    def _get_actor(self, workspace):
        membership = (
            UnionWorkspaceMembership.objects.filter(
                workspace=workspace,
                is_active=True,
            )
            .select_related("user")
            .order_by("role")
            .first()
        )

        if membership:
            return membership.user

        user = User.objects.filter(is_active=True).order_by("id").first()

        if user:
            return user

        return User.objects.create_user(
            email="finance.seed@leagueos.test",
            password="LeagueOS@2026!",
            first_name="Finance",
            last_name="Seed",
            role=User.Role.FAN,
            is_email_verified=True,
        )
