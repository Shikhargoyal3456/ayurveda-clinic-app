import pytest

from app.config import settings
from app.rag_engine import RetrievalResult, get_rag_engine
def test_fallback_mode_is_used_when_ai_disabled(monkeypatch):
    engine = get_rag_engine()
    original = settings.ai_enabled
    object.__setattr__(settings, "ai_enabled", False)
    try:
        monkeypatch.setattr(
            engine,
            "retrieve",
            lambda query, top_k=3: [
                RetrievalResult(
                    source_file="charaka_samhita.pdf",
                    text="Guduchi is frequently used in digestive imbalance references.",
                    score=0.95,
                    chunk_id="chunk-1",
                )
            ],
        )

        payload = engine.generate_clinical_response("Burning after meals")

        assert payload["mode"] == "fallback"
        assert "fallback" in payload["warning"].lower()
        assert payload["sources"] == ["charaka_samhita.pdf"]
    finally:
        object.__setattr__(settings, "ai_enabled", original)


def test_fallback_response_is_cached(monkeypatch):
    engine = get_rag_engine()
    original = settings.ai_enabled
    object.__setattr__(settings, "ai_enabled", False)
    calls = {"count": 0}
    try:
        def fake_retrieve(query, top_k=3):
            calls["count"] += 1
            return [
                RetrievalResult(
                    source_file="charaka_samhita.pdf",
                    text="Digestive care passages.",
                    score=0.9,
                    chunk_id="chunk-2",
                )
            ]

        monkeypatch.setattr(engine, "retrieve", fake_retrieve)

        first = engine.generate_clinical_response("Acidity and heat")
        second = engine.generate_clinical_response("Acidity and heat")

        assert first["mode"] == "fallback"
        assert second["mode"] == "fallback"
        assert calls["count"] == 1
    finally:
        object.__setattr__(settings, "ai_enabled", original)


@pytest.mark.asyncio
async def test_ai_status_endpoint_reports_fallback(authenticated_client, monkeypatch):
    client = authenticated_client["client"]
    engine = get_rag_engine()

    # Patch the correct function
    monkeypatch.setattr(
        engine,
        "ollama_status",
        lambda timeout_seconds=2, allow_retries=False: {
            "status": "degraded",
            "available": False,
            "mode": "fallback",
            "warning": "offline",
            "model": "llama2",
            "provider": "ollama",
            "url": "http://localhost:11434",
        },
    )

    response = await client.get("/api/ai/status")

    assert response.status_code == 200
    payload = response.json()

    # Validate rag_engine reflects fallback
    assert payload["rag_engine"]["mode"] == "fallback"
    assert payload["rag_engine"]["warning"] == "offline"

    # Strategy must reflect truth (not falsely claim LLM usage)
    assert payload["active_strategy"] in (
        "groq_configured_rag_fallback",
        "fallback_only",
    )

    # Structural validation
    assert "groq" in payload
    assert "ollama" in payload
    assert "rag_engine" in payload
