"""
Django settings for Variant S (Synchronous)
Django REST Framework with Gunicorn
"""

import os
import sys
from pathlib import Path

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent
SHARED_DIR = Path(__file__).resolve().parent.parent.parent / "shared"

# Add repo root (parent of shared) to path BEFORE importing base settings so
# Python can import package name `shared`
sys.path.insert(0, str(SHARED_DIR.parent))

from shared.django_settings_base import *  # noqa: F401, F403

DEBUG = os.environ.get("DEBUG", "True") == "True"
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-variant-s-synchronous-key-change-in-production"
)

INSTALLED_APPS += [
    "variant_s.apps",  # Variant S specific apps
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "drf_benchmark_s"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "postgres"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 600,
        "ATOMIC_REQUESTS": False,
    }
}

EXTERNAL_HTTP_CLIENT = "requests"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Gunicorn specific settings
WSGI_APPLICATION = "config.wsgi.application"

# Root URL configuration for the variant (points to variant-specific urls)
ROOT_URLCONF = "config.urls"

# Performance tuning for synchronous variant
# Connection pooling
DATABASE_POOL_SIZE = 20
DATABASE_POOL_MAX_OVERFLOW = 10

# Cache connection pool (already set in base)
CACHES["default"]["OPTIONS"]["CONNECTION_POOL_KWARGS"]["max_connections"] = 50

# Task queue - using sync broker for Variant S
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/2")
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "False") == "True"
CELERY_TASK_EAGER_PROPAGATES = True

# REST Framework settings for Variant S
REST_FRAMEWORK = {"DEFAULT_RENDERER_CLASSES": [
    "rest_framework.renderers.JSONRenderer",
], "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination", "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ], "DEFAULT_THROTTLE_CLASSES": [], "DEFAULT_THROTTLE_RATES": {}}


