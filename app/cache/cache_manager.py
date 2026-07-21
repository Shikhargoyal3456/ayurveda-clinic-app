from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from app.config import settings
from services.cache_service import cache


@dataclass
class PageCacheEntry:
    content: Any
    etag: str


def cache_key(name: str, scope: str = "public") -> str:
    raw = f"{scope}:{name}"
    return "page:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_etag(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_cached_page(name: str, scope: str = "public") -> PageCacheEntry | None:
    value = cache.get_json(cache_key(name, scope))
    if not value:
        return None
    return PageCacheEntry(content=value["content"], etag=value["etag"])


def set_cached_page(name: str, content: Any, *, scope: str = "public", ttl_seconds: int | None = None) -> None:
    cache.set_json(
        cache_key(name, scope),
        {"content": content, "etag": build_etag(str(content))},
        ttl_seconds or settings.cache_ttl_seconds,
    )

