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

CANONICAL_PRIORITY_CHOICES = [
    ("LOW", "Low"),
    ("NORMAL", "Normal"),
    ("HIGH", "High"),
]


def bound_field(model, name, field):
    field.set_attributes_from_name(name)
    field.model = model
    return field


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


def reconcile_notification_contract_schema(apps, schema_editor):
    notification_model = apps.get_model("accounts", "Notification")
    connection = schema_editor.connection
    table_name = notification_model._meta.db_table

    with connection.cursor() as cursor:
        columns = {
            column.name: column
            for column in connection.introspection.get_table_description(
                cursor, table_name
            )
        }

    desired_fields = {
        "action_url": models.CharField(blank=True, default="", max_length=500),
        "event_type": models.CharField(
            choices=CANONICAL_EVENT_TYPE_CHOICES,
            default="SYSTEM",
            max_length=40,
        ),
        "metadata": models.JSONField(blank=True, default=dict),
        "priority": models.CharField(
            choices=CANONICAL_PRIORITY_CHOICES,
            default="NORMAL",
            max_length=20,
        ),
        "read_at": models.DateTimeField(blank=True, null=True),
    }
    for field_name, field in desired_fields.items():
        bound_field(notification_model, field_name, field)

    # SQLite remakes the whole table for each AddField/AlterField operation.
    # Register compatibility columns already present in the physical schema so
    # a later remake preserves them even though the 0016 migration state does
    # not know about the parallel incoming branch.
    for field_name, field in desired_fields.items():
        if field_name in columns:
            notification_model._meta.add_field(field)

    for field_name, field in desired_fields.items():
        if field_name not in columns:
            schema_editor.add_field(notification_model, field)
            notification_model._meta.add_field(field)

    incoming_event_type_column = columns.get("event_type")
    title_column = columns.get("title")
    if (
        incoming_event_type_column is not None
        and title_column is not None
        and title_column.internal_size != 150
    ):
        quoted_table = connection.ops.quote_name(table_name)
        quoted_title = connection.ops.quote_name("title")
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT 1 FROM {quoted_table} "
                f"WHERE LENGTH({quoted_title}) > %s LIMIT 1",
                [150],
            )
            if cursor.fetchone() is not None:
                raise RuntimeError(
                    "Notification titles longer than 150 characters must be "
                    "reviewed before applying the canonical schema."
                )

        old_title = bound_field(
            notification_model,
            "title",
            models.CharField(max_length=255),
        )
        new_title = bound_field(
            notification_model,
            "title",
            models.CharField(max_length=150),
        )
        schema_editor.alter_field(
            notification_model,
            old_title,
            new_title,
            strict=False,
        )

    if (
        incoming_event_type_column is not None
        and incoming_event_type_column.internal_size != 40
    ):
        quoted_table = connection.ops.quote_name(table_name)
        quoted_event_type = connection.ops.quote_name("event_type")
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT 1 FROM {quoted_table} "
                f"WHERE LENGTH({quoted_event_type}) > %s LIMIT 1",
                [40],
            )
            if cursor.fetchone() is not None:
                raise RuntimeError(
                    "Notification event types longer than 40 characters must be "
                    "reviewed before applying the canonical schema."
                )

        old_event_type = bound_field(
            notification_model,
            "event_type",
            models.CharField(blank=True, default="", max_length=100),
        )
        new_event_type = bound_field(
            notification_model,
            "event_type",
            models.CharField(
                choices=CANONICAL_EVENT_TYPE_CHOICES,
                default="SYSTEM",
                max_length=40,
            ),
        )
        schema_editor.alter_field(
            notification_model,
            old_event_type,
            new_event_type,
            strict=False,
        )


def remove_notification_contract_schema(apps, schema_editor):
    notification_model = apps.get_model("accounts", "Notification")
    connection = schema_editor.connection
    table_name = notification_model._meta.db_table
    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(
                cursor, table_name
            )
        }

    removable_fields = {
        "action_url": models.CharField(blank=True, max_length=500),
        "event_type": models.CharField(max_length=40),
        "metadata": models.JSONField(blank=True, default=dict),
        "priority": models.CharField(max_length=20),
        "read_at": models.DateTimeField(blank=True, null=True),
    }
    for field_name, field in removable_fields.items():
        if field_name not in columns:
            continue
        schema_editor.remove_field(
            notification_model,
            bound_field(notification_model, field_name, field),
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
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    reconcile_notification_contract_schema,
                    remove_notification_contract_schema,
                ),
            ],
            state_operations=[
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
                        choices=CANONICAL_PRIORITY_CHOICES,
                        default="NORMAL",
                        max_length=20,
                    ),
                ),
                migrations.AddField(
                    model_name="notification",
                    name="read_at",
                    field=models.DateTimeField(blank=True, null=True),
                ),
            ],
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
