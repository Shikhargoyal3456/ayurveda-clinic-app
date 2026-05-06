from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


async def test_symptom_checker_page_loads(client):
    response = await client.get("/telemedicine/symptom-checker")
    assert response.status_code == 200
    assert "AI Symptom Checker" in response.text


async def test_ai_symptom_analysis_endpoint(client):
    response = await client.post("/api/telemedicine/analyze-symptoms", json={"symptoms": "I have fever and headache"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["urgency"] in {"low", "medium", "high"}
    assert "conditions" in payload


async def test_ai_support_response_endpoint(client):
    response = await client.post(
        "/api/ai/support/respond",
        json={"query": "where is my order", "user_context": {"last_order_id": 123}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["detected_intent"] == "order_status"
    assert payload["needs_human"] is False
