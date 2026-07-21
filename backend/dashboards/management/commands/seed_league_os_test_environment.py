import json
from datetime import datetime, timezone
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import (
    BaseCommand,
    CommandError,
    call_command,
    get_commands,
)
from django.db import transaction

TEST_PASSWORD = "StrongPass123!"

COVERAGE_SEED_STEPS = [
    (
        "seed_league_os_demo",
        {
            "demo_password": TEST_PASSWORD,
        },
    ),
    (
        "seed_union_workspaces",
        {},
    ),
    (
        "seed_union_test_users",
        {
            "password": TEST_PASSWORD,
        },
    ),
    (
        "seed_union_operations_demo_data",
        {},
    ),
    (
        "seed_union_finance_demo_data",
        {},
    ),
    (
        "seed_membership_demo_data",
        {},
    ),
    (
        "seed_ticketing_demo_data",
        {},
    ),
    (
        "seed_sponsor_demo_data",
        {
            "password": TEST_PASSWORD,
        },
    ),
    (
        "seed_sponsorship_marketplace",
        {},
    ),
    (
        "seed_sponsorship_workflow_demo",
        {},
    ),
    (
        "seed_fantasy_demo_data",
        {},
    ),
]

OPTIONAL_COVERAGE_COMMANDS = [
    "seed_union_workflow_coverage",
]

RESET_COMMAND = "clear_league_os_test_environment"
VOLUME_COMMAND = "seed_league_os_volume_data"


class Command(BaseCommand):
    help = (
        "Seed a comprehensive deterministic League OS test environment by "
        "orchestrating the maintained module seed commands."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--profile",
            choices=("coverage", "volume"),
            default="coverage",
            help=(
                "coverage creates broad workflow-state coverage. "
                "volume additionally creates pagination and performance data."
            ),
        )
        parser.add_argument(
            "--reset-demo",
            action="store_true",
            help=(
                "Delete records owned by the comprehensive test seeder before "
                "recreating them. This requires the dedicated cleanup command."
            ),
        )
        parser.add_argument(
            "--output-dir",
            default=".local-test-data",
            help="Directory for generated credentials and record-count reports.",
        )
        parser.add_argument(
            "--skip-credentials",
            action="store_true",
            help="Do not generate the consolidated test-credentials files.",
        )
        parser.add_argument(
            "--skip-reports",
            action="store_true",
            help="Do not generate the model record-count report.",
        )
        parser.add_argument(
            "--allow-nonlocal",
            action="store_true",
            help=(
                "Allow execution against a non-local database such as a Neon "
                "staging branch. This does not permit production databases."
            ),
        )
        parser.add_argument(
            "--allow-production",
            action="store_true",
            help=(
                "Explicitly permit a database whose name or host appears to be "
                "production. Use only for an intentionally disposable database."
            ),
        )

    def handle(self, *args, **options):
        profile = options["profile"]
        output_dir = Path(options["output_dir"])

        self._validate_database_target(
            allow_nonlocal=options["allow_nonlocal"],
            allow_production=options["allow_production"],
        )

        available_commands = get_commands()

        if options["reset_demo"]:
            if RESET_COMMAND not in available_commands:
                raise CommandError(
                    "--reset-demo is not available yet because "
                    f"{RESET_COMMAND} has not been implemented. "
                    "Run the idempotent coverage seed without --reset-demo."
                )

            self.stdout.write(
                self.style.WARNING(
                    "Removing records owned by the comprehensive demo seeder..."
                )
            )
            call_command(RESET_COMMAND)

        if profile == "volume" and VOLUME_COMMAND not in available_commands:
            raise CommandError(
                "The volume profile has not been implemented yet. "
                "Use --profile coverage until seed_league_os_volume_data exists."
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(f"Seeding League OS test environment: {profile}")
        )
        self.stdout.write("")

        with transaction.atomic():
            for command_name, command_options in COVERAGE_SEED_STEPS:
                self._run_required_command(
                    command_name=command_name,
                    command_options=command_options,
                    available_commands=available_commands,
                )

            for command_name in OPTIONAL_COVERAGE_COMMANDS:
                self._run_optional_command(
                    command_name=command_name,
                    available_commands=available_commands,
                )

            if profile == "volume":
                self._run_required_command(
                    command_name=VOLUME_COMMAND,
                    command_options={},
                    available_commands=available_commands,
                )

        output_dir.mkdir(parents=True, exist_ok=True)

        if not options["skip_credentials"]:
            credentials_path = output_dir / "league-os-test-credentials.csv"

            self.stdout.write("")
            self.stdout.write(
                self.style.MIGRATE_LABEL("Generating consolidated test credentials...")
            )

            call_command(
                "seed_full_test_credentials",
                output=str(credentials_path),
            )

        if not options["skip_reports"]:
            report_path = output_dir / "league-os-seed-record-counts.json"
            self._write_record_count_report(
                report_path=report_path,
                profile=profile,
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS("League OS test environment seeded successfully.")
        )
        self.stdout.write(f"Profile: {profile}")
        self.stdout.write(f"Reports: {output_dir.resolve()}")

    def _run_required_command(
        self,
        *,
        command_name,
        command_options,
        available_commands,
    ):
        if command_name not in available_commands:
            raise CommandError(f"Required seed command is unavailable: {command_name}")

        self.stdout.write(self.style.MIGRATE_LABEL(f"Running {command_name}..."))
        call_command(
            command_name,
            **command_options,
        )

    def _run_optional_command(self, *, command_name, available_commands):
        if command_name not in available_commands:
            self.stdout.write(
                self.style.WARNING(
                    f"Optional coverage command not available yet: " f"{command_name}"
                )
            )
            return

        self.stdout.write(self.style.MIGRATE_LABEL(f"Running {command_name}..."))
        call_command(command_name)

    def _validate_database_target(
        self,
        *,
        allow_nonlocal,
        allow_production,
    ):
        database = settings.DATABASES["default"]

        database_name = str(database.get("NAME") or "")
        database_host = str(database.get("HOST") or "")
        normalized_name = database_name.lower()
        normalized_host = database_host.lower()

        local_hosts = {
            "",
            "db",
            "localhost",
            "127.0.0.1",
            "::1",
        }

        looks_nonlocal = normalized_host not in local_hosts
        looks_production = any(
            marker in normalized_name or marker in normalized_host
            for marker in (
                "production",
                "-prod",
                "_prod",
                ".prod",
            )
        )

        self.stdout.write(
            f"Database target: "
            f"{database_name or '<unnamed>'}"
            f"@{database_host or '<local>'}"
        )

        if looks_production and not allow_production:
            raise CommandError(
                "Refusing to seed a database that appears to be production. "
                "Use a staging/UAT database instead."
            )

        if looks_nonlocal and not allow_nonlocal:
            raise CommandError(
                "Refusing to seed a non-local database without " "--allow-nonlocal."
            )

    def _write_record_count_report(self, *, report_path, profile):
        counts = {}

        for model in apps.get_models():
            model_label = model._meta.label_lower

            try:
                counts[model_label] = model.objects.count()
            except Exception as exc:
                counts[model_label] = {
                    "error": str(exc),
                }

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "profile": profile,
            "database": {
                "engine": settings.DATABASES["default"].get("ENGINE"),
                "name": settings.DATABASES["default"].get("NAME"),
                "host": settings.DATABASES["default"].get("HOST"),
                "port": settings.DATABASES["default"].get("PORT"),
            },
            "model_counts": dict(sorted(counts.items())),
        }

        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        self.stdout.write(
            self.style.SUCCESS(f"Record-count report written to {report_path}")
        )
