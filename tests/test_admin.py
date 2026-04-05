import pytest


pytestmark = pytest.mark.asyncio


async def test_admin_metrics_endpoint_returns_health(admin_client):
    client = admin_client["client"]

    response = await client.get("/api/admin/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert "totals" in payload
    assert "health" in payload
    assert "analytics" in payload


async def test_admin_dashboard_renders(admin_client):
    client = admin_client["client"]

    response = await client.get("/admin")

    assert response.status_code == 200
    assert "System Dashboard" in response.text
