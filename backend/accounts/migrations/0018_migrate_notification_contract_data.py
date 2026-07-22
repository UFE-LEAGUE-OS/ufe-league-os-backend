from django.db import migrations

LEGACY_EVENT_TYPE_NORMALIZATION = {
    "MEMBERSHIP": "MEMBERSHIP_UPDATES",
    "SPONSORSHIP": "SPONSORSHIP_UPDATES",
    "CLUB": "CLUB_NEWS",
}

LEGACY_PRIORITY_NORMALIZATION = {
    "low": "LOW",
    "normal": "NORMAL",
    "high": "HIGH",
}

CANONICAL_EVENT_TYPES = (
    "SYSTEM",
    "MATCH_REMINDER",
    "SCORE_UPDATE",
    "FOLLOWED_TEAM_NEWS",
    "STANDINGS_CHANGE",
    "TICKET_UPDATES",
    "TICKET_OFFER",
    "MEMBERSHIP_UPDATES",
    "SPONSORSHIP_UPDATES",
    "FANTASY_UPDATES",
    "LEAGUE_NEWS",
    "CLUB_NEWS",
    "GENERAL_NEWS",
    "MARKETING_UPDATES",
    "GOVERNANCE",
)

NOTIFICATION_CATEGORY_EVENT_TYPES = {
    "SYSTEM": "SYSTEM",
    "MEMBERSHIP": "MEMBERSHIP_UPDATES",
    "TICKET": "TICKET_UPDATES",
    "TICKETING": "TICKET_UPDATES",
    "SPONSORSHIP": "SPONSORSHIP_UPDATES",
    "FANTASY": "FANTASY_UPDATES",
    "MATCH": "MATCH_REMINDER",
    "GOVERNANCE": "GOVERNANCE",
    "CLUB": "CLUB_NEWS",
    "PAYMENT": "SYSTEM",
}

LEGACY_BOOLEAN_EVENT_TYPES = (
    ("membership_updates", "MEMBERSHIP_UPDATES"),
    ("ticket_updates", "TICKET_UPDATES"),
    ("sponsorship_updates", "SPONSORSHIP_UPDATES"),
    ("governance_updates", "GOVERNANCE"),
)


def create_preferences_from_legacy_booleans(
    preference_model,
    schema_editor,
    db_alias,
):
    connection = schema_editor.connection
    table_name = preference_model._meta.db_table
    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(
                cursor, table_name
            )
        }

    available_mappings = [
        (column_name, event_type)
        for column_name, event_type in LEGACY_BOOLEAN_EVENT_TYPES
        if column_name in columns
    ]
    if not available_mappings:
        return

    primary_key_column = preference_model._meta.pk.column
    selected_columns = [
        primary_key_column,
        "user_id",
        *[item[0] for item in available_mappings],
    ]
    quoted_columns = ", ".join(
        connection.ops.quote_name(column_name) for column_name in selected_columns
    )
    quoted_table = connection.ops.quote_name(table_name)
    quoted_primary_key = connection.ops.quote_name(primary_key_column)
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {quoted_columns} FROM {quoted_table} "
            f"ORDER BY {quoted_primary_key}"
        )
        legacy_rows = cursor.fetchall()

    # The old AddField operations left NOT NULL columns without persistent
    # database defaults. Give them temporary defaults so per-event rows can be
    # inserted before 0019 removes the compatibility-only columns.
    for column_name, _event_type in available_mappings:
        quoted_column = connection.ops.quote_name(column_name)
        schema_editor.execute(
            f"ALTER TABLE {quoted_table} "
            f"ALTER COLUMN {quoted_column} SET DEFAULT %s",
            params=(True,),
        )

    preferences = preference_model.objects.using(db_alias)
    for row in legacy_rows:
        user_id = row[1]
        for (_column_name, event_type), enabled in zip(
            available_mappings,
            row[2:],
        ):
            preferences.get_or_create(
                user_id=user_id,
                event_type=event_type,
                defaults={
                    "email_enabled": bool(enabled),
                    "push_enabled": bool(enabled),
                    "sms_enabled": False,
                },
            )


def migrate_notification_contract_data(apps, schema_editor):
    preference_model = apps.get_model("accounts", "NotificationPreference")
    notification_model = apps.get_model("accounts", "Notification")
    db_alias = schema_editor.connection.alias
    preferences = preference_model.objects.using(db_alias)

    for alias, canonical in LEGACY_EVENT_TYPE_NORMALIZATION.items():
        for alias_preference in list(
            preferences.filter(event_type=alias).order_by("id")
        ):
            canonical_preference = (
                preferences.filter(
                    user_id=alias_preference.user_id,
                    event_type=canonical,
                )
                .exclude(pk=alias_preference.pk)
                .first()
            )
            if canonical_preference is None:
                alias_preference.event_type = canonical
                alias_preference.save(using=db_alias, update_fields=["event_type"])
                continue

            canonical_preference.email_enabled = (
                canonical_preference.email_enabled and alias_preference.email_enabled
            )
            canonical_preference.push_enabled = (
                canonical_preference.push_enabled and alias_preference.push_enabled
            )
            canonical_preference.sms_enabled = (
                canonical_preference.sms_enabled and alias_preference.sms_enabled
            )
            canonical_preference.save(
                using=db_alias,
                update_fields=["email_enabled", "push_enabled", "sms_enabled"],
            )
            alias_preference.delete(using=db_alias)

    create_preferences_from_legacy_booleans(
        preference_model,
        schema_editor,
        db_alias,
    )

    for legacy, canonical in LEGACY_PRIORITY_NORMALIZATION.items():
        notification_model.objects.using(db_alias).filter(priority=legacy).update(
            priority=canonical
        )

    user_ids = list(preferences.values_list("user_id", flat=True).distinct())
    for user_id in user_ids:
        for event_type in CANONICAL_EVENT_TYPES:
            preferences.get_or_create(
                user_id=user_id,
                event_type=event_type,
                defaults={
                    "email_enabled": True,
                    "push_enabled": True,
                    "sms_enabled": False,
                },
            )

    for category, event_type in NOTIFICATION_CATEGORY_EVENT_TYPES.items():
        notification_model.objects.using(db_alias).filter(category=category).update(
            event_type=event_type
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0017_prepare_notification_contracts"),
    ]

    operations = [
        migrations.RunPython(
            migrate_notification_contract_data,
            migrations.RunPython.noop,
        ),
    ]


# Reverse is intentionally a no-op: the corrected 0017 schema remains per-event
# and is fully compatible with the canonical rows created above.
