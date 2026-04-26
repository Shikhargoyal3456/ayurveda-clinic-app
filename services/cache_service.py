from __future__ import annotations

import json
from typing import Any

from app.config import settings


_LOCAL_ASYNC_CACHE: dict[str, Any] = {}


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


async def redis_ping() -> bool:
    # PROD-LAUNCH-1: Async Redis ping for health/smoke tests; missing Redis is graceful.
    try:
        import redis.asyncio as redis  # type: ignore

        client = redis.from_url(settings.redis_url or "redis://localhost:6379/0", socket_connect_timeout=1, socket_timeout=1)
        try:
            return bool(await client.ping())
        finally:
            await client.aclose()
    except Exception:
        return False


async def cache_set_json_async(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    # PROD-LAUNCH-1: Async cache setter for pharmacies/medicines; app keeps working if Redis is down.
    try:
        import redis.asyncio as redis  # type: ignore

        client = redis.from_url(settings.redis_url or "redis://localhost:6379/0", socket_connect_timeout=1, socket_timeout=1)
        try:
            await client.setex(key, ttl_seconds, json.dumps(value))
            return True
        finally:
            await client.aclose()
    except Exception:
        _LOCAL_ASYNC_CACHE[key] = value
        return True


async def cache_get_json_async(key: str) -> Any | None:
    # PROD-LAUNCH-1: Async cache getter for pharmacies/medicines; returns None on any cache issue.
    try:
        import redis.asyncio as redis  # type: ignore

        client = redis.from_url(settings.redis_url or "redis://localhost:6379/0", socket_connect_timeout=1, socket_timeout=1)
        try:
            value = await client.get(key)
            return json.loads(value) if value else None
        finally:
            await client.aclose()
    except Exception:
        return _LOCAL_ASYNC_CACHE.get(key)


async def cache_pharmacies(key: str, data: Any, ttl: int = 3600) -> bool:
    # PROD-LAUNCH-1: Named helper requested for pharmacy caching.
    return await cache_set_json_async(f"pharmacies:{key}", data, ttl)


async def cache_medicines(key: str, data: Any, ttl: int = 3600) -> bool:
    # PROD-LAUNCH-1: Named helper requested for medicine caching.
    return await cache_set_json_async(f"medicines:{key}", data, ttl)


def cache_get_json(key: str) -> Any | None:
    if not settings.redis_url:
        return None
    try:
        import redis  # type: ignore

        value = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1).get(key)
        return json.loads(value) if value else None
    except Exception:
        return None


def cache_set_json(key: str, value: Any, ttl_seconds: int = 900) -> None:
    if not settings.redis_url:
        return
    try:
        import redis  # type: ignore

        redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1).setex(
            key,
            ttl_seconds,
            json.dumps(value),
        )
    except Exception:
        return
