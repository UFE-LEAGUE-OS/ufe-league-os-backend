from django.db import connection, models
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class NotificationContractMigrationTests(TransactionTestCase):
    migrate_from = ("accounts", "0010_clubadminscope")
    migrate_to = ("accounts", "0019_finalize_notification_contracts")
    canonical_event_types = (
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

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        self.old_apps = self.executor.loader.project_state([self.migrate_from]).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def create_historical_user(self, apps, suffix):
        user_model = apps.get_model("accounts", "User")
        return user_model.objects.create(
            email=f"notification-migration-{suffix}@example.com",
            password="!",
            first_name="Migration",
            last_name="User",
        )

    def migrate_to_state(self, target):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([target])
        return self.executor.loader.project_state([target]).apps

    def test_populated_forward_path_preserves_rows_channels_and_categories(self):
        preference_model = self.old_apps.get_model("accounts", "NotificationPreference")
        notification_model = self.old_apps.get_model("accounts", "Notification")
        user = self.create_historical_user(self.old_apps, "populated")
        original_values = {
            "MATCH_REMINDER": (False, True, False),
            "TICKET_UPDATES": (True, False, True),
            "MEMBERSHIP_UPDATES": (False, False, True),
            "CLUB_NEWS": (True, True, False),
        }
        original_ids = {}
        for event_type, channels in original_values.items():
            preference = preference_model.objects.create(
                user=user,
                event_type=event_type,
                email_enabled=channels[0],
                push_enabled=channels[1],
                sms_enabled=channels[2],
            )
            original_ids[event_type] = preference.pk

        category_mapping = {
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
        notification_ids = {}
        for category in category_mapping:
            notification = notification_model.objects.create(
                user=user,
                category=category,
                title=f"{category} notification",
                message="Preserve category mapping.",
            )
            notification_ids[category] = notification.pk

        new_apps = self.migrate_to_state(self.migrate_to)
        migrated_preferences = new_apps.get_model(
            "accounts", "NotificationPreference"
        ).objects
        migrated_notifications = new_apps.get_model("accounts", "Notification").objects

        for event_type, channels in original_values.items():
            with self.subTest(event_type=event_type):
                preference = migrated_preferences.get(
                    user_id=user.pk,
                    event_type=event_type,
                )
                self.assertEqual(preference.pk, original_ids[event_type])
                self.assertEqual(
                    (
                        preference.email_enabled,
                        preference.push_enabled,
                        preference.sms_enabled,
                    ),
                    channels,
                )

        self.assertEqual(
            set(
                migrated_preferences.filter(user_id=user.pk).values_list(
                    "event_type", flat=True
                )
            ),
            set(self.canonical_event_types),
        )
        for event_type in self.canonical_event_types:
            self.assertEqual(
                migrated_preferences.filter(
                    user_id=user.pk,
                    event_type=event_type,
                ).count(),
                1,
            )
        for category, event_type in category_mapping.items():
            self.assertEqual(
                migrated_notifications.get(pk=notification_ids[category]).event_type,
                event_type,
            )

    def test_alias_normalization_preserves_primary_key_and_channels(self):
        preference_model = self.old_apps.get_model("accounts", "NotificationPreference")
        user = self.create_historical_user(self.old_apps, "alias")
        alias = preference_model.objects.create(
            user=user,
            event_type="MEMBERSHIP",
            email_enabled=False,
            push_enabled=True,
            sms_enabled=True,
        )

        new_apps = self.migrate_to_state(self.migrate_to)
        normalized = new_apps.get_model(
            "accounts", "NotificationPreference"
        ).objects.get(user_id=user.pk, event_type="MEMBERSHIP_UPDATES")

        self.assertEqual(normalized.pk, alias.pk)
        self.assertFalse(normalized.email_enabled)
        self.assertTrue(normalized.push_enabled)
        self.assertTrue(normalized.sms_enabled)

    def test_alias_conflict_preserves_canonical_row_and_channel_opt_outs(self):
        preference_model = self.old_apps.get_model("accounts", "NotificationPreference")
        user = self.create_historical_user(self.old_apps, "alias-conflict")
        alias = preference_model.objects.create(
            user=user,
            event_type="MEMBERSHIP",
            email_enabled=False,
            push_enabled=True,
            sms_enabled=False,
        )
        canonical = preference_model.objects.create(
            user=user,
            event_type="MEMBERSHIP_UPDATES",
            email_enabled=True,
            push_enabled=False,
            sms_enabled=True,
        )

        new_apps = self.migrate_to_state(self.migrate_to)
        preferences = new_apps.get_model("accounts", "NotificationPreference").objects
        merged = preferences.get(
            user_id=user.pk,
            event_type="MEMBERSHIP_UPDATES",
        )

        self.assertEqual(merged.pk, canonical.pk)
        self.assertFalse(merged.email_enabled)
        self.assertFalse(merged.push_enabled)
        self.assertFalse(merged.sms_enabled)
        self.assertFalse(preferences.filter(pk=alias.pk).exists())
        self.assertEqual(
            preferences.filter(
                user_id=user.pk,
                event_type="MEMBERSHIP_UPDATES",
            ).count(),
            1,
        )

    def test_reverse_to_0010_keeps_multiple_per_event_rows_and_channels(self):
        preference_model = self.old_apps.get_model("accounts", "NotificationPreference")
        user = self.create_historical_user(self.old_apps, "reverse")
        originals = {}
        for event_type, channels in {
            "MATCH_REMINDER": (False, True, False),
            "TICKET_UPDATES": (True, False, True),
        }.items():
            preference = preference_model.objects.create(
                user=user,
                event_type=event_type,
                email_enabled=channels[0],
                push_enabled=channels[1],
                sms_enabled=channels[2],
            )
            originals[preference.pk] = (event_type, channels)

        self.migrate_to_state(self.migrate_to)
        reverted_apps = self.migrate_to_state(self.migrate_from)
        reverted_preferences = reverted_apps.get_model(
            "accounts", "NotificationPreference"
        ).objects

        self.assertGreater(reverted_preferences.filter(user_id=user.pk).count(), 1)
        for preference_id, (event_type, channels) in originals.items():
            preference = reverted_preferences.get(pk=preference_id)
            self.assertEqual(preference.event_type, event_type)
            self.assertEqual(
                (
                    preference.email_enabled,
                    preference.push_enabled,
                    preference.sms_enabled,
                ),
                channels,
            )

    def test_populated_path_migrates_from_0010_through_0021(self):
        preference_model = self.old_apps.get_model("accounts", "NotificationPreference")
        user = self.create_historical_user(self.old_apps, "full-chain")
        original_ids = []
        for event_type in (
            "MATCH_REMINDER",
            "TICKET_UPDATES",
            "MEMBERSHIP_UPDATES",
            "CLUB_NEWS",
        ):
            original_ids.append(
                preference_model.objects.create(
                    user=user,
                    event_type=event_type,
                    email_enabled=False,
                    push_enabled=True,
                    sms_enabled=False,
                ).pk
            )

        final_apps = self.migrate_to_state(
            ("accounts", "0021_backfill_feed_source_contracts")
        )
        final_preferences = final_apps.get_model(
            "accounts", "NotificationPreference"
        ).objects

        self.assertEqual(
            final_preferences.filter(pk__in=original_ids).count(),
            len(original_ids),
        )
        self.assertEqual(
            final_preferences.filter(user_id=user.pk).count(),
            len(self.canonical_event_types),
        )


class LegacyAppliedNotificationSchemaCompatibilityTests(TransactionTestCase):
    migrate_from = (
        "accounts",
        "0016_paymenthistory_description_paymenthistory_metadata_and_more",
    )
    migrate_to = ("accounts", "0021_backfill_feed_source_contracts")
    canonical_event_types = NotificationContractMigrationTests.canonical_event_types
    legacy_boolean_values = {
        "membership_updates": False,
        "ticket_updates": True,
        "sponsorship_updates": False,
        "governance_updates": True,
    }

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        self.old_apps = self.executor.loader.project_state([self.migrate_from]).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def physical_columns(self, model):
        with connection.cursor() as cursor:
            return {
                column.name
                for column in connection.introspection.get_table_description(
                    cursor,
                    model._meta.db_table,
                )
            }

    def physical_constraints(self, model):
        with connection.cursor() as cursor:
            return connection.introspection.get_constraints(
                cursor,
                model._meta.db_table,
            )

    def test_legacy_applied_0016_schema_migrates_safely_through_0021(self):
        user_model = self.old_apps.get_model("accounts", "User")
        preference_model = self.old_apps.get_model("accounts", "NotificationPreference")
        user = user_model.objects.create(
            email="legacy-applied-0016@example.com",
            password="!",
            first_name="Legacy",
            last_name="Applied",
        )
        original = preference_model.objects.create(
            user=user,
            event_type="SYSTEM",
            email_enabled=False,
            push_enabled=True,
            sms_enabled=True,
        )
        original_channels = (
            original.email_enabled,
            original.push_enabled,
            original.sms_enabled,
        )

        with connection.schema_editor() as schema_editor:
            schema_editor.alter_unique_together(
                preference_model,
                {("user", "event_type")},
                set(),
            )
            schema_editor.add_constraint(
                preference_model,
                models.UniqueConstraint(
                    fields=("user",),
                    name="test_legacy_notification_preference_user_unique",
                ),
            )
            schema_editor.remove_field(
                preference_model,
                preference_model._meta.get_field("created_at"),
            )
            schema_editor.remove_field(
                preference_model,
                preference_model._meta.get_field("updated_at"),
            )
            for column_name in self.legacy_boolean_values:
                field = models.BooleanField(default=True)
                field.set_attributes_from_name(column_name)
                field.model = preference_model
                schema_editor.add_field(preference_model, field)

        table_name = connection.ops.quote_name(preference_model._meta.db_table)
        assignments = ", ".join(
            f"{connection.ops.quote_name(column_name)} = %s"
            for column_name in self.legacy_boolean_values
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table_name} SET {assignments} WHERE id = %s",
                [*self.legacy_boolean_values.values(), original.pk],
            )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        final_apps = self.executor.loader.project_state([self.migrate_to]).apps
        final_model = final_apps.get_model("accounts", "NotificationPreference")
        final_preferences = final_model.objects
        preserved = final_preferences.get(pk=original.pk)

        self.assertEqual(
            (
                preserved.email_enabled,
                preserved.push_enabled,
                preserved.sms_enabled,
            ),
            original_channels,
        )
        self.assertIsNotNone(preserved.created_at)
        self.assertIsNotNone(preserved.updated_at)

        expected_legacy_events = {
            "MEMBERSHIP_UPDATES": False,
            "TICKET_UPDATES": True,
            "SPONSORSHIP_UPDATES": False,
            "GOVERNANCE": True,
        }
        for event_type, enabled in expected_legacy_events.items():
            with self.subTest(event_type=event_type):
                preference = final_preferences.get(
                    user_id=user.pk,
                    event_type=event_type,
                )
                self.assertEqual(preference.email_enabled, enabled)
                self.assertEqual(preference.push_enabled, enabled)
                self.assertFalse(preference.sms_enabled)

        self.assertEqual(
            set(
                final_preferences.filter(user_id=user.pk).values_list(
                    "event_type",
                    flat=True,
                )
            ),
            set(self.canonical_event_types),
        )
        for event_type in self.canonical_event_types:
            self.assertEqual(
                final_preferences.filter(
                    user_id=user.pk,
                    event_type=event_type,
                ).count(),
                1,
            )

        final_columns = self.physical_columns(final_model)
        self.assertIn("created_at", final_columns)
        self.assertIn("updated_at", final_columns)
        for column_name in self.legacy_boolean_values:
            self.assertNotIn(column_name, final_columns)

        constraints = self.physical_constraints(final_model)
        user_column = final_model._meta.get_field("user").column
        event_column = final_model._meta.get_field("event_type").column
        self.assertFalse(
            any(
                constraint["unique"] and list(constraint["columns"]) == [user_column]
                for constraint in constraints.values()
            )
        )
        self.assertTrue(
            any(
                constraint["unique"]
                and set(constraint["columns"]) == {user_column, event_column}
                and len(constraint["columns"]) == 2
                for constraint in constraints.values()
            )
        )
        self.assertTrue(
            any(
                constraint["foreign_key"]
                and list(constraint["columns"]) == [user_column]
                for constraint in constraints.values()
            )
        )
        self.assertEqual(
            final_preferences.filter(user_id=user.pk).count(),
            len(self.canonical_event_types),
        )


class RestoredRoleAndFeedContractMigrationTests(TransactionTestCase):
    migrate_from = ("accounts", "0019_finalize_notification_contracts")
    migrate_to = ("accounts", "0021_backfill_feed_source_contracts")

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        self.old_apps = self.executor.loader.project_state([self.migrate_from]).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def create_historical_user(self, apps, suffix):
        user_model = apps.get_model("accounts", "User")
        return user_model.objects.create(
            email=f"role-feed-migration-{suffix}@example.com",
            password="!",
            first_name="Migration",
            last_name="User",
        )

    def migrate_to_state(self, target):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([target])
        return self.executor.loader.project_state([target]).apps

    def test_migrations_use_default_atomic_behavior(self):
        schema_migration = self.executor.loader.get_migration(
            "accounts", "0020_restore_role_follow_feed_schema"
        )
        data_migration = self.executor.loader.get_migration(
            "accounts", "0021_backfill_feed_source_contracts"
        )

        self.assertTrue(schema_migration.atomic)
        self.assertTrue(data_migration.atomic)

    def test_forward_preserves_and_converts_role_and_feed_data(self):
        feed_model = self.old_apps.get_model("accounts", "FeedItem")
        approval_model = self.old_apps.get_model("accounts", "RoleApproval")
        target_user = self.create_historical_user(self.old_apps, "target")
        reviewer = self.create_historical_user(self.old_apps, "reviewer")
        feed = feed_model.objects.create(
            user=target_user,
            content_type="CLUB",
            object_id=42,
            title="Legacy feed title",
            description="Legacy feed description",
        )
        approval = approval_model.objects.create(
            user=target_user,
            approved_by=reviewer,
            requested_role="CLUB_ADMIN",
        )

        new_apps = self.migrate_to_state(self.migrate_to)
        migrated_feed = new_apps.get_model("accounts", "FeedItem").objects.get(
            pk=feed.pk
        )
        migrated_approval = new_apps.get_model("accounts", "RoleApproval").objects.get(
            pk=approval.pk
        )

        self.assertEqual(migrated_feed.pk, feed.pk)
        self.assertEqual(migrated_feed.source_content_type, "CLUB")
        self.assertEqual(migrated_feed.source_object_id, 42)
        self.assertEqual(migrated_feed.title, "Legacy feed title")
        self.assertEqual(migrated_feed.description, "Legacy feed description")
        self.assertEqual(migrated_approval.pk, approval.pk)
        self.assertEqual(migrated_approval.target_user_id, target_user.pk)
        self.assertEqual(migrated_approval.reviewed_by_id, reviewer.pk)

    def test_reverse_preserves_and_converts_typed_feed_source(self):
        new_apps = self.migrate_to_state(self.migrate_to)
        user = self.create_historical_user(new_apps, "reverse")
        feed = new_apps.get_model("accounts", "FeedItem").objects.create(
            user=user,
            content_type="",
            object_id=0,
            source_content_type="LEAGUE",
            source_object_id=77,
            title="Typed feed title",
            description="Typed feed description",
        )

        old_apps = self.migrate_to_state(self.migrate_from)
        reverted_feed = old_apps.get_model("accounts", "FeedItem").objects.get(
            pk=feed.pk
        )

        self.assertEqual(reverted_feed.pk, feed.pk)
        self.assertEqual(reverted_feed.content_type, "LEAGUE")
        self.assertEqual(reverted_feed.object_id, 77)
