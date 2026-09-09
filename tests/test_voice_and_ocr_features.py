import pytest
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import extract_csrf_token

client = TestClient(app)

def test_prescription_medicine_db_endpoint():
    response = client.get("/prescription/medicine-db?q=ashwagandha&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)

def test_prescription_ocr_endpoint_validation():
    # Sending invalid/empty upload should return 400 JSON instead of redirecting
    response = client.post("/api/prescription/decode-handwriting")
    assert response.status_code in [400, 422]
    # Verify response is valid JSON
    assert response.headers["content-type"].startswith("application/json")

def test_order_medicines_ai_suggest():
    page = client.get("/order-medicines")
    csrf_token = extract_csrf_token(page.text)
    response = client.post(
        "/order-medicines/ai-suggest",
        data={"symptoms": "Digestive bloating and acidity", "csrf_token": csrf_token},
        headers={"X-CSRF-Token": csrf_token}
    )
    assert response.status_code in [200, 503]
    if response.status_code == 200:
        data = response.json()
        assert "suggested_medicines" in data

