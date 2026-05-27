import base64
from uuid import uuid4

import pytest

from tests.conftest import extract_csrf_token


pytestmark = pytest.mark.asyncio


def _unique_phone() -> str:
    digits = "".join(str(int(char, 16) % 10) for char in uuid4().hex)
    return f"98{digits}"[:10]


async def _register_and_login_portal_user(client, role_slug: str, role_value: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    unique = uuid4().hex[:8]
    email = f"{role_slug}.{unique}@example.com"
    phone = _unique_phone()
    register_page = await client.get(f"/auth/register/{role_slug}")
    csrf_token = extract_csrf_token(register_page.text)
    payload = {
        "csrf_token": csrf_token,
        "role": role_value,
        "full_name": f"{role_slug.title()} User",
        "email": email,
        "phone": phone,
        "password": "PortalSecure123!",
    }
    payload.update(extra or {})
    register_response = await client.post("/api/auth/register", data=payload, headers={"X-CSRF-Token": csrf_token})
    assert register_response.status_code == 200
    verification_token = register_response.json()["verification_token"]
    await client.get(f"/auth/verify-email?token={verification_token}", follow_redirects=False)

    login_page = await client.get(f"/auth/login/{role_slug}")
    login_csrf = extract_csrf_token(login_page.text)
    login_response = await client.post(
        "/auth/login",
        data={"csrf_token": login_csrf, "identifier": email, "password": "PortalSecure123!", "role": role_value},
        follow_redirects=False,
    )
    assert login_response.status_code == 303
    return {"email": email, "phone": phone}


async def _seed_medicine(admin_client, name: str, brand: str, category: str, mrp: str, price: str):
    admin = admin_client["client"]
    page = await admin.get("/admin/add-medicine")
    csrf_token = extract_csrf_token(page.text)
    response = await admin.post(
        "/api/admin/medicines/add",
        data={"csrf_token": csrf_token, "name": name, "brand": brand, "category": category, "mrp": mrp, "price": price, "stock": "20"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200


async def _logout_portal_user(client):
    page = await client.get("/profiles/add")
    assert page.status_code == 200
    csrf_token = extract_csrf_token(page.text)
    response = await client.post(
        "/auth/logout",
        data={"csrf_token": csrf_token},
        headers={"X-CSRF-Token": csrf_token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return response


async def test_patient_prescription_analysis_history_and_order_prefill(client, admin_client):
    await _seed_medicine(admin_client, "Paracetamol 500mg", "HealthBrand", "allopathy", "50", "32")
    await _seed_medicine(admin_client, "Omeprazole 20mg", "AcidCare", "allopathy", "80", "55")
    await _register_and_login_portal_user(client, "patient", "patient")

    text = "Tab Paracetamol 500mg twice daily for 5 days\nCap Omeprazole 20mg once daily before food"
    image_payload = "data:image/jpeg;base64," + base64.b64encode(text.encode("utf-8")).decode("utf-8")
    analyze_response = await client.post("/api/prescription/analyze", json={"image": image_payload})
    assert analyze_response.status_code == 200
    result = analyze_response.json()
    assert result["medicines"]
    assert any("Paracetamol" in item["name"] for item in result["medicines"])
    assert result["id"] > 0

    history_response = await client.get("/api/prescription/history")
    assert history_response.status_code == 200
    history = history_response.json()
    assert history
    assert history[0]["id"] == result["id"]

    order_page = await client.get(f"/order-medicines?source=prescription&prescription_id={result['id']}")
    assert order_page.status_code == 200
    assert "Paracetamol 500mg" in order_page.text


async def test_medicine_info_and_pharmacy_verification_flow(client, admin_client):
    await _seed_medicine(admin_client, "Paracetamol 650mg", "QuickRelief", "allopathy", "60", "42")
    await _register_and_login_portal_user(client, "patient", "patient")
    image_payload = "data:image/jpeg;base64," + base64.b64encode(b"Tab Paracetamol 650mg twice daily for 3 days").decode("utf-8")
    analyze_response = await client.post("/api/prescription/analyze", json={"image": image_payload})
    prescription_id = analyze_response.json()["id"]
    await _logout_portal_user(client)

    await _register_and_login_portal_user(
        client,
        "pharmacy",
        "pharmacy_owner",
        extra={"pharmacy_name": "Verify Pharmacy", "gst_number": f"GST{uuid4().hex[:8].upper()}", "license_number": f"LIC{uuid4().hex[:8].upper()}", "address": "Sector 21"},
    )
    add_response = await client.post(
        "/api/pharmacy/medicines/add",
        data={"name": "Paracetamol 650mg", "brand": "QuickRelief", "category": "allopathy", "mrp": "60", "price": "42", "stock": "14", "expiry_date": "2027-12-31", "prescription_required": "1"},
    )
    assert add_response.status_code == 200

    info_response = await client.get("/api/medicine/info/Paracetamol 650mg")
    assert info_response.status_code == 200
    info = info_response.json()
    assert "Fever" in info["uses"] or "pain" in info["uses"].lower()
    assert info["prices"]

    verify_response = await client.post("/api/prescription/verify", json={"prescription_id": prescription_id})
    assert verify_response.status_code == 200
    verify_payload = verify_response.json()
    assert "confidence" in verify_payload


async def test_doctor_interaction_check_and_eprescription_generation(client):
    await _register_and_login_portal_user(
        client,
        "doctor",
        "doctor",
        extra={"specialization": "General Medicine", "qualification": "MBBS", "registration_number": f"REG{uuid4().hex[:8].upper()}"},
    )

    interaction_response = await client.post(
        "/api/prescription/check-interactions",
        json={"medicines": [{"name": "Atorvastatin 10mg"}, {"name": "Clarithromycin 250mg"}]},
    )
    assert interaction_response.status_code == 200
    interaction_payload = interaction_response.json()
    assert interaction_payload["has_interactions"] is True

    generate_response = await client.post(
        "/api/doctor/e-prescription/generate",
        json={
            "patient_name": "Portal Patient",
            "medicines": [
                {"name": "Paracetamol 500mg", "dosage": "500mg", "duration": "5 days", "instructions": "After food", "suggested_quantity": 10},
                {"name": "Omeprazole 20mg", "dosage": "20mg", "duration": "5 days", "instructions": "Before breakfast", "suggested_quantity": 10},
            ],
        },
    )
    assert generate_response.status_code == 200
    payload = generate_response.json()
    assert payload["success"] is True
    assert payload["download_url"].endswith("/download")
