from __future__ import annotations

import base64

import pytest


pytestmark = pytest.mark.asyncio


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9pG7n3wAAAAASUVORK5CYII="
)


async def test_prescription_scanner_endpoint(client):
    response = await client.post(
        "/api/ai/scan-prescription",
        files={"file": ("prescription.txt", b"Tab Ashwagandha 500mg once daily for 5 days", "text/plain")},
        data={"user_id": "7"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "medicines" in payload
    assert payload["confidence"] > 0


async def test_voice_command_endpoint(client):
    response = await client.post(
        "/api/ai/voice-command",
        files={"file": ("voice.txt", b"track my latest order", "text/plain")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["intent"] == "track_order"
    assert payload["voice_response_base64"]


async def test_image_analysis_endpoint(client):
    response = await client.post(
        "/api/ai/analyze-symptom-image",
        files={"file": ("skin.png", PNG_1X1, "image/png")},
        data={"symptom_type": "skin"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["symptom_type"] == "skin"
    assert payload["possible_conditions"]


async def test_chatbot_memory_and_personalization_endpoints(client):
    chat = await client.post("/api/ai/chat/12", json={"message": "track my order"})
    assert chat.status_code == 200, chat.text
    chat_payload = chat.json()
    assert chat_payload["intent"] == "order_status"
    assert chat_payload["quick_replies"]

    feed = await client.get("/api/ai/feed/12")
    assert feed.status_code == 200, feed.text
    feed_payload = feed.json()
    assert "medicines" in feed_payload
    assert "offers" in feed_payload


async def test_predictions_endpoints(client):
    insights = await client.get("/api/ai/health-insights/4")
    assert insights.status_code == 200, insights.text
    assert "health_score" in insights.json()

    revenue = await client.get("/api/ai/forecast-revenue?days=10")
    assert revenue.status_code == 200, revenue.text
    revenue_payload = revenue.json()
    assert revenue_payload["forecasted_revenue"]

    churn = await client.get("/api/ai/churn-prediction")
    assert churn.status_code == 200, churn.text
    assert isinstance(churn.json(), list)
