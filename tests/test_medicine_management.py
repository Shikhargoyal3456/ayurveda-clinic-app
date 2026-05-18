import pytest
import json
from io import BytesIO
from uuid import uuid4

from tests.conftest import extract_csrf_token


pytestmark = pytest.mark.asyncio


async def _register_and_login_portal_pharmacy(client):
    unique = uuid4().hex[:8]
    email = f"pharmacy.owner.{unique}@example.com"
    phone = f"98{uuid4().hex[:8]}".replace("a", "1").replace("b", "2").replace("c", "3").replace("d", "4").replace("e", "5").replace("f", "6")[:10]
    register_page = await client.get("/auth/register/pharmacy")
    csrf_token = extract_csrf_token(register_page.text)
    register_response = await client.post(
        "/api/auth/register",
        data={
            "csrf_token": csrf_token,
            "role": "pharmacy_owner",
            "full_name": "Portal Pharmacy Owner",
            "email": email,
            "phone": phone,
            "password": "PortalSecure123!",
            "pharmacy_name": f"Portal Wellness Pharmacy {unique}",
            "gst_number": f"GST{unique.upper()}",
            "license_number": f"LIC{unique.upper()}",
            "address": "Sector 14, Gurugram",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    token = register_response.json()["verification_token"]
    await client.get(f"/auth/verify-email?token={token}", follow_redirects=False)

    login_page = await client.get("/auth/login/pharmacy")
    login_csrf = extract_csrf_token(login_page.text)
    login_response = await client.post(
        "/auth/login",
        data={
            "csrf_token": login_csrf,
            "identifier": email,
            "password": "PortalSecure123!",
            "role": "pharmacy_owner",
        },
        follow_redirects=False,
    )
    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/pharmacy"


async def test_admin_master_medicine_add_and_list(admin_client):
    client = admin_client["client"]

    page = await client.get("/admin/add-medicine")
    csrf_token = extract_csrf_token(page.text)

    response = await client.post(
        "/api/admin/medicines/add",
        data={
            "csrf_token": csrf_token,
            "name": "Paracetamol 650mg Test",
            "category": "allopathy",
            "brand": "Cipla",
            "mrp": "60",
            "price": "45",
            "stock": "25",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True

    list_response = await client.get("/api/admin/medicines?q=Paracetamol 650mg Test")
    assert list_response.status_code == 200
    rows = list_response.json()
    assert any(row["name"] == "Paracetamol 650mg Test" for row in rows)


async def test_pharmacy_owner_can_add_and_view_inventory(client):
    await _register_and_login_portal_pharmacy(client)

    add_response = await client.post(
        "/api/pharmacy/medicines/add",
        data={
            "name": "Ashwagandha Gold",
            "brand": "Dabur",
            "category": "ayurveda",
            "mrp": "250",
            "price": "199",
            "stock": "42",
            "expiry_date": "2027-12-31",
            "prescription_required": "0",
            "description": "Daily vitality support",
        },
    )
    assert add_response.status_code == 200
    assert add_response.json()["success"] is True

    inventory_response = await client.get("/api/pharmacy/inventory")
    assert inventory_response.status_code == 200
    rows = inventory_response.json()["inventory"]
    assert any(row["name"] == "Ashwagandha Gold" for row in rows)


async def test_patient_can_request_missing_medicine(client):
    response = await client.post(
        "/api/patient/request-medicine",
        json={"name": "Rare Syrup", "brand": "HealthBrand"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["request"]["medicine_name"] == "Rare Syrup"


async def test_pharmacy_owner_image_stock_and_expiry_features(client):
    await _register_and_login_portal_pharmacy(client)

    upload_response = await client.post(
        "/api/medicines/upload-image",
        files={"image": ("medicine.jpg", BytesIO(b"fake-image-data"), "image/jpeg")},
    )
    assert upload_response.status_code == 200
    image_url = upload_response.json()["image_url"]
    assert image_url

    add_response = await client.post(
        "/api/pharmacy/medicines/add",
        data={
            "name": "Expiry Test Capsule",
            "brand": "Wellness Labs",
            "category": "wellness",
            "mrp": "120",
            "price": "90",
            "stock": "4",
            "expiry_date": "2026-05-20",
            "prescription_required": "0",
            "image_urls": json.dumps([image_url]),
        },
    )
    assert add_response.status_code == 200

    inventory_response = await client.get("/api/pharmacy/inventory")
    rows = inventory_response.json()["inventory"]
    item = next(row for row in rows if row["name"] == "Expiry Test Capsule")
    assert item["image_url"] == image_url

    alerts_response = await client.get("/api/pharmacy/stock-alerts")
    assert alerts_response.status_code == 200
    alerts = alerts_response.json()
    assert any(alert["medicine_name"] == "Expiry Test Capsule" and alert["alert_level"] == "critical" for alert in alerts)

    expiry_response = await client.get("/api/pharmacy/expiry-alerts")
    assert expiry_response.status_code == 200
    expiry_payload = expiry_response.json()
    assert any(alert["medicine_name"] == "Expiry Test Capsule" for alert in expiry_payload["alerts"])


async def test_patient_alternatives_and_price_comparison(client, admin_client):
    admin = admin_client["client"]
    admin_page = await admin.get("/admin/add-medicine")
    csrf_token = extract_csrf_token(admin_page.text)

    medicines = [
        {"name": "Paracetamol Prime 500mg", "brand": "BrandA", "category": "allopathy", "mrp": "50", "price": "40", "stock": "50"},
        {"name": "Paracetamol Saver 500mg", "brand": "BrandB", "category": "allopathy", "mrp": "45", "price": "25", "stock": "50"},
        {"name": "Giloy Relief", "brand": "AyurHerb", "category": "ayurveda", "mrp": "35", "price": "20", "stock": "50"},
    ]
    for item in medicines:
        response = await admin.post(
            "/api/admin/medicines/add",
            data={"csrf_token": csrf_token, **item},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

    await _register_and_login_portal_pharmacy(client)
    add_response = await client.post(
        "/api/pharmacy/medicines/add",
        data={
            "name": "Paracetamol Saver 500mg",
            "brand": "BrandB",
            "category": "allopathy",
            "mrp": "45",
            "price": "25",
            "stock": "12",
            "expiry_date": "2027-12-31",
            "prescription_required": "0",
        },
    )
    assert add_response.status_code == 200

    alternatives_response = await client.get("/api/medicines/alternatives?medicine_name=Paracetamol Prime")
    assert alternatives_response.status_code == 200
    alternatives_payload = alternatives_response.json()
    assert alternatives_payload["original"]["name"] == "Paracetamol Prime 500mg"
    assert alternatives_payload["alternatives"]

    compare_response = await client.post(
        "/api/medicines/compare",
        json={"medicine_name": "Paracetamol Saver", "user_location": {"lat": 28.4595, "lng": 77.0266}},
    )
    assert compare_response.status_code == 200
    compare_payload = compare_response.json()
    assert compare_payload["medicine_name"] == "Paracetamol Saver 500mg"
    assert compare_payload["pharmacies"]

    deals_response = await client.get("/api/medicines/best-deals")
    assert deals_response.status_code == 200
    deals_payload = deals_response.json()
    assert any(item["medicine_name"] == "Paracetamol Saver 500mg" for item in deals_payload)
