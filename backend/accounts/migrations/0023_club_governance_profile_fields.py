from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0022_merge_notification_migration_branches")]

    operations = [
        migrations.AddField(
            model_name="club",
            name="address",
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name="club",
            name="contact_email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="club", name="description", field=models.TextField(blank=True)
        ),
        migrations.AddField(
            model_name="club",
            name="founded_year",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="club", name="is_active", field=models.BooleanField(default=True)
        ),
        migrations.AddField(
            model_name="club",
            name="phone_number",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="club",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="club", name="website", field=models.URLField(blank=True)
        ),
    ]
