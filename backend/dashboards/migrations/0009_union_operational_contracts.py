# Generated for maintained Union operational contracts.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("dashboards", "0008_add_union_ticketing_officer_role"),
        ("teams", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NationalTeam",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=180)),
                ("slug", models.SlugField(max_length=200)),
                (
                    "category",
                    models.CharField(
                        help_text="Examples: Senior Men, Senior Women, U20, Sevens.",
                        max_length=120,
                    ),
                ),
                ("gender", models.CharField(blank=True, max_length=40)),
                ("age_group", models.CharField(blank=True, max_length=40)),
                ("head_coach", models.CharField(blank=True, max_length=160)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ACTIVE", "Active"),
                            ("CAMP", "In Camp"),
                            ("SELECTION", "Selection"),
                            ("INACTIVE", "Inactive"),
                        ],
                        default="ACTIVE",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_national_teams",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="national_teams",
                        to="dashboards.unionworkspace",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "unique_together": {("workspace", "slug")},
                "indexes": [
                    models.Index(
                        fields=["workspace", "status"],
                        name="dash_natteam_ws_status_idx",
                    ),
                    models.Index(
                        fields=["workspace", "is_active"],
                        name="dash_natteam_ws_active_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="NationalTeamMember",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("full_name", models.CharField(max_length=160)),
                (
                    "member_type",
                    models.CharField(
                        choices=[("PLAYER", "Player"), ("STAFF", "Staff")],
                        default="PLAYER",
                        max_length=20,
                    ),
                ),
                ("role", models.CharField(blank=True, max_length=100)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ACTIVE", "Active"),
                            ("INJURED", "Injured"),
                            ("UNAVAILABLE", "Unavailable"),
                            ("RELEASED", "Released"),
                        ],
                        default="ACTIVE",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "club",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="national_team_members",
                        to="accounts.club",
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="members",
                        to="dashboards.nationalteam",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="national_team_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["member_type", "full_name"],
                "indexes": [
                    models.Index(
                        fields=["team", "member_type", "status"],
                        name="dash_natmem_team_type_idx",
                    ),
                    models.Index(
                        fields=["club", "status"],
                        name="dash_natmem_club_status_idx",
                    ),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="nationalteammember",
            constraint=models.UniqueConstraint(
                condition=models.Q(user__isnull=False),
                fields=("team", "user", "member_type"),
                name="unique_team_user_member_type",
            ),
        ),
        migrations.CreateModel(
            name="UnionRegistrationApplication",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "application_type",
                    models.CharField(
                        choices=[
                            ("NEW_PLAYER", "New Player"),
                            ("TRANSFER", "Transfer"),
                            ("RENEWAL", "Renewal"),
                            ("SQUAD", "Squad Registration"),
                            ("STAFF", "Staff Registration"),
                        ],
                        default="NEW_PLAYER",
                        max_length=30,
                    ),
                ),
                ("applicant_name", models.CharField(max_length=180)),
                ("registration_number", models.CharField(blank=True, max_length=80)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("UNDER_REVIEW", "Under Review"),
                            ("DOCUMENTS_REQUIRED", "Documents Required"),
                            ("APPROVED", "Approved"),
                            ("REJECTED", "Rejected"),
                            ("WITHDRAWN", "Withdrawn"),
                        ],
                        default="PENDING",
                        max_length=30,
                    ),
                ),
                ("documents_complete", models.BooleanField(default=False)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("reviewer_notes", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "club",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="union_registration_applications",
                        to="accounts.club",
                    ),
                ),
                (
                    "competition",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="registration_applications",
                        to="dashboards.competition",
                    ),
                ),
                (
                    "player_registration",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="union_review_applications",
                        to="teams.playerregistration",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_union_registration_applications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="submitted_union_registration_applications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="union_registration_applications",
                        to="teams.team",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="registration_applications",
                        to="dashboards.unionworkspace",
                    ),
                ),
            ],
            options={
                "ordering": ["-submitted_at", "applicant_name"],
                "indexes": [
                    models.Index(
                        fields=["workspace", "status", "submitted_at"],
                        name="dash_regapp_ws_status_idx",
                    ),
                    models.Index(
                        fields=["workspace", "club", "status"],
                        name="dash_regapp_ws_club_idx",
                    ),
                    models.Index(
                        fields=["registration_number"],
                        name="dash_regapp_regnum_idx",
                    ),
                ],
            },
        ),
    ]
