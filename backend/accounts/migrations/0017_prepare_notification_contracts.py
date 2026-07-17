import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

CANONICAL_EVENT_TYPE_CHOICES = [
    ("SYSTEM", "System"),
    ("MATCH_REMINDER", "Match Reminder"),
    ("SCORE_UPDATE", "Score Update"),
    ("FOLLOWED_TEAM_NEWS", "Followed Team News"),
    ("STANDINGS_CHANGE", "Standings Change"),
    ("TICKET_UPDATES", "Ticket Updates"),
    ("TICKET_OFFER", "Ticket Offer"),
    ("MEMBERSHIP_UPDATES", "Membership Updates"),
    ("SPONSORSHIP_UPDATES", "Sponsorship Updates"),
    ("FANTASY_UPDATES", "Fantasy Updates"),
    ("LEAGUE_NEWS", "League News"),
    ("CLUB_NEWS", "Club News"),
    ("GENERAL_NEWS", "General News"),
    ("MARKETING_UPDATES", "Marketing Updates"),
    ("GOVERNANCE", "Governance"),
]


class Migration(migrations.Migration):
    dependencies = [
        (
            "accounts",
            "0016_paymenthistory_description_paymenthistory_metadata_and_more",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="notificationpreference",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notification_preferences",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="notificationpreference",
            name="event_type",
            field=models.CharField(
                choices=CANONICAL_EVENT_TYPE_CHOICES,
                default="SYSTEM",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="notificationpreference",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="notificationpreference",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="notification",
            name="action_url",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="notification",
            name="event_type",
            field=models.CharField(
                choices=CANONICAL_EVENT_TYPE_CHOICES,
                default="SYSTEM",
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name="notification",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="notification",
            name="priority",
            field=models.CharField(
                choices=[("LOW", "Low"), ("NORMAL", "Normal"), ("HIGH", "High")],
                default="NORMAL",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="notification",
            name="read_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="notification",
            name="category",
            field=models.CharField(
                choices=[
                    ("SYSTEM", "System"),
                    ("MEMBERSHIP", "Membership"),
                    ("TICKET", "Ticket"),
                    ("TICKETING", "Ticketing"),
                    ("PAYMENT", "Payment"),
                    ("SPONSORSHIP", "Sponsorship"),
                    ("FANTASY", "Fantasy"),
                    ("MATCH", "Match"),
                    ("GOVERNANCE", "Governance"),
                    ("CLUB", "Club"),
                ],
                default="SYSTEM",
                max_length=30,
            ),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["user", "is_read", "created_at"],
                name="accounts_no_user_id_cabb0a_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["user", "category", "created_at"],
                name="accounts_no_user_id_56141b_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["event_type"],
                name="accounts_no_event_t_69df80_idx",
            ),
        ),
    ]
