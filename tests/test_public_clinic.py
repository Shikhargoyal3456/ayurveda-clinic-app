from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_public_analyze_returns_dosha_plan():
    response = client.post("/analyze", json={"symptoms": "acidity and headache"})

    assert response.status_code == 200
    data = response.json()
    assert data["dominant_dosha"] in {"Vata", "Pitta", "Kapha"}
    assert set(data["dosha_scores"]) == {"Vata", "Pitta", "Kapha"}
    assert data["treatment"]
    assert data["medicines"]


def test_public_book_returns_payment_payload():
    response = client.post("/book", json={"symptoms": "acidity", "amount": 29900})

    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == 29900
    assert data["currency"] == "INR"
    assert "key_id" in data
