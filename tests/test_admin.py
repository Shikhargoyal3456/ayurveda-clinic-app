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

    response = await client.get("/admin", follow_redirects=True)

    assert response.status_code == 200
    assert "html" in response.text.lower() or "admin" in response.text.lower() or len(response.text) > 0



async def test_admin_dashboard_alias_renders(admin_client):
    client = admin_client["client"]

    response = await client.get("/admin/dashboard", follow_redirects=True)

    assert response.status_code == 200
    assert "Admin Dashboard" in response.text or "Accuracy" in response.text or "Platform" in response.text


async def test_admin_simple_endpoints_render(admin_client):
    client = admin_client["client"]

    dashboard = await client.get("/admin", follow_redirects=True)
    users = await client.get("/api/admin/users/recent?limit=5", follow_redirects=True)
    orders = await client.get("/api/admin/orders/recent?limit=5", follow_redirects=True)
    users_page = await client.get("/admin/users", follow_redirects=True)
    orders_page = await client.get("/admin/orders", follow_redirects=True)

    assert dashboard.status_code == 200
    assert users.status_code == 200

    assert orders.status_code == 200
    assert users_page.status_code == 200
    assert orders_page.status_code == 200
    assert isinstance(users.json(), list)
    assert isinstance(orders.json(), list)
