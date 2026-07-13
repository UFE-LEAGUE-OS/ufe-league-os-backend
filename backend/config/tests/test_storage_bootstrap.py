from unittest.mock import patch

from django.test import SimpleTestCase

from config.storage_bootstrap import (
    build_public_read_policy,
    environment_flag,
    serialize_public_read_policy,
)


class StorageBootstrapTests(SimpleTestCase):
    def test_public_policy_grants_only_object_reads(self):
        bucket_name = "league-os-public"

        policy = build_public_read_policy(bucket_name)
        statement = policy["Statement"][0]

        self.assertEqual(policy["Version"], "2012-10-17")
        self.assertEqual(statement["Effect"], "Allow")
        self.assertEqual(statement["Principal"], "*")
        self.assertEqual(statement["Action"], "s3:GetObject")
        self.assertEqual(
            statement["Resource"],
            f"arn:aws:s3:::{bucket_name}/*",
        )

    def test_serialized_policy_is_valid_json_document(self):
        serialized = serialize_public_read_policy("league-os-public")

        self.assertIn('"Action":"s3:GetObject"', serialized)
        self.assertIn(
            '"Resource":"arn:aws:s3:::league-os-public/*"',
            serialized,
        )

    def test_environment_flag_accepts_common_true_values(self):
        for value in ("1", "true", "TRUE", "yes", "on"):
            with self.subTest(value=value):
                with patch.dict(
                    "os.environ",
                    {"S3_MANAGE_BUCKET_POLICIES": value},
                ):
                    self.assertTrue(environment_flag("S3_MANAGE_BUCKET_POLICIES"))

    def test_environment_flag_defaults_to_false(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(environment_flag("S3_MANAGE_BUCKET_POLICIES"))
