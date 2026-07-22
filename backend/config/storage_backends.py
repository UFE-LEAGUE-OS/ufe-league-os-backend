from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from storages.backends.s3 import S3Storage


def rewrite_presigned_url(url, external_base_url):
    """
    Rewrite an internally signed S3 URL to a browser-accessible proxy URL.

    The signature and original S3 object path remain unchanged. The frontend
    proxy must strip its external path prefix and forward the original query
    string while setting the Host header expected by the S3 signature.
    """
    external_base_url = (external_base_url or "").strip().rstrip("/")

    if not external_base_url:
        return url

    internal_parts = urlsplit(url)
    external_parts = urlsplit(external_base_url)

    if external_parts.scheme not in {"http", "https"}:
        raise ImproperlyConfigured(
            "S3_PRIVATE_EXTERNAL_BASE_URL must use http or https."
        )

    if not external_parts.netloc:
        raise ImproperlyConfigured(
            "S3_PRIVATE_EXTERNAL_BASE_URL must include a hostname."
        )

    if external_parts.query or external_parts.fragment:
        raise ImproperlyConfigured(
            "S3_PRIVATE_EXTERNAL_BASE_URL cannot contain a query or fragment."
        )

    external_prefix = external_parts.path.rstrip("/")
    internal_path = internal_parts.path

    if not internal_path.startswith("/"):
        internal_path = f"/{internal_path}"

    external_path = f"{external_prefix}{internal_path}"

    return urlunsplit(
        (
            external_parts.scheme,
            external_parts.netloc,
            external_path,
            internal_parts.query,
            internal_parts.fragment,
        )
    )


class PublicMediaStorage(S3Storage):
    """S3-compatible storage for browser-readable League OS media."""


class PrivateMediaStorage(S3Storage):
    """S3-compatible storage for restricted League OS documents."""

    def url(
        self,
        name,
        parameters=None,
        expire=None,
        http_method=None,
    ):
        internal_url = super().url(
            name,
            parameters=parameters,
            expire=expire,
            http_method=http_method,
        )

        external_base_url = getattr(
            settings,
            "S3_PRIVATE_EXTERNAL_BASE_URL",
            "",
        )

        return rewrite_presigned_url(
            internal_url,
            external_base_url,
        )


class LocalPrivateMediaStorage(FileSystemStorage):
    """Local private storage that is not exposed by Django media URLs."""
