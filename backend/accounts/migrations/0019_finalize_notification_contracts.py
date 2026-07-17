from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0018_migrate_notification_contract_data"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="notificationpreference",
            name="governance_updates",
        ),
        migrations.RemoveField(
            model_name="notificationpreference",
            name="membership_updates",
        ),
        migrations.RemoveField(
            model_name="notificationpreference",
            name="sponsorship_updates",
        ),
        migrations.RemoveField(
            model_name="notificationpreference",
            name="ticket_updates",
        ),
        migrations.AlterUniqueTogether(
            name="notificationpreference",
            unique_together={("user", "event_type")},
        ),
        migrations.AlterModelOptions(
            name="notificationpreference",
            options={"ordering": ["user__email", "event_type"]},
        ),
    ]
