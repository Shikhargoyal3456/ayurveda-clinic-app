import pytest

from tests.conftest import extract_csrf_token


pytestmark = pytest.mark.asyncio


async def test_full_flow(client):
    # POLISH-9-SMOKE-TEST: Health check should be stable.
    health = await client.get("/health")
    assert health.status_code == 200

    # POLISH-9-SMOKE-TEST: Public medicines entry should reuse the existing ordering route.
    medicines_entry = await client.get("/medicines", follow_redirects=False)
    assert medicines_entry.status_code in {307, 308}
    assert medicines_entry.headers["location"] == "/order-medicines"

    # POLISH-9-SMOKE-TEST: Medicines catalog should load without requiring DB seed data.
    medicines = await client.get("/patient/medicines")
    assert medicines.status_code == 200
    assert isinstance(medicines.json(), list)

    # POLISH-9-SMOKE-TEST: AI suggest route should return a safe response, even if provider fallback is used.
    order_page = await client.get("/order-medicines")
    assert order_page.status_code == 200
    csrf_token = extract_csrf_token(order_page.text)
    ai_response = await client.post(
        "/order-medicines/ai-suggest",
        data={"symptoms": "acidity", "csrf_token": csrf_token},
    )
    assert ai_response.status_code == 200
    assert "suggested_medicines" in ai_response.json()

    # POLISH-9-SMOKE-TEST: Order create guard should fail safely, not crash, when data is invalid.
    guarded_order = await client.post(
        "/patient/order/create",
        data={
            "patient_name": "Smoke Patient",
            "patient_phone": "9999999999",
            "patient_address": "Smoke Address",
            "medicines_json": "[]",
            "pharmacy_id": "1",
            "csrf_token": csrf_token,
        },
    )
    assert guarded_order.status_code in {400, 404}



async def test_checkout_docs_visible_for_doctor(authenticated_client):
    # POLISH-9-SMOKE-TEST: Razorpay test-card docs should be visible in checkout UI.
    payments = await authenticated_client["client"].get("/payments/daily")
    assert payments.status_code == 200
    assert "4111 1111 1111 1111" in payments.text


async def test_admin_access(admin_client):
    # POLISH-9-SMOKE-TEST: Admin dashboard should be protected but reachable for admin.
    admin = await admin_client["client"].get("/admin")
    assert admin.status_code == 200
