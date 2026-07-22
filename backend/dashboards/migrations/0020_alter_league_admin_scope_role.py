from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("dashboards", "0019_union_transfer_loan_return")]

    operations = [
        migrations.AlterField(
            model_name="leagueadminscope",
            name="role",
            field=models.CharField(
                choices=[
                    ("LEAGUE_ADMIN", "League Administrator"),
                    ("COMPETITION_ADMIN", "Competition Administrator"),
                    ("FIXTURES_MANAGER", "Fixtures Manager"),
                    ("REGISTRAR", "Registrar"),
                    ("OFFICIALS_COORDINATOR", "Officials Coordinator"),
                    ("VIEWER", "Viewer"),
                ],
                default="LEAGUE_ADMIN",
                max_length=40,
            ),
        )
    ]
