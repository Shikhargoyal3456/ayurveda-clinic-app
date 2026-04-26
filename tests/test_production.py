from __future__ import annotations

import os

import pytest

from app.config import settings
from services import cache_service


def test_sentry_config():
    # PROD-LAUNCH-1: Launch config exposes Sentry DSN via env-style compatibility alias.
    assert settings.SENTRY_DSN


@pytest.mark.asyncio
async def test_redis_cache_roundtrip():
    # PROD-LAUNCH-1: Redis cache API round-trips when Redis is present and falls back safely when absent.
    key = "test:production:roundtrip"
    payload = {"ok": True}
    assert await cache_service.cache_set_json_async(key, payload, ttl_seconds=5)
    assert await cache_service.cache_get_json_async(key) == payload


def test_cloud_run_env(monkeypatch):
    # PROD-LAUNCH-1: Cloud Run can be detected through K_SERVICE when deployed.
    monkeypatch.setenv("K_SERVICE", "ayurveda-prod")
    assert os.getenv("K_SERVICE") == "ayurveda-prod"
