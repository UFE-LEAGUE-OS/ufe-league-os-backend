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


def repair_legacy_notification_preference_schema(apps, schema_editor):
    preference_model = apps.get_model("accounts", "NotificationPreference")
    connection = schema_editor.connection
    table_name = preference_model._meta.db_table

    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(
                cursor, table_name
            )
        }

    for field_name in ("created_at", "updated_at"):
        field = preference_model._meta.get_field(field_name)
        if field.column not in columns:
            schema_editor.add_field(preference_model, field)

    user_field = preference_model._meta.get_field("user")
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table_name)
    legacy_unique_names = [
        name
        for name, constraint in constraints.items()
        if constraint["unique"]
        and not constraint["primary_key"]
        and not constraint["foreign_key"]
        and list(constraint["columns"]) == [user_field.column]
    ]
    for constraint_name in legacy_unique_names:
        schema_editor.remove_constraint(
            preference_model,
            models.UniqueConstraint(
                fields=("user",),
                name=constraint_name,
            ),
        )


class Migration(migrations.Migration):
    dependencies = [
        (
            "accounts",
            "0016_paymenthistory_description_paymenthistory_metadata_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            repair_legacy_notification_preference_schema,
            # Migration state already expects timestamps and a per-event FK.
            migrations.RunPython.noop,
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
