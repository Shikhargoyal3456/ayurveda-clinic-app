import time

import pytest

import routers.ai as ai_router
from app.rag_engine import RetrievalResult, get_rag_engine
from tests.conftest import extract_csrf_token


pytestmark = pytest.mark.asyncio


async def test_ai_analyzer_returns_degraded_response_when_ollama_is_unavailable(authenticated_client, monkeypatch):
    client = authenticated_client["client"]
    engine = get_rag_engine()

    monkeypatch.setattr(engine, "ensure_ollama_available", lambda: (False, "Ollama unavailable during test"))
    monkeypatch.setattr(
        engine,
        "retrieve",
        lambda query, top_k=3: [
            RetrievalResult(
                source_file="charaka_samhita.pdf",
                text="Guduchi and light diet are classically used for ama-related digestive disturbance.",
                score=0.92,
                chunk_id="chunk-1",
            )
        ],
    )
    monkeypatch.setattr(
        ai_router,
        "get_ai_response",
        lambda symptoms, mode="samhita", context=None: {
            "answer": "Possible acidity-related digestive imbalance. Review agni, avoid irritants, and monitor severity.",
            "mode": mode,
            "provider": "gemini",
        },
    )

    analyzer_page = await client.get("/ai-analyzer")
    assert analyzer_page.status_code == 200
    csrf_token = extract_csrf_token(analyzer_page.text)

    response = await client.post(
        "/api/ai/analyze",
        json={"symptoms": "Burning after meals and sour belching"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) >= {"answer", "sources", "context_passages"}
    assert isinstance(payload["answer"], str)
    assert isinstance(payload["sources"], list)
    assert isinstance(payload["context_passages"], list)


async def test_ai_analyzer_returns_ai_response_when_context_is_available(authenticated_client, monkeypatch):
    client = authenticated_client["client"]
    engine = get_rag_engine()

    monkeypatch.setattr(
        engine,
        "retrieve",
        lambda query, top_k=3: [
            RetrievalResult(
                source_file="charaka_samhita.pdf",
                text="Digestive complaints should be matched with agni status and ama features before selecting herbs.",
                score=0.88,
                chunk_id="chunk-ollama-1",
            )
        ],
    )
    monkeypatch.setattr(
        ai_router,
        "get_ai_response",
        lambda symptoms, mode="samhita", context=None: {
            "answer": "Likely pitta-dominant digestive irritation with supportive dietary and review advice.",
            "mode": mode,
            "provider": "gemini",
        },
    )

    analyzer_page = await client.get("/ai-analyzer")
    assert analyzer_page.status_code == 200
    csrf_token = extract_csrf_token(analyzer_page.text)

    started = time.perf_counter()
    response = await client.post(
        "/api/ai/analyze",
        json={"symptoms": "Acidity, heat, and disturbed appetite for three days"},
        headers={"X-CSRF-Token": csrf_token},
    )
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"].strip()
    assert elapsed < 30


async def test_ai_analyzer_rejects_empty_input(authenticated_client):
    client = authenticated_client["client"]

    analyzer_page = await client.get("/ai-analyzer")
    assert analyzer_page.status_code == 200
    csrf_token = extract_csrf_token(analyzer_page.text)

    response = await client.post(
        "/api/ai/analyze",
        json={"symptoms": "   "},
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Symptoms are required."


async def test_ai_analyzer_rejects_oversized_input(authenticated_client):
    client = authenticated_client["client"]

    analyzer_page = await client.get("/ai-analyzer")
    assert analyzer_page.status_code == 200
    csrf_token = extract_csrf_token(analyzer_page.text)

    response = await client.post(
        "/api/ai/analyze",
        json={"symptoms": "a" * 2001},
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Symptoms must be 2000 characters or fewer."
