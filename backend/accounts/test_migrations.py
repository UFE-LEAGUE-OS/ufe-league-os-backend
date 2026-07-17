from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class NotificationContractMigrationTests(TransactionTestCase):
    migrate_from = (
        "accounts",
        "0016_paymenthistory_description_paymenthistory_metadata_and_more",
    )
    migrate_to = ("accounts", "0019_finalize_notification_contracts")

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        self.old_apps = self.executor.loader.project_state([self.migrate_from]).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def create_legacy_user(self, suffix):
        user_model = self.old_apps.get_model("accounts", "User")
        return user_model.objects.create(
            email=f"migration-{suffix}@example.com",
            password="!",
            first_name="Migration",
            last_name="User",
        )

    def migrate_forward(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        return self.executor.loader.project_state([self.migrate_to]).apps

    def migrate_backward(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        return self.executor.loader.project_state([self.migrate_from]).apps

    def test_forward_migration_preserves_preferences_and_notification_semantics(self):
        preference_model = self.old_apps.get_model("accounts", "NotificationPreference")
        notification_model = self.old_apps.get_model("accounts", "Notification")
        user = self.create_legacy_user("forward")
        preference = preference_model.objects.create(
            user=user,
            event_type="SYSTEM",
            email_enabled=True,
            push_enabled=True,
            sms_enabled=False,
            membership_updates=False,
            ticket_updates=True,
            sponsorship_updates=False,
            governance_updates=True,
        )
        categories = (
            "TICKET",
            "MEMBERSHIP",
            "SPONSORSHIP",
            "GOVERNANCE",
            "CLUB",
            "SYSTEM",
        )
        notification_ids = {}
        for category in categories:
            notification = notification_model.objects.create(
                user=user,
                category=category,
                title=f"{category} notification",
                message="Preserve this notification.",
                is_read=category == "SYSTEM",
            )
            notification_ids[category] = notification.id

        new_apps = self.migrate_forward()
        migrated_preference_model = new_apps.get_model(
            "accounts", "NotificationPreference"
        )
        migrated_notification_model = new_apps.get_model("accounts", "Notification")

        preferences = {
            item.event_type: item
            for item in migrated_preference_model.objects.filter(user_id=user.id)
        }
        self.assertEqual(
            set(preferences),
            {
                "SYSTEM",
                "MEMBERSHIP_UPDATES",
                "TICKET_UPDATES",
                "SPONSORSHIP_UPDATES",
                "GOVERNANCE",
            },
        )
        self.assertEqual(preferences["SYSTEM"].id, preference.id)
        self.assertTrue(preferences["SYSTEM"].email_enabled)
        self.assertTrue(preferences["SYSTEM"].push_enabled)
        self.assertFalse(preferences["SYSTEM"].sms_enabled)

        expected_channels = {
            "MEMBERSHIP_UPDATES": False,
            "TICKET_UPDATES": True,
            "SPONSORSHIP_UPDATES": False,
            "GOVERNANCE": True,
        }
        for event_type, enabled in expected_channels.items():
            with self.subTest(event_type=event_type):
                self.assertEqual(preferences[event_type].email_enabled, enabled)
                self.assertEqual(preferences[event_type].push_enabled, enabled)
                self.assertFalse(preferences[event_type].sms_enabled)

        expected_notification_events = {
            "TICKET": "TICKET_UPDATES",
            "MEMBERSHIP": "MEMBERSHIP_UPDATES",
            "SPONSORSHIP": "SPONSORSHIP_UPDATES",
            "GOVERNANCE": "GOVERNANCE",
            "CLUB": "CLUB_NEWS",
            "SYSTEM": "SYSTEM",
        }
        for category, event_type in expected_notification_events.items():
            with self.subTest(category=category):
                notification = migrated_notification_model.objects.get(
                    pk=notification_ids[category]
                )
                self.assertEqual(notification.user_id, user.id)
                self.assertEqual(notification.category, category)
                self.assertEqual(notification.event_type, event_type)
                self.assertEqual(notification.message, "Preserve this notification.")
                self.assertEqual(notification.is_read, category == "SYSTEM")

    def test_forward_migration_normalizes_legacy_event_types_without_data_loss(self):
        preference_model = self.old_apps.get_model("accounts", "NotificationPreference")
        cases = (
            ("MEMBERSHIP", "MEMBERSHIP_UPDATES"),
            ("SPONSORSHIP", "SPONSORSHIP_UPDATES"),
            ("CLUB", "CLUB_NEWS"),
        )
        originals = {}
        for legacy_event_type, canonical_event_type in cases:
            user = self.create_legacy_user(legacy_event_type.lower())
            preference = preference_model.objects.create(
                user=user,
                event_type=legacy_event_type,
                email_enabled=False,
                push_enabled=False,
                sms_enabled=True,
                membership_updates=True,
                ticket_updates=True,
                sponsorship_updates=True,
                governance_updates=True,
            )
            originals[legacy_event_type] = (
                user.id,
                preference.id,
                canonical_event_type,
            )

        new_apps = self.migrate_forward()
        migrated_preference_model = new_apps.get_model(
            "accounts", "NotificationPreference"
        )

        for legacy_event_type, (
            user_id,
            preference_id,
            canonical_event_type,
        ) in originals.items():
            with self.subTest(legacy_event_type=legacy_event_type):
                normalized = migrated_preference_model.objects.get(pk=preference_id)
                self.assertEqual(normalized.user_id, user_id)
                self.assertEqual(normalized.event_type, canonical_event_type)
                self.assertFalse(normalized.email_enabled)
                self.assertFalse(normalized.push_enabled)
                self.assertTrue(normalized.sms_enabled)
                self.assertEqual(
                    migrated_preference_model.objects.filter(
                        user_id=user_id,
                        event_type=canonical_event_type,
                    ).count(),
                    1,
                )

        final_event_types = set(
            migrated_preference_model.objects.values_list("event_type", flat=True)
        )
        self.assertTrue(
            {"MEMBERSHIP_UPDATES", "SPONSORSHIP_UPDATES", "CLUB_NEWS"}.issubset(
                final_event_types
            )
        )
        self.assertTrue(
            {"MEMBERSHIP", "SPONSORSHIP", "CLUB"}.isdisjoint(final_event_types)
        )

    def test_reverse_migration_collapses_rows_before_restoring_one_to_one(self):
        preference_model = self.old_apps.get_model("accounts", "NotificationPreference")
        user = self.create_legacy_user("reverse")
        system_preference = preference_model.objects.create(
            user=user,
            event_type="SYSTEM",
            membership_updates=True,
            ticket_updates=True,
            sponsorship_updates=True,
            governance_updates=True,
        )

        new_apps = self.migrate_forward()
        migrated_preference_model = new_apps.get_model(
            "accounts", "NotificationPreference"
        )
        expected_values = {
            "MEMBERSHIP_UPDATES": False,
            "TICKET_UPDATES": True,
            "SPONSORSHIP_UPDATES": False,
            "GOVERNANCE": True,
        }
        for event_type, enabled in expected_values.items():
            migrated_preference_model.objects.filter(
                user_id=user.id,
                event_type=event_type,
            ).update(push_enabled=enabled)

        reverted_apps = self.migrate_backward()
        reverted_preference_model = reverted_apps.get_model(
            "accounts", "NotificationPreference"
        )
        reverted = reverted_preference_model.objects.get(user_id=user.id)

        self.assertEqual(
            reverted_preference_model.objects.filter(user_id=user.id).count(),
            1,
        )
        self.assertEqual(reverted.id, system_preference.id)
        self.assertEqual(reverted.event_type, "SYSTEM")
        self.assertFalse(reverted.membership_updates)
        self.assertTrue(reverted.ticket_updates)
        self.assertFalse(reverted.sponsorship_updates)
        self.assertTrue(reverted.governance_updates)

    def test_reverse_migration_normalizes_oldest_row_when_system_is_absent(self):
        preference_model = self.old_apps.get_model("accounts", "NotificationPreference")
        user = self.create_legacy_user("reverse-no-system")
        oldest = preference_model.objects.create(
            user=user,
            event_type="MEMBERSHIP",
            email_enabled=False,
            push_enabled=False,
            sms_enabled=True,
            membership_updates=True,
            ticket_updates=False,
            sponsorship_updates=True,
            governance_updates=False,
        )

        self.migrate_forward()
        reverted_apps = self.migrate_backward()
        reverted_preference_model = reverted_apps.get_model(
            "accounts", "NotificationPreference"
        )
        reverted = reverted_preference_model.objects.get(user_id=user.id)

        self.assertEqual(reverted.id, oldest.id)
        self.assertEqual(reverted.event_type, "MEMBERSHIP")
        self.assertFalse(reverted.membership_updates)
        self.assertFalse(reverted.ticket_updates)
        self.assertTrue(reverted.sponsorship_updates)
        self.assertFalse(reverted.governance_updates)
