from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

import requests


class AIFallback:
    def __init__(self, cache_path: Path | None = None, ttl_seconds: int = 24 * 3600, max_items: int = 100) -> None:
        base_dir = Path(__file__).resolve().parent.parent
        self.cache_path = cache_path or (base_dir / "data" / "ai_cache.json")
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._load_cache()

    def _load_cache(self) -> None:
        if not self.cache_path.exists():
            return
        try:
            raw_data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if isinstance(raw_data, list):
                for item in raw_data:
                    key = str(item.get("key", ""))
                    if key:
                        self._cache[key] = item
            self._purge_expired()
        except Exception:
            self._cache.clear()

    def _save_cache(self) -> None:
        self.cache_path.write_text(json.dumps(list(self._cache.values()), indent=2, ensure_ascii=True), encoding="utf-8")

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [key for key, value in self._cache.items() if float(value.get("expires_at", 0)) <= now]
        for key in expired:
            self._cache.pop(key, None)

    def _cache_key(self, query: str, context: str) -> str:
        payload = f"{query.strip().lower()}::{context.strip().lower()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _lookup(self, cache_key: str) -> dict[str, Any] | None:
        self._purge_expired()
        item = self._cache.get(cache_key)
        if item is None:
            self._misses += 1
            return None
        self._cache.move_to_end(cache_key)
        self._hits += 1
        return dict(item["payload"])

    def _remember(self, cache_key: str, payload: dict[str, Any]) -> None:
        self._purge_expired()
        if cache_key in self._cache:
            self._cache.pop(cache_key)
        while len(self._cache) >= self.max_items:
            self._cache.popitem(last=False)
            self._evictions += 1
        self._cache[cache_key] = {
            "key": cache_key,
            "created_at": time.time(),
            "expires_at": time.time() + self.ttl_seconds,
            "payload": payload,
        }
        self._save_cache()

    def _build_response_text(self, query: str, context: str) -> str:
        """Return neutral fallback - no hardcoded medical advice."""
        return (
            "Primary AI response is currently unavailable. "
            "Please retry shortly or consult a qualified clinician for tailored guidance."
        )

    def get_response(self, query: str, context: str = "") -> dict[str, Any]:
        cache_key = self._cache_key(query, context)
        cached = self._lookup(cache_key)
        if cached is not None:
            return cached

        payload = {
            "response": self._build_response_text(query, context),
            "source": "fallback",
            "topics": ["fallback"],
            "generated_at": int(time.time()),
        }
        self._remember(cache_key, payload)
        return payload

    def get_status(self) -> dict[str, Any]:
        self._purge_expired()
        return {
            "cache_size": len(self._cache),
            "max_items": self.max_items,
            "ttl_seconds": self.ttl_seconds,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "cache_path": str(self.cache_path),
        }


fallback_handler = AIFallback()


def fallback_health_status(probe_remote: bool = False) -> dict[str, Any]:
    if not probe_remote:
        return {
            "available": False,
            "checked": False,
            "mode": "probe_skipped",
        }
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return {"available": response.status_code < 500, "status_code": response.status_code, "checked": True}
    except requests.RequestException as exc:
        return {"available": False, "error": str(exc), "checked": True}
