import pytest


pytestmark = pytest.mark.asyncio


async def test_health_endpoint_returns_extended_status(client):
    response = await client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) >= {"status", "api", "database", "ai", "rag"}
    assert payload["status"] == "ok"
    assert payload["api"] == "ok"


async def test_appointments_and_followups_pages_render(authenticated_client):
    client = authenticated_client["client"]

    appointments_response = await client.get("/appointments")
    assert appointments_response.status_code == 200

    followups_response = await client.get("/followups")
    assert followups_response.status_code == 200
