from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0021_backfill_feed_source_contracts"),
        ("accounts", "0019_fix_notificationpreference_user_field"),
    ]

    operations = []
