import asyncio

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.rate_limit import limiter


@pytest.mark.asyncio
async def test_unhandled_errors_return_safe_api_payload():
    route_count = len(app.router.routes)

    @app.get("/api/_test/production-error")
    async def _raise_unhandled_error():
        raise RuntimeError("boom")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/_test/production-error", headers={"accept": "application/json"})

    assert response.status_code == 500
    payload = response.json()
    assert payload["success"] is False
    assert "error" in payload
    assert "error_id" in payload

    del app.router.routes[route_count:]


@pytest.mark.asyncio
async def test_security_headers_are_present(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-XSS-Protection"] == "1; mode=block"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in response.headers


@pytest.mark.asyncio
async def test_deep_health_check_returns_monitoring_details(client):
    response = await client.get("/health/deep")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"healthy", "degraded", "unhealthy"}
    assert "checks" in payload
    assert "monitoring" in payload
    assert "database" in payload["checks"]
    assert "backup" in payload["checks"]


@pytest.mark.asyncio
async def test_rate_limiting_blocks_excess_requests():
    route_count = len(app.router.routes)

    @app.get("/api/_test/rate-limit")
    @limiter.limit("2/minute")
    async def _rate_limited_route(request: Request):
        return {"ok": True}

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.get("/api/_test/rate-limit", headers={"accept": "application/json"})
        second = await client.get("/api/_test/rate-limit", headers={"accept": "application/json"})
        third = await client.get("/api/_test/rate-limit", headers={"accept": "application/json"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429

    del app.router.routes[route_count:]


@pytest.mark.asyncio
async def test_concurrent_health_requests_do_not_fail(client):
    responses = await asyncio.gather(*[client.get("/health/deep") for _ in range(10)])

    assert all(response.status_code == 200 for response in responses)
