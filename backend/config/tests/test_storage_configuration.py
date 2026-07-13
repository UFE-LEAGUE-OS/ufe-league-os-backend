from pathlib import Path

from django.conf import settings
from django.core.files.storage import (
    FileSystemStorage,
    default_storage,
    storages,
)
from django.test import SimpleTestCase

from accounts.models import Club, User
from config.storage_backends import (
    LocalPrivateMediaStorage,
    PrivateMediaStorage,
    PublicMediaStorage,
)
from dashboards.models import League, Union
from governance.models import SportVariant


class StorageConfigurationTests(SimpleTestCase):
    def test_required_storage_aliases_are_configured(self):
        self.assertIn("default", settings.STORAGES)
        self.assertIn("private", settings.STORAGES)
        self.assertIn("staticfiles", settings.STORAGES)

    def test_existing_image_fields_use_public_default_storage(self):
        image_fields = (
            (User, "avatar"),
            (Club, "logo"),
            (Club, "banner"),
            (Union, "logo"),
            (League, "logo"),
            (SportVariant, "icon"),
        )

        for model, field_name in image_fields:
            with self.subTest(
                model=model.__name__,
                field=field_name,
            ):
                field = model._meta.get_field(field_name)
                self.assertIs(field.storage, default_storage)

    def test_storage_backend_permissions(self):
        public_storage = storages["default"]
        private_storage = storages["private"]

        if settings.USE_S3_MEDIA:
            self.assertIsInstance(
                public_storage,
                PublicMediaStorage,
            )
            self.assertIsInstance(
                private_storage,
                PrivateMediaStorage,
            )

            self.assertEqual(
                public_storage.bucket_name,
                settings.S3_PUBLIC_BUCKET_NAME,
            )
            self.assertEqual(
                private_storage.bucket_name,
                settings.S3_PRIVATE_BUCKET_NAME,
            )

            self.assertFalse(public_storage.querystring_auth)
            self.assertEqual(
                public_storage.default_acl,
                "public-read",
            )

            self.assertTrue(private_storage.querystring_auth)
            self.assertEqual(
                private_storage.default_acl,
                "private",
            )
            self.assertEqual(
                private_storage.querystring_expire,
                settings.PRIVATE_MEDIA_URL_EXPIRY,
            )
        else:
            self.assertIsInstance(
                public_storage,
                FileSystemStorage,
            )
            self.assertIsInstance(
                private_storage,
                LocalPrivateMediaStorage,
            )

            self.assertNotEqual(
                Path(public_storage.location),
                Path(private_storage.location),
            )
