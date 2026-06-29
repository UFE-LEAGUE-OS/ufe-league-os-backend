from django.core.management.base import BaseCommand
from django.utils import timezone

from ticketing.models import TicketOrder
from ticketing.services.orders import expire_stale_ticket_reservations


class Command(BaseCommand):
    help = "Expire unpaid ticket reservations whose reservation window has passed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many reservations would be expired without changing data.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()

        expired_queryset = TicketOrder.objects.filter(
            status=TicketOrder.Status.PENDING,
            reservation_released_at__isnull=True,
            reservation_expires_at__isnull=False,
            reservation_expires_at__lte=now,
        )

        expired_count = expired_queryset.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run complete. {expired_count} reservation(s) would expire."
                )
            )
            return

        expired_count = expire_stale_ticket_reservations(now=now)

        self.stdout.write(
            self.style.SUCCESS(f"Expired {expired_count} unpaid ticket reservation(s).")
        )
