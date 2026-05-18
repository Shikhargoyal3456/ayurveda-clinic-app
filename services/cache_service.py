from __future__ import annotations

import json
import logging
import time
from functools import wraps
from hashlib import md5
from typing import Any

from app.config import settings


_LOCAL_ASYNC_CACHE: dict[str, Any] = {}
_LOCAL_CACHE_EXPIRY: dict[str, float] = {}
logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self) -> None:
        self._sync_client = None
        self._async_client = None
        self._connect()

    def _connect(self) -> None:
        if not settings.cache_enabled or not settings.redis_url:
            return
        try:
            import redis  # type: ignore

            self._sync_client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
            self._sync_client.ping()
        except Exception as exc:
            logger.warning("Redis sync cache unavailable: %s", exc)
            self._sync_client = None
        try:
            import redis.asyncio as redis_async  # type: ignore

            self._async_client = redis_async.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
        except Exception as exc:
            logger.warning("Redis async cache unavailable: %s", exc)
            self._async_client = None

    def _make_key(self, func_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        payload = f"{func_name}:{repr(args)}:{repr(sorted(kwargs.items()))}"
        return md5(payload.encode("utf-8")).hexdigest()

    def _local_get(self, key: str) -> Any | None:
        expires_at = _LOCAL_CACHE_EXPIRY.get(key, 0)
        if expires_at and expires_at < time.time():
            _LOCAL_ASYNC_CACHE.pop(key, None)
            _LOCAL_CACHE_EXPIRY.pop(key, None)
            return None
        return _LOCAL_ASYNC_CACHE.get(key)

    def _local_set(self, key: str, value: Any, ttl_seconds: int) -> None:
        _LOCAL_ASYNC_CACHE[key] = value
        _LOCAL_CACHE_EXPIRY[key] = time.time() + ttl_seconds

    def cached(self, ttl: int = 300):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                cache_key = self._make_key(func.__name__, args, kwargs)
                cached_value = await self.get_json_async(cache_key)
                if cached_value is not None:
                    return cached_value
                result = await func(*args, **kwargs)
                await self.set_json_async(cache_key, result, ttl)
                return result

            return wrapper

        return decorator

    async def get_or_set(self, key: str, fetch_func, ttl: int = 300):
        cached_value = await self.get_json_async(key)
        if cached_value is not None:
            return cached_value
        result = await fetch_func()
        await self.set_json_async(key, result, ttl)
        return result

    async def get_json_async(self, key: str) -> Any | None:
        if self._async_client is not None:
            try:
                value = await self._async_client.get(key)
                return json.loads(value) if value else None
            except Exception as exc:
                logger.warning("Async cache read failed for %s: %s", key, exc)
        return self._local_get(key)

    async def set_json_async(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        if self._async_client is not None:
            try:
                await self._async_client.setex(key, ttl_seconds, json.dumps(value))
                return True
            except Exception as exc:
                logger.warning("Async cache write failed for %s: %s", key, exc)
        self._local_set(key, value, ttl_seconds)
        return True

    def get_json(self, key: str) -> Any | None:
        if self._sync_client is not None:
            try:
                value = self._sync_client.get(key)
                return json.loads(value) if value else None
            except Exception as exc:
                logger.warning("Cache read failed for %s: %s", key, exc)
        return self._local_get(key)

    def set_json(self, key: str, value: Any, ttl_seconds: int = 900) -> None:
        if self._sync_client is not None:
            try:
                self._sync_client.setex(key, ttl_seconds, json.dumps(value))
                return
            except Exception as exc:
                logger.warning("Cache write failed for %s: %s", key, exc)
        self._local_set(key, value, ttl_seconds)

    def invalidate(self, pattern: str) -> None:
        if self._sync_client is not None:
            try:
                keys = self._sync_client.keys(pattern)
                if keys:
                    self._sync_client.delete(*keys)
            except Exception as exc:
                logger.warning("Cache invalidation failed for %s: %s", pattern, exc)
        stale = [key for key in _LOCAL_ASYNC_CACHE if pattern == "*" or pattern.rstrip("*") in key]
        for key in stale:
            _LOCAL_ASYNC_CACHE.pop(key, None)
            _LOCAL_CACHE_EXPIRY.pop(key, None)


class IntelligentCache:
    """
    Smart caching for AI responses with normalized semantic-style keys.
    Uses the shared cache service with Redis/local fallback.
    """

    def __init__(self, base_cache: CacheService) -> None:
        self.base_cache = base_cache

    def ai_cache_key(self, query: str, context: dict[str, Any] | None = None) -> str:
        normalized_query = str(query or "").strip().lower()
        safe_context = context or {}
        key_data = f"{normalized_query}:{json.dumps(safe_context, sort_keys=True, default=str)}"
        return f"ai_cache:{md5(key_data.encode('utf-8')).hexdigest()}"

    async def get_or_generate(
        self,
        query: str,
        context: dict[str, Any] | None,
        generator_func,
        ttl: int = 3600,
    ) -> Any:
        cache_key = self.ai_cache_key(query, context)
        cached = await self.base_cache.get_json_async(cache_key)
        if cached is not None:
            return cached
        result = await generator_func()
        await self.base_cache.set_json_async(cache_key, result, ttl)
        return result


cache = CacheService()
intelligent_cache = IntelligentCache(cache)
redis_client = cache._sync_client


def redis_health_status() -> dict[str, Any]:
    # GRAND-UNIFIED-1: Optional Redis monitoring; app remains healthy without Redis.
    if not settings.redis_url:
        return {"status": "not_configured", "configured": False}
    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        return {"status": "ok", "configured": True}
    except Exception as exc:
        return {"status": "degraded", "configured": True, "error": str(exc)}


async def redis_ping() -> bool | None:
    # PROD-LAUNCH-1: Async Redis ping for health/smoke tests; missing Redis is graceful.
    if not settings.redis_url:
        return None
    try:
        import redis.asyncio as redis  # type: ignore

        client = redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
        try:
            return bool(await client.ping())
        finally:
            await client.aclose()
    except Exception:
        return False


async def cache_set_json_async(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    return await cache.set_json_async(key, value, ttl_seconds)


async def cache_get_json_async(key: str) -> Any | None:
    return await cache.get_json_async(key)


async def cache_pharmacies(key: str, data: Any, ttl: int = 3600) -> bool:
    # PROD-LAUNCH-1: Named helper requested for pharmacy caching.
    return await cache_set_json_async(f"pharmacies:{key}", data, ttl)


async def cache_medicines(key: str, data: Any, ttl: int = 3600) -> bool:
    # PROD-LAUNCH-1: Named helper requested for medicine caching.
    return await cache_set_json_async(f"medicines:{key}", data, ttl)


def cache_get_json(key: str) -> Any | None:
    return cache.get_json(key)


def cache_set_json(key: str, value: Any, ttl_seconds: int = 900) -> None:
    cache.set_json(key, value, ttl_seconds)


def cache_result(ttl: int = 300):
    """Compatibility decorator for async routes/services with Redis + local fallback."""
    return cache.cached(ttl=ttl)
