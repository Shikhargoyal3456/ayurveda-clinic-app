import pytest

from services.medicine_management import ensure_master_medicine
from services.ai_provider import AIProvider
from tests.conftest import extract_csrf_token


pytestmark = pytest.mark.asyncio


async def test_order_medicines_page_has_direct_ai_help_button(client):
    page = await client.get("/order-medicines")

    assert page.status_code == 200
    assert 'id="aiInput"' in page.text
    assert 'id="heroAiButton"' in page.text


async def test_order_medicines_ai_suggest_returns_empty_symptom_guidance(client):
    page = await client.get("/order-medicines")
    csrf_token = extract_csrf_token(page.text)

    response = await client.post(
        "/order-medicines/ai-suggest",
        data={"symptoms": "   ", "csrf_token": csrf_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggested_medicines"] == []
    assert "Symptoms are required" in payload["precautions"][0]


async def test_order_medicines_ai_suggest_falls_back_without_crashing(client, monkeypatch):
    from routers import order_medicines

    async def failing_json_call(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(order_medicines.ai_provider, "call_ai_json_with_retry", failing_json_call)
    monkeypatch.setattr(order_medicines, "logger", type("Logger", (), {"exception": staticmethod(lambda *args, **kwargs: None)})())

    page = await client.get("/order-medicines")
    csrf_token = extract_csrf_token(page.text)

    response = await client.post(
        "/order-medicines/ai-suggest",
        data={"symptoms": "acidity", "csrf_token": csrf_token},
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["suggested_medicines"] == []
    assert payload["provider"] == "error"
    assert "provider unavailable" in payload["error"]
    assert payload["disclaimer"] == "AI suggestions are advisory. Consult a doctor if needed."


async def test_order_medicines_ai_suggest_maps_generic_ai_terms_to_catalog_names(client, monkeypatch):
    from routers import order_medicines

    async def generic_chat(*args, **kwargs):
        return (
            {
                "suggested_medicines": ["Antacids", "Proton pump inhibitors", "Acetaminophen"],
                "precautions": ["Take only as directed."],
            },
            AIProvider.GEMINI.value,
        )

    monkeypatch.setattr(order_medicines.ai_provider, "call_ai_json_with_retry", generic_chat)

    page = await client.get("/order-medicines")
    csrf_token = extract_csrf_token(page.text)

    response = await client.post(
        "/order-medicines/ai-suggest",
        data={"symptoms": "acidity and headache", "csrf_token": csrf_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggested_medicines"] == ["Avipattikar Churna", "Hingvastak Churna", "Paracetamol"]
    assert payload["provider"] == "gemini"


async def test_medicine_search_returns_seeded_master_catalog_rows(client, db_session):
    ensure_master_medicine(
        db_session,
        name="Paracetamol 500mg",
        brand="Cipla",
        category="allopathy",
        mrp=50,
        price=35,
        prescription_required=False,
        description="General symptom support",
    )
    db_session.commit()

    response = await client.get("/api/medicines/search?q=paracetamol")

    assert response.status_code == 200
    payload = response.json()
    assert payload["medicines"]
    assert payload["medicines"][0]["name"] == "Paracetamol 500mg"
    assert payload["medicines"][0]["pharmacy_id"] == 1
