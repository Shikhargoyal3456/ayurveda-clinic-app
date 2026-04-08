import pytest


pytestmark = pytest.mark.asyncio


async def test_admin_metrics_requires_admin(authenticated_client):
    client = authenticated_client["client"]

    response = await client.get("/api/admin/metrics")

    assert response.status_code == 403
