from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.storage_backends import rewrite_presigned_url


class StorageExternalURLTests(SimpleTestCase):
    def test_empty_external_base_keeps_original_url(self):
        original = (
            "http://object-storage:8333/"
            "league-os-private/documents/file.pdf"
            "?X-Amz-Signature=test-signature"
        )

        self.assertEqual(
            rewrite_presigned_url(original, ""),
            original,
        )

    def test_rewrites_host_and_adds_proxy_prefix(self):
        internal = (
            "http://object-storage:8333/"
            "league-os-private/documents/file.pdf"
            "?X-Amz-Algorithm=AWS4-HMAC-SHA256"
            "&X-Amz-Signature=test-signature"
        )

        result = rewrite_presigned_url(
            internal,
            "https://league-os.example/storage",
        )

        self.assertEqual(
            result,
            (
                "https://league-os.example/storage/"
                "league-os-private/documents/file.pdf"
                "?X-Amz-Algorithm=AWS4-HMAC-SHA256"
                "&X-Amz-Signature=test-signature"
            ),
        )

    def test_external_base_requires_http_or_https(self):
        with self.assertRaises(ImproperlyConfigured):
            rewrite_presigned_url(
                "http://object-storage:8333/bucket/file.pdf",
                "ftp://league-os.example/storage",
            )

    def test_external_base_rejects_query_parameters(self):
        with self.assertRaises(ImproperlyConfigured):
            rewrite_presigned_url(
                "http://object-storage:8333/bucket/file.pdf",
                "https://league-os.example/storage?unsafe=true",
            )
