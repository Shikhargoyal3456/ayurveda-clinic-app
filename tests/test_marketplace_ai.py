from __future__ import annotations

import pytest

from models.medicine import Medicine


pytestmark = pytest.mark.asyncio


async def test_marketplace_nearby_shops_and_routing(client):
    await client.get("/portal")

    nearby_response = await client.get("/api/marketplace/nearby-shops")
    assert nearby_response.status_code == 200, nearby_response.text
    nearby_payload = nearby_response.json()
    assert nearby_payload["pharmacies"]
    assert nearby_payload["labs"]

    candidate_ids = [item["id"] for item in nearby_payload["pharmacies"][:3]]
    route_response = await client.post(
        "/api/marketplace/route-order",
        json={
            "pharmacy_ids": candidate_ids,
            "user_location": {"lat": 28.4595, "lng": 77.0266},
            "medicines": [],
        },
    )
    assert route_response.status_code == 200, route_response.text
    route_payload = route_response.json()
    assert route_payload["selected_pharmacy"] in candidate_ids
    assert "reason" in route_payload


async def test_marketplace_dynamic_price(client, db_session):
    await client.get("/portal")
    medicine = db_session.query(Medicine).order_by(Medicine.id.asc()).first()
    assert medicine is not None

    response = await client.post(
        "/api/marketplace/dynamic-price",
        json={"product_id": medicine.id, "user_context": {"user_id": 7}},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["product_id"] == medicine.id
    assert payload["dynamic_price"] > 0


async def test_business_owner_and_lab_endpoints(client):
    await client.get("/portal")

    register_pharmacy = await client.post(
        "/api/pharmacy/register",
        json={
            "store_name": "Marketplace Care Pharmacy",
            "address": "Sector 21, Gurugram",
            "phone": "9999999999",
            "city": "Gurugram",
            "pincode": "122001",
        },
    )
    assert register_pharmacy.status_code == 200, register_pharmacy.text
    store_id = register_pharmacy.json()["store_id"]

    live_orders = await client.get(f"/api/pharmacy/orders/live?store_id={store_id}")
    assert live_orders.status_code == 200, live_orders.text
    assert "orders" in live_orders.json()

    register_lab = await client.post(
        "/api/lab/register",
        json={"lab_name": "Marketplace Diagnostics", "address": "Sector 30, Gurugram"},
    )
    assert register_lab.status_code == 200, register_lab.text

    manage_tests = await client.get("/api/lab/tests/manage")
    assert manage_tests.status_code == 200, manage_tests.text
    assert "tests" in manage_tests.json()
