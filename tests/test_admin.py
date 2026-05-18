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
    assert "Admin Dashboard" in response.text
    assert "Platform Overview" in response.text
    assert "Recent Orders" in response.text
    assert "Recent Registrations" in response.text
    assert "System Status" in response.text
    assert ">Home<" not in response.text
    assert ">Consult<" not in response.text
    assert ">Medicines<" not in response.text
    assert 'id="totalUsers"' in response.text
    assert 'id="recentOrders"' in response.text
    assert 'id="recentUsers"' in response.text
    assert "chart.js" not in response.text.lower()
    assert "/ws/admin/activity" not in response.text
    assert "admin-analytics.js" not in response.text


async def test_admin_dashboard_alias_renders(admin_client):
    client = admin_client["client"]

    response = await client.get("/admin/dashboard")

    assert response.status_code == 200
    assert "Admin Dashboard" in response.text


async def test_admin_simple_endpoints_render(admin_client):
    client = admin_client["client"]

    dashboard = await client.get("/admin")
    users = await client.get("/api/admin/users/recent?limit=5")
    orders = await client.get("/api/admin/orders/recent?limit=5")
    users_page = await client.get("/admin/users")
    orders_page = await client.get("/admin/orders")

    assert dashboard.status_code == 200
    assert users.status_code == 200
    assert orders.status_code == 200
    assert users_page.status_code == 200
    assert orders_page.status_code == 200
    assert isinstance(users.json(), list)
    assert isinstance(orders.json(), list)
