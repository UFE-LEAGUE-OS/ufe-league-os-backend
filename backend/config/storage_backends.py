from django.core.files.storage import FileSystemStorage
from storages.backends.s3 import S3Storage


class PublicMediaStorage(S3Storage):
    """S3-compatible storage for browser-readable League OS media."""


class PrivateMediaStorage(S3Storage):
    """S3-compatible storage for restricted League OS documents."""


class LocalPrivateMediaStorage(FileSystemStorage):
    """Local private storage that is not exposed by Django media URLs."""
