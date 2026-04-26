import pytest

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
    assert "Describe your symptoms" in payload["precautions"][0]


async def test_order_medicines_ai_suggest_falls_back_without_crashing(client, monkeypatch):
    from routers import order_medicines

    def failing_chat(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(order_medicines.ai_provider, "chat_with_fallback", failing_chat)

    page = await client.get("/order-medicines")
    csrf_token = extract_csrf_token(page.text)

    response = await client.post(
        "/order-medicines/ai-suggest",
        data={"symptoms": "acidity", "csrf_token": csrf_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggested_medicines"] == ["Avipattikar Churna", "Hingvastak Churna", "Triphala"]
    assert "AI suggestions are temporarily unavailable." in payload["precautions"]
    assert payload["provider"] == "fallback"
    assert payload["disclaimer"] == "AI suggestions are advisory. Consult a doctor if needed."


async def test_order_medicines_ai_suggest_maps_generic_ai_terms_to_catalog_names(client, monkeypatch):
    from routers import order_medicines

    def generic_chat(*args, **kwargs):
        return (
            '{"suggested_medicines":["Antacids","Proton pump inhibitors","Acetaminophen"],'
            '"precautions":["Take only as directed."]}',
            AIProvider.GEMINI,
        )

    monkeypatch.setattr(order_medicines.ai_provider, "chat_with_fallback", generic_chat)

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
