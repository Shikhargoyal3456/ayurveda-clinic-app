import pytest

from app.auth import _RATE_LIMIT_BUCKETS
from app.rag_engine import get_rag_engine
from app.security import validate_password_complexity
from tests.conftest import extract_csrf_token


def test_password_complexity_validation():
    assert validate_password_complexity("weak") != []
    assert validate_password_complexity("StrongPass123!") == []


@pytest.mark.asyncio
async def test_rate_limiting_returns_429(authenticated_client, monkeypatch):
    client = authenticated_client["client"]
    engine = get_rag_engine()
    from routers import ai as ai_router

    monkeypatch.setattr(
        engine,
        "generate_clinical_response",
        lambda symptoms, patient_context="": {"answer": "ok", "sources": [], "context_passages": [], "mode": "fallback"},
    )
    monkeypatch.setattr(
        ai_router,
        "get_ai_response",
        lambda prompt, mode="samhita", context=None: {"answer": "ok", "sources": [], "context_passages": [], "mode": mode, "provider": "mock"},
    )
    analyzer_page = await client.get("/ai-analyzer", follow_redirects=False)
    if analyzer_page.status_code == 200:
        csrf_token = extract_csrf_token(analyzer_page.text)
    else:
        dashboard_page = await client.get("/dashboard")
        assert dashboard_page.status_code == 200
        csrf_token = extract_csrf_token(dashboard_page.text)

    for _ in range(10):
        response = await client.post(
            "/api/ai/analyze",
            json={"symptoms": "burning"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

    limited = await client.post(
        "/api/ai/analyze",
        json={"symptoms": "burning"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert limited.status_code == 429
    assert limited.headers["retry-after"]
    _RATE_LIMIT_BUCKETS.clear()


@pytest.mark.asyncio
async def test_session_timeout_redirects_to_login(authenticated_client, monkeypatch):
    client = authenticated_client["client"]
    monkeypatch.setattr("app.auth.session_timed_out", lambda request: True)

    response = await client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
