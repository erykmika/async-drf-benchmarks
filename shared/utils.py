"""
Shared utilities for both variants
"""

import os
import asyncio
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class HTTPClient:
    """
    Unified HTTP client interface for both variants.
    Variant S uses synchronous requests.
    Variant A uses async aiohttp.
    """

    def __init__(self, variant: str = "S"):
        self.variant = variant.upper()
        if self.variant == "A":
            # Async variant will use aiohttp
            try:
                import aiohttp

                self.http_client = "aiohttp"
            except ImportError:
                logger.warning("aiohttp not available, falling back to requests")
                import requests

                self.http_client = "requests"
        else:
            # Sync variant uses requests
            import requests

            self.http_client = "requests"

    def get(self, url: str, **kwargs) -> Any:
        """Make a GET request"""
        if self.http_client == "requests":
            return requests.get(url, **kwargs)
        else:
            raise NotImplementedError("Use async variant of this method for aiohttp")

    def post(self, url: str, **kwargs) -> Any:
        """Make a POST request"""
        if self.http_client == "requests":
            return requests.post(url, **kwargs)
        else:
            raise NotImplementedError("Use async variant of this method for aiohttp")

    async def aget(self, url: str, **kwargs) -> Any:
        """Make an async GET request"""
        if self.http_client == "aiohttp":
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(url, **kwargs) as response:
                    return await response.json()
        else:
            raise NotImplementedError("Use sync variant of this method for requests")

    async def apost(self, url: str, **kwargs) -> Any:
        """Make an async POST request"""
        if self.http_client == "aiohttp":
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(url, **kwargs) as response:
                    return await response.json()
        else:
            raise NotImplementedError("Use sync variant of this method for requests")


class CacheClient:
    """
    Unified cache client interface for both variants.
    """

    def __init__(self, variant: str = "S"):
        self.variant = variant.upper()
        import redis

        redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
        self.redis_client = redis.from_url(redis_url)

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        return self.redis_client.get(key)

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set value in cache"""
        return self.redis_client.set(key, value, ex=ex)

    def delete(self, key: str) -> int:
        """Delete key from cache"""
        return self.redis_client.delete(key)

    async def aget(self, key: str) -> Optional[Any]:
        """Async get value from cache (for Variant A)"""
        if self.variant == "A":
            import redis.asyncio as redis

            redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
            async with redis.from_url(redis_url) as redis:
                return await redis.get(key)
        else:
            return self.get(key)

    async def aset(
        self, key: str, value: Any, ex: Optional[int] = None
    ) -> bool:
        """Async set value in cache (for Variant A)"""
        if self.variant == "A":
            import redis.asyncio as redis

            redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
            async with redis.from_url(redis_url) as redis:
                return await redis.set(key, value, ex=ex)
        else:
            return self.set(key, value, ex)


def get_worker_count() -> int:
    """
    Calculate worker count based on CPU cores.
    Formula: workers = 2 * cpu_count + 1
    """
    import multiprocessing

    cpu_count = multiprocessing.cpu_count()
    return 2 * cpu_count + 1


def setup_environment():
    """
    Load environment variables from .env file if it exists.
    """
    import django
    from django.conf import settings

    env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_file):
        from dotenv import load_dotenv

        load_dotenv(env_file)

