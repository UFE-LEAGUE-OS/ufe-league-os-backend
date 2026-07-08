from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from dashboards.models import Union, UnionWorkspace, UnionWorkspaceMembership

WORKSPACES = [
    {
        "name": "Uganda Rugby Union",
        "acronym": "URU",
        "sport": "Rugby",
        "workspace_type": UnionWorkspace.WorkspaceType.FEDERATION,
        "description": "National rugby federation workspace.",
        "primary_color": "#7b3ff2",
        "country": "Uganda",
        "founded_year": 1955,
    },
    {
        "name": "Federation of Uganda Football Associations",
        "acronym": "FUFA",
        "sport": "Football",
        "workspace_type": UnionWorkspace.WorkspaceType.FEDERATION,
        "description": "National football federation workspace.",
        "primary_color": "#f97316",
        "country": "Uganda",
        "founded_year": 1924,
    },
    {
        "name": "Federation of Uganda Basketball Associations",
        "acronym": "FUBA",
        "sport": "Basketball",
        "workspace_type": UnionWorkspace.WorkspaceType.FEDERATION,
        "description": "National basketball federation workspace.",
        "primary_color": "#2563eb",
        "country": "Uganda",
        "founded_year": 1968,
    },
    {
        "name": "Budo League",
        "acronym": "BUDO",
        "sport": "Football",
        "workspace_type": UnionWorkspace.WorkspaceType.COMMUNITY_LEAGUE,
        "description": "Community league operations workspace.",
        "primary_color": "#10b981",
        "country": "Uganda",
        "founded_year": 2010,
    },
    {
        "name": "SMACK League",
        "acronym": "SMACK",
        "sport": "Football",
        "workspace_type": UnionWorkspace.WorkspaceType.COMMUNITY_LEAGUE,
        "description": "Community league operations workspace.",
        "primary_color": "#a855f7",
        "country": "Uganda",
        "founded_year": 2012,
    },
]


class Command(BaseCommand):
    help = "Seed default League OS union workspaces and optionally attach a user."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email", help="Existing user email to attach to the workspaces."
        )
        parser.add_argument(
            "--role",
            default=UnionWorkspaceMembership.Role.OWNER,
            choices=[choice[0] for choice in UnionWorkspaceMembership.Role.choices],
            help="Workspace role to assign to the user.",
        )

    def handle(self, *args, **options):
        email = options.get("email")
        role = options.get("role")

        user = None

        if email:
            User = get_user_model()
            user = User.objects.filter(email__iexact=email).first()

            if user is None:
                raise SystemExit(f"No user found with email {email}")

        for item in WORKSPACES:
            slug = slugify(item["name"])

            union = (
                Union.objects.filter(slug=slug).first()
                or Union.objects.filter(name__iexact=item["name"]).first()
            )

            if union is None:
                union = Union.objects.create(
                    slug=slug,
                    name=item["name"],
                    description=item["description"],
                    country=item["country"],
                    founded_year=item["founded_year"],
                )
            else:
                union.slug = union.slug or slug
                union.name = item["name"]
                union.description = item["description"]
                union.country = item["country"]
                union.founded_year = item["founded_year"]
                union.save(
                    update_fields=[
                        "slug",
                        "name",
                        "description",
                        "country",
                        "founded_year",
                    ]
                )

            workspace = (
                UnionWorkspace.objects.filter(slug=slug).first()
                or UnionWorkspace.objects.filter(name__iexact=item["name"]).first()
                or UnionWorkspace.objects.filter(
                    acronym__iexact=item["acronym"]
                ).first()
            )

            created = workspace is None

            if workspace is None:
                workspace = UnionWorkspace(slug=slug)

            workspace.related_union = union
            workspace.name = item["name"]
            workspace.acronym = item["acronym"]
            workspace.sport = item["sport"]
            workspace.workspace_type = item["workspace_type"]
            workspace.description = item["description"]
            workspace.primary_color = item["primary_color"]
            workspace.status = UnionWorkspace.Status.ACTIVE
            workspace.save()

            if user:
                UnionWorkspaceMembership.objects.update_or_create(
                    user=user,
                    workspace=workspace,
                    defaults={
                        "role": role,
                        "is_active": True,
                    },
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"{'Created' if created else 'Updated'} {workspace.acronym} workspace"
                )
            )

        if user:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Attached {user.email} to all union workspaces as {role}"
                )
            )
