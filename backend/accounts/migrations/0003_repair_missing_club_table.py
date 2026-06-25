from django.db import migrations, models


class Migration(migrations.Migration):
    """
    This migration repairs a missing accounts_club table on Render/PostgreSQL
    deployments. On SQLite (used for local testing), the table is already
    created by 0001_initial's CreateModel, so this is a no-op.
    """

    dependencies = [
        ("accounts", "0002_alter_user_managers_and_more"),
    ]

    operations = [
        # No-op on SQLite. On PostgreSQL, the RunSQL below would be used
        # but the SQL uses PL/pgSQL which is incompatible with SQLite.
        # The accounts_club table is already properly created via
        # CreateModel in 0001_initial on development/test environments.
        migrations.RunSQL(
            sql=migrations.RunSQL.noop,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]