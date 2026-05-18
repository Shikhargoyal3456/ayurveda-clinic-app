from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


async def test_simple_patient_pages_are_easy_to_use(client):
    home = await client.get("/")
    assert home.status_code == 200
    assert "ORDER MEDICINES" in home.text or "Order medicines" in home.text
    assert "UPLOAD PRESCRIPTION" in home.text or "Upload Prescription" in home.text
    assert "TRACK ORDER" in home.text or "Track Orders" in home.text

    search = await client.get("/order-medicines")
    assert search.status_code == 200
    assert "Place Order" in search.text
    assert "Your Cart" in search.text
    assert "Search Results" in search.text
    assert "Upload Prescription" in search.text
    assert "Start typing medicine name" in search.text

    orders = await client.get("/orders")
    assert orders.status_code == 200
    assert "Track Orders" in orders.text
    assert "Contact Delivery Partner" in orders.text
    assert "Reorder Same Items" in orders.text

    health = await client.get("/my-health")
    assert health.status_code == 200
    assert "My Health" in health.text
    assert "Set Reminder" in health.text
    assert "Consult Doctor" in health.text

    history = await client.get("/api/prescription/history")
    assert history.status_code == 200
    assert isinstance(history.json(), list)

    consult = await client.get("/telemedicine/book")
    assert consult.status_code == 200
    assert "Start Consultation" in consult.text
    assert "Choose a doctor" in consult.text

    contact = await client.get("/contact")
    assert contact.status_code == 200
    assert "Contact Us" in contact.text
    assert "9350397175" in contact.text
    assert "goyalshikhar67@gmail.com" in contact.text


async def test_contact_form_endpoint_returns_success(client):
    response = await client.post(
        "/api/contact/submit",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "phone": "9876543210",
            "subject": "Order Issue",
            "message": "Need help with my order.",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True


async def test_marketplace_portals_load(client):
    selector = await client.get("/portal")
    assert selector.status_code == 200
    assert "India's most trusted healthcare platform" in selector.text

    patient = await client.get("/portal/patient")
    assert patient.status_code in {200, 303}
    if patient.status_code == 200:
        assert "My Health" in patient.text
    else:
        assert "/auth/login" in patient.headers.get("location", "")

    pharmacy = await client.get("/portal/pharmacy")
    assert pharmacy.status_code in {200, 303}
    if pharmacy.status_code == 200:
        assert "Real-time order queue" in pharmacy.text
    else:
        assert "/auth/login" in pharmacy.headers.get("location", "")


async def test_delivery_find_assign_and_track(client, admin_client):
    await client.get("/portal")

    find_response = await client.post(
        "/api/delivery/find-pharmacy",
        json={"user_location": {"lat": 28.4595, "lng": 77.0266}, "medicines": []},
    )
    assert find_response.status_code == 200, find_response.text
    find_payload = find_response.json()
    assert find_payload["pharmacy"] is not None
    assert find_payload["eta_minutes"] is not None

    admin = admin_client["client"]
    assign_response = await admin.post(
        "/api/delivery/assign/9991",
        json={
            "pharmacy_location": {"lat": 28.4595, "lng": 77.0266},
            "customer_location": {"lat": 28.4710, "lng": 77.0440},
        },
    )
    assert assign_response.status_code == 200, assign_response.text
    assign_payload = assign_response.json()
    assert assign_payload["status"] == "assigned"
    assert assign_payload["partner_id"] > 0

    track_response = await client.get("/api/delivery/track/9991")
    assert track_response.status_code == 200, track_response.text
    track_payload = track_response.json()
    assert track_payload["order_id"] == 9991
    assert "partner_location" in track_payload


async def test_delivery_prediction_and_batch_optimization(client, admin_client):
    await client.get("/portal")

    admin = admin_client["client"]
    optimize_response = await admin.post(
        "/api/delivery/optimize-batch",
        json=[
            {"id": 1, "delivery_pincode": "122001"},
            {"id": 2, "delivery_pincode": "122001"},
            {"id": 3, "delivery_pincode": "122002"},
        ],
    )
    assert optimize_response.status_code == 200, optimize_response.text
    optimize_payload = optimize_response.json()
    assert "122001" in optimize_payload
    assert optimize_payload["122001"]["estimated_time"] == 20

    predict_response = await client.get("/api/delivery/predict-time/9991")
    assert predict_response.status_code == 200, predict_response.text
    predict_payload = predict_response.json()
    assert predict_payload["predicted_minutes"] > 0
    assert "factors" in predict_payload


async def test_delivery_assignment_redirects_to_partner_login_and_legacy_slug_alias_works(client):
    assign_response = await client.post(
        "/api/delivery/assign/9991",
        json={
            "pharmacy_location": {"lat": 28.4595, "lng": 77.0266},
            "customer_location": {"lat": 28.4710, "lng": 77.0440},
        },
        follow_redirects=False,
    )
    assert assign_response.status_code == 303
    assert assign_response.headers["location"] == "/auth/login/partner"

    partner_login = await client.get("/auth/login/partner")
    assert partner_login.status_code == 200
    assert "Delivery partner login" in partner_login.text

    legacy_slug = await client.get("/auth/login/delivery", follow_redirects=False)
    assert legacy_slug.status_code == 303
    assert legacy_slug.headers["location"] == "/auth/login/partner"
