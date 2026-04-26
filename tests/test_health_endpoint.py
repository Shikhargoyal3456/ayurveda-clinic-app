import pytest

from app.config import normalize_database_url, production_validation_errors, resolve_razorpay_mode


pytestmark = pytest.mark.asyncio


async def test_health_endpoint_returns_extended_status(client):
    response = await client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) >= {"status", "api", "database", "ai", "rag", "runtime"}
    assert payload["status"] == "ok"
    assert payload["api"] == "ok"
    assert payload["runtime"]["status"] in {"protected", "unbounded"}


async def test_appointments_and_followups_pages_render(authenticated_client):
    client = authenticated_client["client"]

    appointments_response = await client.get("/appointments")
    assert appointments_response.status_code == 200

    followups_response = await client.get("/followups")
    assert followups_response.status_code == 200


async def test_production_readiness_helpers_are_safe():
    assert production_validation_errors("production", "strong-secret", False, True) == [
        "HTTPS required: SESSION_HTTPS_ONLY must be true in production."
    ]
    assert production_validation_errors("production", "strong-secret", True, True) == []
    assert normalize_database_url("sqlite:///./ayurveda.db") == "sqlite:///./ayurveda.db?cache=shared&timeout=30"
    assert resolve_razorpay_mode("development") == "test"
    assert resolve_razorpay_mode("production") == "live"
