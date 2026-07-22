from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("dashboards", "0006_alter_unionworkspacemembership_role"),
    ]

    operations = [
        migrations.CreateModel(
            name="LeagueAdminScope",
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
                    "role",
                    models.CharField(
                        choices=[
                            ("LEAGUE_ADMIN", "League Administrator"),
                            ("COMPETITION_ADMIN", "Competition Administrator"),
                            ("OFFICIALS_COORDINATOR", "Officials Coordinator"),
                            ("VIEWER", "Viewer"),
                        ],
                        default="LEAGUE_ADMIN",
                        max_length=40,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "competition",
                    models.ForeignKey(
                        blank=True,
                        help_text="Leave blank to grant access to the whole league.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="admin_scopes",
                        to="dashboards.competition",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_league_admin_scopes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "league",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="admin_scopes",
                        to="dashboards.league",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="league_admin_scopes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["league__name", "competition__name", "user__email"],
                "indexes": [
                    models.Index(
                        fields=["user", "is_active"],
                        name="dashboards_user_id_482361_idx",
                    ),
                    models.Index(
                        fields=["league", "is_active"],
                        name="dashboards_league__6316d7_idx",
                    ),
                    models.Index(
                        fields=["competition", "is_active"],
                        name="dashboards_competi_c7b452_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(competition__isnull=True),
                        fields=("user", "league"),
                        name="unique_user_full_league_admin_scope",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(competition__isnull=False),
                        fields=("user", "competition"),
                        name="unique_user_competition_admin_scope",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="fixtureofficialassignment",
            name="responded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="fixtureofficialassignment",
            name="response_note",
            field=models.TextField(blank=True),
        ),
    ]
