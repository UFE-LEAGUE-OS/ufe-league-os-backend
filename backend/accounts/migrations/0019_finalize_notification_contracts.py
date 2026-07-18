from django.db import migrations, models

LEGACY_BOOLEAN_COLUMNS = (
    "membership_updates",
    "ticket_updates",
    "sponsorship_updates",
    "governance_updates",
)


def finalize_legacy_notification_preference_schema(apps, schema_editor):
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

    for column_name in LEGACY_BOOLEAN_COLUMNS:
        if column_name not in columns:
            continue
        field = models.BooleanField(default=True)
        field.set_attributes_from_name(column_name)
        field.model = preference_model
        schema_editor.remove_field(preference_model, field)

    user_column = preference_model._meta.get_field("user").column
    event_type_column = preference_model._meta.get_field("event_type").column
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table_name)
    user_event_uniques = [
        (name, constraint)
        for name, constraint in constraints.items()
        if constraint["unique"]
        and not constraint["primary_key"]
        and not constraint["foreign_key"]
        and set(constraint["columns"]) == {user_column, event_type_column}
        and len(constraint["columns"]) == 2
    ]
    if not user_event_uniques:
        schema_editor.alter_unique_together(
            preference_model,
            set(),
            {("user", "event_type")},
        )
        return

    preferred_name = (
        "unique_user_event_type"
        if any(name == "unique_user_event_type" for name, _ in user_event_uniques)
        else sorted(name for name, _ in user_event_uniques)[0]
    )
    for constraint_name, constraint in user_event_uniques:
        if constraint_name == preferred_name:
            continue
        if constraint["index"]:
            schema_editor.remove_index(
                preference_model,
                models.Index(
                    fields=("user", "event_type"),
                    name=constraint_name,
                ),
            )
        else:
            schema_editor.remove_constraint(
                preference_model,
                models.UniqueConstraint(
                    fields=("user", "event_type"),
                    name=constraint_name,
                ),
            )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0018_migrate_notification_contract_data"),
    ]

    operations = [
        migrations.RunPython(
            finalize_legacy_notification_preference_schema,
            # Compatibility columns and constraint repair are database-only.
            migrations.RunPython.noop,
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
