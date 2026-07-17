from django.db import migrations

LEGACY_EVENT_TYPE_NORMALIZATION = {
    "MEMBERSHIP": "MEMBERSHIP_UPDATES",
    "SPONSORSHIP": "SPONSORSHIP_UPDATES",
    "CLUB": "CLUB_NEWS",
}

LEGACY_BOOLEAN_MAPPINGS = (
    ("MEMBERSHIP_UPDATES", "membership_updates"),
    ("TICKET_UPDATES", "ticket_updates"),
    ("SPONSORSHIP_UPDATES", "sponsorship_updates"),
    ("GOVERNANCE", "governance_updates"),
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

DOWNGRADE_EVENT_TYPE_NORMALIZATION = {
    "MEMBERSHIP_UPDATES": "MEMBERSHIP",
    "SPONSORSHIP_UPDATES": "SPONSORSHIP",
    "CLUB_NEWS": "CLUB",
    "TICKET_UPDATES": "TICKET_UPDATES",
    "GOVERNANCE": "GOVERNANCE",
    "SYSTEM": "SYSTEM",
}


def migrate_notification_contract_data(apps, schema_editor):
    preference_model = apps.get_model("accounts", "NotificationPreference")
    notification_model = apps.get_model("accounts", "Notification")
    db_alias = schema_editor.connection.alias

    original_preferences = list(preference_model.objects.using(db_alias).order_by("id"))
    for preference in original_preferences:
        normalized_event_type = LEGACY_EVENT_TYPE_NORMALIZATION.get(
            preference.event_type
        )
        if normalized_event_type:
            preference.event_type = normalized_event_type
            preference.save(using=db_alias, update_fields=["event_type"])

    for preference in original_preferences:
        for event_type, legacy_field in LEGACY_BOOLEAN_MAPPINGS:
            preference_model.objects.using(db_alias).get_or_create(
                user_id=preference.user_id,
                event_type=event_type,
                defaults={
                    "email_enabled": getattr(preference, legacy_field),
                    "push_enabled": getattr(preference, legacy_field),
                    "sms_enabled": False,
                },
            )

    for category, event_type in NOTIFICATION_CATEGORY_EVENT_TYPES.items():
        notification_model.objects.using(db_alias).filter(category=category).update(
            event_type=event_type
        )


def reverse_notification_contract_data(apps, schema_editor):
    preference_model = apps.get_model("accounts", "NotificationPreference")
    db_alias = schema_editor.connection.alias
    queryset = preference_model.objects.using(db_alias)
    user_ids = list(queryset.values_list("user_id", flat=True).distinct())

    for user_id in user_ids:
        user_preferences = queryset.filter(user_id=user_id).order_by("id")
        retained = user_preferences.filter(event_type="SYSTEM").first()
        if retained is None:
            retained = user_preferences.first()

        for event_type, legacy_field in LEGACY_BOOLEAN_MAPPINGS:
            event_preference = user_preferences.filter(event_type=event_type).first()
            setattr(
                retained,
                legacy_field,
                event_preference.push_enabled if event_preference else True,
            )

        retained.event_type = DOWNGRADE_EVENT_TYPE_NORMALIZATION.get(
            retained.event_type,
            "SYSTEM",
        )
        retained.save(
            using=db_alias,
            update_fields=[
                "event_type",
                *[
                    legacy_field
                    for _event_type, legacy_field in LEGACY_BOOLEAN_MAPPINGS
                ],
            ],
        )
        user_preferences.exclude(pk=retained.pk).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0017_prepare_notification_contracts"),
    ]

    operations = [
        migrations.RunPython(
            migrate_notification_contract_data,
            reverse_notification_contract_data,
        ),
    ]
