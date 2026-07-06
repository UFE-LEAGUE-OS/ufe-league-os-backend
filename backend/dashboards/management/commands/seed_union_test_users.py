from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from dashboards.models import UnionWorkspace, UnionWorkspaceMembership

TEST_USERS = [
    {
        "email": "uru.owner@leagueos.test",
        "first_name": "URU",
        "last_name": "Owner",
        "workspace": "URU",
        "role": UnionWorkspaceMembership.Role.OWNER,
    },
    {
        "email": "uru.admin@leagueos.test",
        "first_name": "URU",
        "last_name": "Admin",
        "workspace": "URU",
        "role": UnionWorkspaceMembership.Role.UNION_ADMIN,
    },
    {
        "email": "uru.registrar@leagueos.test",
        "first_name": "URU",
        "last_name": "Registrar",
        "workspace": "URU",
        "role": UnionWorkspaceMembership.Role.REGISTRAR,
    },
    {
        "email": "uru.referees@leagueos.test",
        "first_name": "URU",
        "last_name": "Referees",
        "workspace": "URU",
        "role": UnionWorkspaceMembership.Role.REFEREE_MANAGER,
    },
    {
        "email": "uru.finance@leagueos.test",
        "first_name": "URU",
        "last_name": "Finance",
        "workspace": "URU",
        "role": UnionWorkspaceMembership.Role.FINANCE_OFFICER,
    },
    {
        "email": "fufa.owner@leagueos.test",
        "first_name": "FUFA",
        "last_name": "Owner",
        "workspace": "FUFA",
        "role": UnionWorkspaceMembership.Role.OWNER,
    },
    {
        "email": "fufa.competitions@leagueos.test",
        "first_name": "FUFA",
        "last_name": "Competitions",
        "workspace": "FUFA",
        "role": UnionWorkspaceMembership.Role.COMPETITIONS_MANAGER,
    },
    {
        "email": "fuba.owner@leagueos.test",
        "first_name": "FUBA",
        "last_name": "Owner",
        "workspace": "FUBA",
        "role": UnionWorkspaceMembership.Role.OWNER,
    },
    {
        "email": "fuba.registrar@leagueos.test",
        "first_name": "FUBA",
        "last_name": "Registrar",
        "workspace": "FUBA",
        "role": UnionWorkspaceMembership.Role.REGISTRAR,
    },
    {
        "email": "budo.owner@leagueos.test",
        "first_name": "Budo",
        "last_name": "Owner",
        "workspace": "BUDO",
        "role": UnionWorkspaceMembership.Role.OWNER,
    },
    {
        "email": "budo.league.admin@leagueos.test",
        "first_name": "Budo",
        "last_name": "League Admin",
        "workspace": "BUDO",
        "role": UnionWorkspaceMembership.Role.UNION_ADMIN,
    },
    {
        "email": "smack.owner@leagueos.test",
        "first_name": "SMACK",
        "last_name": "Owner",
        "workspace": "SMACK",
        "role": UnionWorkspaceMembership.Role.OWNER,
    },
    {
        "email": "smack.viewer@leagueos.test",
        "first_name": "SMACK",
        "last_name": "Viewer",
        "workspace": "SMACK",
        "role": UnionWorkspaceMembership.Role.VIEWER,
    },
]


class Command(BaseCommand):
    help = "Seed test users for Union Admin workspace permission testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="LeagueOS@2026!",
            help="Password assigned to all seeded test users.",
        )

    def handle(self, *args, **options):
        password = options["password"]
        User = get_user_model()

        missing_workspaces = []

        for item in TEST_USERS:
            if not UnionWorkspace.objects.filter(
                acronym__iexact=item["workspace"]
            ).exists():
                missing_workspaces.append(item["workspace"])

        if missing_workspaces:
            raise CommandError(
                "Missing workspaces: "
                + ", ".join(sorted(set(missing_workspaces)))
                + ". Run seed_union_workspaces first."
            )

        for item in TEST_USERS:
            user, created_user = User.objects.get_or_create(
                email=item["email"],
                defaults={
                    "first_name": item["first_name"],
                    "last_name": item["last_name"],
                    "role": User.Role.FAN,
                    "is_email_verified": True,
                },
            )

            user.first_name = item["first_name"]
            user.last_name = item["last_name"]
            user.role = User.Role.FAN
            user.is_email_verified = True
            user.set_password(password)
            user.save(
                update_fields=[
                    "first_name",
                    "last_name",
                    "role",
                    "is_email_verified",
                    "password",
                ]
            )

            workspace = UnionWorkspace.objects.get(acronym__iexact=item["workspace"])

            UnionWorkspaceMembership.objects.update_or_create(
                user=user,
                workspace=workspace,
                defaults={
                    "role": item["role"],
                    "is_active": True,
                },
            )

            action = "Created" if created_user else "Updated"

            self.stdout.write(
                self.style.SUCCESS(
                    f"{action} {item['email']} -> {workspace.acronym} as {item['role']}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(f"All test users use password: {password}")
        )
