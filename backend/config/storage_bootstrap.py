import json
import os
import time

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

TRUE_VALUES = {"1", "true", "yes", "on"}


def environment_flag(name, default=False):
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in TRUE_VALUES


def build_public_read_policy(bucket_name):
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "LeagueOSPublicMediaRead",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket_name}/*",
            }
        ],
    }


def serialize_public_read_policy(bucket_name):
    return json.dumps(
        build_public_read_policy(bucket_name),
        separators=(",", ":"),
        sort_keys=True,
    )


def create_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
        region_name=os.getenv("S3_REGION_NAME", "us-east-1"),
        config=Config(
            signature_version="s3v4",
            s3={
                "addressing_style": os.getenv(
                    "S3_ADDRESSING_STYLE",
                    "path",
                )
            },
        ),
    )


def configure_object_storage():
    if not environment_flag("S3_MANAGE_BUCKET_POLICIES"):
        print(
            "Object-storage policy bootstrap skipped: "
            "S3_MANAGE_BUCKET_POLICIES is disabled."
        )
        return

    public_bucket = os.getenv(
        "S3_PUBLIC_BUCKET_NAME",
        "league-os-public",
    )
    private_bucket = os.getenv(
        "S3_PRIVATE_BUCKET_NAME",
        "league-os-private",
    )
    max_attempts = int(os.getenv("S3_BOOTSTRAP_MAX_ATTEMPTS", "30"))
    retry_seconds = float(os.getenv("S3_BOOTSTRAP_RETRY_SECONDS", "2"))

    if max_attempts <= 0:
        raise ValueError("S3_BOOTSTRAP_MAX_ATTEMPTS must be greater than zero.")

    client = create_s3_client()

    for attempt in range(1, max_attempts + 1):
        try:
            existing_buckets = {
                item["Name"] for item in client.list_buckets().get("Buckets", [])
            }

            for bucket_name in (public_bucket, private_bucket):
                if bucket_name not in existing_buckets:
                    client.create_bucket(Bucket=bucket_name)
                    print(f"Created object-storage bucket: {bucket_name}")

            client.put_bucket_policy(
                Bucket=public_bucket,
                Policy=serialize_public_read_policy(public_bucket),
            )

            print("Applied anonymous read policy to public bucket: " f"{public_bucket}")
            print("Private bucket remains credential-protected: " f"{private_bucket}")
            return
        except (BotoCoreError, ClientError) as exc:
            if attempt == max_attempts:
                raise RuntimeError(
                    "Object-storage bootstrap failed after " f"{max_attempts} attempts."
                ) from exc

            print(
                "Object storage is not ready; retrying " f"({attempt}/{max_attempts})."
            )
            time.sleep(retry_seconds)


if __name__ == "__main__":
    configure_object_storage()
