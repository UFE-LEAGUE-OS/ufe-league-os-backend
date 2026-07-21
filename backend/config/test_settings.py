import warnings
from pathlib import Path
from datetime import timedelta

# Minimal settings for running tests in CI/local with sqlite
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-test-key-at-least-32-characters-long-for-jwt-signing"
DEBUG = True

ALLOWED_HOSTS = ["localhost"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "channels",
    "accounts",
    "dashboards",
    "governance.apps.GovernanceConfig",
    "teams",
    "sponsorships",
    "ticketing",
    "memberships",
    "fantasy",
    "engagements",
    "monitoring.apps.MonitoringConfig",
    "platform_admin",
    "club_operations",
    "rbac.apps.RbacConfig",
    "analytics.apps.AnalyticsConfig",
    "django_filters",
    "finances",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"

USE_S3_MEDIA = False
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "test_media"

PRIVATE_MEDIA_URL = "/private-media/"
PRIVATE_MEDIA_ROOT = BASE_DIR / "test_private_media"
PRIVATE_MEDIA_URL_EXPIRY = 900

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": MEDIA_ROOT,
            "base_url": MEDIA_URL,
        },
    },
    "private": {
        "BACKEND": "config.storage_backends.LocalPrivateMediaStorage",
        "OPTIONS": {
            "location": PRIVATE_MEDIA_ROOT,
            "base_url": PRIVATE_MEDIA_URL,
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "URL_FORMAT_OVERRIDE": None,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5

# Channels / WebSocket configuration for tests
ASGI_APPLICATION = "config.asgi.application"
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# Suppress DRF URL converter deprecation warning during tests
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, module="rest_framework.urlpatterns"
)
