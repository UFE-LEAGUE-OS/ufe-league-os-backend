"""Return due maintained player loans to their source Clubs."""

from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from dashboards.models import UnionPlayerTransfer
from dashboards.union_player_transfer_return_services import (
    process_due_player_loan_returns,
)


class Command(BaseCommand):
    help = "Return due active player loans to their source Clubs."

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
                status=UnionPlayerTransfer.Status.LOAN_ACTIVE,
                transfer_type="LOAN",
                loan_end_on__lt=as_of,
            ).order_by("loan_end_on", "id")
            due_count = queryset.count()
            if limit is not None:
                queryset = queryset[:limit]
            due = list(queryset.values_list("id", "loan_end_on"))
            self.stdout.write(
                f"Dry run as of {as_of.isoformat()}: {due_count} loan(s) due."
            )
            self.stdout.write(
                f"Transfer IDs: {[transfer_id for transfer_id, _ in due]}"
            )
            self.stdout.write(
                "Effective return dates: "
                f"{[(loan_end + timedelta(days=1)).isoformat() for _, loan_end in due]}"
            )
            return

        try:
            result = process_due_player_loan_returns(
                as_of=as_of,
                limit=limit,
            )
        except Exception as exc:
            raise CommandError("Scheduled loan-return processing failed.") from exc
        self.stdout.write(f"As of: {result['as_of'].isoformat()}")
        self.stdout.write(f"Returned: {result['returned_count']}")
        self.stdout.write(f"Failed: {result['failed_count']}")
        self.stdout.write(f"Returned transfer IDs: {result['returned_transfer_ids']}")
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
