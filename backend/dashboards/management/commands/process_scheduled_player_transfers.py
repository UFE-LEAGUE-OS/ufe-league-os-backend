"""Activate due maintained player transfers."""

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from dashboards.models import UnionPlayerTransfer
from dashboards.union_player_transfer_activation_services import (
    process_due_player_transfer_activations,
)


class Command(BaseCommand):
    help = "Activate due approved player transfers."

    def add_arguments(self, parser):
        parser.add_argument("--as-of", dest="as_of")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        as_of = self._parse_as_of(options.get("as_of"))
        limit = options.get("limit")
        if limit is not None and limit <= 0:
            raise CommandError("--limit must be a positive integer.")
        if options.get("dry_run"):
            queryset = UnionPlayerTransfer.objects.filter(
                status=UnionPlayerTransfer.Status.APPROVED,
                effective_on__lte=as_of,
            ).order_by("effective_on", "id")
            due_count = queryset.count()
            if limit is not None:
                queryset = queryset[:limit]
            transfer_ids = list(queryset.values_list("id", flat=True))
            self.stdout.write(
                f"Dry run as of {as_of.isoformat()}: {due_count} transfer(s) due."
            )
            self.stdout.write(f"Transfer IDs: {transfer_ids}")
            return

        try:
            result = process_due_player_transfer_activations(
                as_of=as_of,
                limit=limit,
            )
        except Exception as exc:
            raise CommandError("Scheduled transfer processing failed.") from exc
        self.stdout.write(f"As of: {result['as_of'].isoformat()}")
        self.stdout.write(f"Activated: {result['activated_count']}")
        self.stdout.write(f"Failed: {result['failed_count']}")
        self.stdout.write(f"Activated transfer IDs: {result['activated_transfer_ids']}")
        for failure in result["failures"]:
            self.stdout.write(f"Transfer {failure['transfer_id']}: {failure['error']}")

    @staticmethod
    def _parse_as_of(value):
        if not value:
            return timezone.localdate()
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise CommandError("--as-of must use YYYY-MM-DD.") from exc
