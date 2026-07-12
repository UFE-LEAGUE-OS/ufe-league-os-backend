import csv
import secrets
import string
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from accounts.models import Club
from accounts.rbac import (
    get_backend_dashboard_route,
    get_dashboard_route,
)
from dashboards.models import (
    Competition,
    League,
    LeagueAdminScope,
    UnionWorkspace,
    UnionWorkspaceMembership,
)


TEST_DOMAIN = "leagueos.test"
FIXED_TEST_PASSWORD = "StrongPass123!"
PASSWORD_SYMBOLS = "!@#$%^&*"


def make_password(length=20):
    random_source = secrets.SystemRandom()

    characters = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(PASSWORD_SYMBOLS),
    ]

    alphabet = (
        string.ascii_letters
        + string.digits
        + PASSWORD_SYMBOLS
    )

    characters.extend(
        secrets.choice(alphabet)
        for _ in range(max(length - len(characters), 0))
    )

    random_source.shuffle(characters)
    return "".join(characters)


def safe_token(value, object_id):
    token = slugify(value) or "record"
    return f"{token[:45]}-{object_id}"


def markdown_value(value):
    return str(value or "").replace("|", r"\|").replace("\n", " ")


class Command(BaseCommand):
    help = (
        "Create comprehensive League OS test credentials and export "
        "all @leagueos.test users to CSV and Markdown."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default=".local-test-data/neon-test-credentials.csv",
            help="CSV output path.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        output_path = Path(options["output"])
        markdown_path = output_path.with_suffix(".md")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        generated_types = {}
        created_count = 0
        updated_count = 0

        def ensure_user(
            *,
            email,
            first_name,
            last_name,
            role,
            account_type,
            club=None,
        ):
            nonlocal created_count, updated_count

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name[:150],
                    "last_name": last_name[:150],
                    "role": role,
                    "club": club,
                    "is_active": True,
                    "is_email_verified": True,
                },
            )

            user.first_name = first_name[:150]
            user.last_name = last_name[:150]
            user.role = role
            user.club = club
            user.is_active = True
            user.is_email_verified = True
            user.save()

            generated_types[email] = account_type

            if created:
                created_count += 1
            else:
                updated_count += 1

            return user

        # ------------------------------------------------------------
        # Union and community workspace accounts
        # ------------------------------------------------------------
        workspaces = (
            UnionWorkspace.objects
            .filter(status=UnionWorkspace.Status.ACTIVE)
            .order_by("name")
        )

        for workspace in workspaces:
            token = safe_token(
                workspace.slug or workspace.acronym,
                workspace.pk,
            )
            label = workspace.acronym or workspace.name

            union_admin = ensure_user(
                email=f"qa.union-admin.{token}@{TEST_DOMAIN}",
                first_name=label,
                last_name="Test Union Administrator",
                role=User.Role.UNION_ADMIN,
                account_type="Union administrator",
            )

            UnionWorkspaceMembership.objects.update_or_create(
                user=union_admin,
                workspace=workspace,
                defaults={
                    "role": UnionWorkspaceMembership.Role.UNION_ADMIN,
                    "extra_permissions": [],
                    "is_active": True,
                },
            )

            union_ticketing = ensure_user(
                email=f"qa.union-ticketing.{token}@{TEST_DOMAIN}",
                first_name=label,
                last_name="Test Union Ticketing Officer",
                role=User.Role.TICKETING_OFFICER,
                account_type="Union ticketing officer",
            )

            # The membership model currently has no dedicated
            # TICKETING_OFFICER choice. Keep VIEWER membership plus
            # explicit ticketing permissions while the primary role
            # controls dashboard access.
            UnionWorkspaceMembership.objects.update_or_create(
                user=union_ticketing,
                workspace=workspace,
                defaults={
                    "role": UnionWorkspaceMembership.Role.VIEWER,
                    "extra_permissions": [
                        "union.ticketing.manage",
                        "ticketing.validate",
                    ],
                    "is_active": True,
                },
            )

        # ------------------------------------------------------------
        # League and competition accounts
        # ------------------------------------------------------------
        leagues = (
            League.objects
            .filter(is_active=True)
            .select_related("union")
            .order_by("union__name", "name")
        )

        for league in leagues:
            token = safe_token(league.slug or league.name, league.pk)

            league_admin = ensure_user(
                email=f"qa.league-admin.{token}@{TEST_DOMAIN}",
                first_name=league.name,
                last_name="Test League Administrator",
                role=User.Role.LEAGUE_ADMIN,
                account_type="League administrator",
            )

            LeagueAdminScope.objects.update_or_create(
                user=league_admin,
                league=league,
                competition=None,
                defaults={
                    "role": LeagueAdminScope.Role.LEAGUE_ADMIN,
                    "is_active": True,
                },
            )

            competitions = (
                Competition.objects
                .filter(league=league, is_active=True)
                .order_by("name")
            )

            for competition in competitions:
                competition_token = safe_token(
                    competition.slug or competition.name,
                    competition.pk,
                )

                competition_admin = ensure_user(
                    email=(
                        f"qa.competition-admin."
                        f"{competition_token}@{TEST_DOMAIN}"
                    ),
                    first_name=competition.name,
                    last_name="Test Competition Administrator",
                    role=User.Role.LEAGUE_ADMIN,
                    account_type="Competition administrator",
                )

                LeagueAdminScope.objects.update_or_create(
                    user=competition_admin,
                    league=league,
                    competition=competition,
                    defaults={
                        "role": (
                            LeagueAdminScope.Role.COMPETITION_ADMIN
                        ),
                        "is_active": True,
                    },
                )

        # ------------------------------------------------------------
        # Club accounts
        # ------------------------------------------------------------
        clubs = Club.objects.all().order_by("sport", "name")

        for club in clubs:
            token = safe_token(club.slug or club.name, club.pk)
            club_label = club.short_name or club.name

            club_admin = ensure_user(
                email=f"qa.club-admin.{token}@{TEST_DOMAIN}",
                first_name=club_label,
                last_name="Test Club Administrator",
                role=User.Role.CLUB_ADMIN,
                account_type="Club administrator",
                club=club,
            )

            # Do not replace a real club administrator.
            if (
                club.admin_id is None
                or club.admin.email.lower().endswith(
                    f"@{TEST_DOMAIN}"
                )
            ):
                club.admin = club_admin
                club.save(update_fields=["admin"])

            ensure_user(
                email=f"qa.club-ticketing.{token}@{TEST_DOMAIN}",
                first_name=club_label,
                last_name="Test Club Ticketing Officer",
                role=User.Role.TICKETING_OFFICER,
                account_type="Club ticketing officer",
                club=club,
            )

        # ------------------------------------------------------------
        # Reset every test-domain password so the exported table is
        # complete, including older test users created previously.
        # ------------------------------------------------------------
        test_users = list(
            User.objects
            .filter(email__iendswith=f"@{TEST_DOMAIN}")
            .select_related("club")
            .order_by("email")
        )

        password_map = {}

        for user in test_users:
            password = FIXED_TEST_PASSWORD
            password_map[user.email] = password

            user.set_password(password)
            user.is_active = True
            user.is_email_verified = True
            user.save(
                update_fields=[
                    "password",
                    "is_active",
                    "is_email_verified",
                ]
            )

        rows = []

        for user in test_users:
            memberships = (
                user.union_workspace_memberships
                .filter(is_active=True)
                .select_related("workspace")
                .order_by("workspace__name")
            )

            membership_text = "; ".join(
                (
                    f"{membership.workspace.acronym}:"
                    f"{membership.role}"
                )
                for membership in memberships
            )

            scopes = (
                user.league_admin_scopes
                .filter(is_active=True)
                .select_related("league", "competition")
                .order_by("league__name", "competition__name")
            )

            scope_text = "; ".join(
                (
                    f"{scope.league.name} -> "
                    f"{scope.competition.name if scope.competition else 'ALL'} "
                    f"({scope.role})"
                )
                for scope in scopes
            )

            rows.append(
                {
                    "account_type": generated_types.get(
                        user.email,
                        "Existing test user",
                    ),
                    "email": user.email,
                    "password": password_map[user.email],
                    "primary_role": user.role,
                    "frontend_dashboard": get_dashboard_route(user),
                    "backend_dashboard": (
                        get_backend_dashboard_route(user)
                    ),
                    "workspace_memberships": membership_text,
                    "league_competition_scopes": scope_text,
                    "club": user.club.name if user.club else "",
                    "active": user.is_active,
                    "email_verified": user.is_email_verified,
                }
            )

        fieldnames = [
            "account_type",
            "email",
            "password",
            "primary_role",
            "frontend_dashboard",
            "backend_dashboard",
            "workspace_memberships",
            "league_competition_scopes",
            "club",
            "active",
            "email_verified",
        ]

        with output_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=fieldnames,
            )
            writer.writeheader()
            writer.writerows(rows)

        with markdown_path.open(
            "w",
            encoding="utf-8",
        ) as markdown_file:
            markdown_file.write(
                "| Type | Email | Password | Role | Dashboard | "
                "Workspace | League/Competition | Club |\n"
            )
            markdown_file.write(
                "|---|---|---|---|---|---|---|---|\n"
            )

            for row in rows:
                markdown_file.write(
                    "| "
                    + " | ".join(
                        [
                            markdown_value(row["account_type"]),
                            markdown_value(row["email"]),
                            markdown_value(row["password"]),
                            markdown_value(row["primary_role"]),
                            markdown_value(
                                row["frontend_dashboard"]
                            ),
                            markdown_value(
                                row["workspace_memberships"]
                            ),
                            markdown_value(
                                row["league_competition_scopes"]
                            ),
                            markdown_value(row["club"]),
                        ]
                    )
                    + " |\n"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_count} new comprehensive "
                f"test accounts."
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {updated_count} comprehensive "
                f"test accounts."
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Reset and exported {len(rows)} total "
                f"@{TEST_DOMAIN} accounts."
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"CSV: {output_path}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Markdown: {markdown_path}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "All @leagueos.test accounts now use "
                "StrongPass123!."
            )
        )
