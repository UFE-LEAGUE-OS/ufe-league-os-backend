from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("dashboards", "0020_alter_league_admin_scope_role")]

    operations = [
        migrations.AlterField(
            model_name="league",
            name="name",
            field=models.CharField(max_length=200),
        ),
        migrations.AddConstraint(
            model_name="league",
            constraint=models.UniqueConstraint(
                fields=("union", "name"), name="unique_union_league_name"
            ),
        ),
    ]
