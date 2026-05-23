"""
Shared __init__.py for utility modules
"""

"""Shared package exports.

NOTE: Do NOT import Django models at package import time. Importing
`shared.models` here caused Django to attempt to create model classes
before the app registry was ready -> AppRegistryNotReady.

Only export pure utilities from here. Import models via
`from shared import models` or `from shared.models import Article` in
modules where Django is already configured (views/serializers after
django.setup()).
"""

from .utils import HTTPClient, CacheClient, get_worker_count, setup_environment

__all__ = [
    "HTTPClient",
    "CacheClient",
    "get_worker_count",
    "setup_environment",
]

