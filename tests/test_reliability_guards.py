import shutil
import zipfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.rag_engine import RetrievalResult, get_rag_engine
from routers.ai import rebuild_status
import scripts.backup_db as backup_db_module

@pytest.mark.asyncio
async def test_global_exception_handler_returns_json_500():
    route_count = len(app.router.routes)

    @app.get("/_test/unhandled-error")
    async def _raise_unhandled_error():
        raise RuntimeError("boom")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/_test/unhandled-error", headers={"accept": "application/json"})

    assert response.status_code == 500
    payload = response.json()
    assert payload["success"] is False
    assert "error" in payload
    assert "error_id" in payload

    del app.router.routes[route_count:]


def test_ai_cache_failures_do_not_break_response(monkeypatch):
    engine = get_rag_engine()

    class BrokenCache:
        def get(self, key):
            raise RuntimeError("cache read failed")

        def setex(self, key, ttl, value):
            raise RuntimeError("cache write failed")

    monkeypatch.setattr(engine, "_cache_client", lambda: BrokenCache())
    monkeypatch.setattr(
        engine,
        "retrieve",
        lambda query, top_k=3: [
            RetrievalResult(
                source_file="charaka_samhita.pdf",
                text="Guduchi supports digestive balance in classical references.",
                score=0.91,
                chunk_id="chunk-1",
            )
        ],
    )
    monkeypatch.setattr(engine, "ensure_ollama_available", lambda: (False, "Ollama unavailable"))

    payload = engine.generate_clinical_response("Burning after meals")

    assert payload["answer"]
    assert payload["sources"] == ["charaka_samhita.pdf"]
    assert payload["context_passages"][0]["chunk_id"] == "chunk-1"


def test_backup_script_creates_timestamped_copy(monkeypatch):
    temp_root = Path("tests") / "backup_script_tmp"
    try:
        shutil.rmtree(temp_root, ignore_errors=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        source_db = temp_root / "ayurveda_clinic.db"
        source_db.write_text("sqlite-data", encoding="utf-8")

        monkeypatch.setattr(backup_db_module, "_sqlite_db_path", lambda _: source_db)
        monkeypatch.setattr(
            backup_db_module,
            "settings",
            type(
                "BackupSettings",
                (),
                {
                    "base_dir": temp_root,
                    "database_url": f"sqlite:///{source_db.as_posix()}",
                    "backups_dir": temp_root / "backups",
                },
            )(),
        )

        backup_path = backup_db_module.backup_sqlite_db()

        assert backup_path.exists()
        assert backup_path.suffix == ".zip"
        assert backup_path.parent == temp_root / "backups"
        with zipfile.ZipFile(backup_path) as archive:
            payload = archive.read("ayurveda_clinic.db").decode("utf-8")
        assert payload == "sqlite-data"
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


@pytest.mark.asyncio
async def test_required_routes_return_valid_responses(authenticated_client, monkeypatch):
    client = authenticated_client["client"]
    engine = get_rag_engine()

    home_response = await client.get("/")
    assert home_response.status_code in {200, 303}

    login_response = await client.get("/login")
    assert login_response.status_code in {200, 303}

    dashboard_response = await client.get("/dashboard")
    assert dashboard_response.status_code == 200

    demo_response = await client.get("/demo")
    assert demo_response.status_code == 200

    from tests.conftest import extract_csrf_token

    demo_token = extract_csrf_token(demo_response.text)
    create_demo_response = await client.post(
        "/demo/create-workspace",
        data={"csrf_token": demo_token},
        follow_redirects=False,
    )
    assert create_demo_response.status_code == 303
    patient_cases_path = create_demo_response.headers["location"]

    cases_response = await client.get(patient_cases_path)
    assert cases_response.status_code == 200

    appointments_response = await client.get("/appointments")
    assert appointments_response.status_code == 200

    seed_response = await client.get("/demo/setup", follow_redirects=False)
    assert seed_response.status_code == 303
    assert seed_response.headers["location"] == "/dashboard"

    seeded_dashboard = await client.get("/dashboard")
    assert seeded_dashboard.status_code == 200
    assert "Demo Mode" in seeded_dashboard.text

    payments_page = await client.get("/payments/daily")
    assert payments_page.status_code == 200
    payments_token = extract_csrf_token(payments_page.text)

    patient_id = patient_cases_path.strip("/").split("/")[1]

    prescription_page = await client.get(f"/patients/{patient_id}/prescriptions/new")
    assert prescription_page.status_code == 200
    assert "Use Template" in prescription_page.text
    assert "Reuse last prescription" in prescription_page.text or "No previous prescription" in prescription_page.text
    prescription_token = extract_csrf_token(prescription_page.text)
    prescription_response = await client.post(
        "/prescriptions/create",
        data={
            "patient_id": patient_id,
            "diagnosis": "Demo diagnosis",
            "advice": "Demo advice",
            "follow_up_days": "7",
            "medicine_name": ["Triphala"],
            "medicine_dosage": ["1 tsp"],
            "medicine_frequency": ["Nightly"],
            "csrf_token": prescription_token,
        },
        follow_redirects=False,
    )
    assert prescription_response.status_code == 303
    prescription_path = prescription_response.headers["location"]
    assert "?created=1" in prescription_path

    prescription_detail = await client.get(prescription_path)
    assert prescription_detail.status_code == 200
    assert "Next visit recommended in 7 days" in prescription_detail.text
    share_token = extract_csrf_token(prescription_detail.text)
    share_response = await client.post(
        prescription_path.split("?")[0] + "/share",
        data={"csrf_token": share_token},
        follow_redirects=False,
    )
    assert share_response.status_code == 303

    outcome_page = await client.get(f"/patients/{patient_id}/outcomes")
    assert outcome_page.status_code == 200
    outcome_token = extract_csrf_token(outcome_page.text)
    outcome_response = await client.post(
        "/outcomes/add",
        data={
            "patient_id": patient_id,
            "improvement_status": "Better",
            "symptom_score": "5",
            "notes": "Patient feels lighter.",
            "csrf_token": outcome_token,
        },
        follow_redirects=False,
    )
    assert outcome_response.status_code == 303
    assert outcome_response.headers["location"] == f"/patients/{patient_id}/outcomes"

    payment_response = await client.post(
        "/payments/add",
        data={
            "patient_id": patient_id,
            "amount": "500.00",
            "payment_status": "paid",
            "csrf_token": payments_token,
        },
        follow_redirects=False,
    )
    assert payment_response.status_code == 303
    assert payment_response.headers["location"] == "/payments/daily"

    reset_token = extract_csrf_token(seeded_dashboard.text)
    reset_demo_response = await client.post(
        "/demo/reset",
        data={"csrf_token": reset_token},
        follow_redirects=False,
    )
    assert reset_demo_response.status_code == 303
    assert reset_demo_response.headers["location"] == "/dashboard"

    followups_response = await client.get("/followups")
    assert followups_response.status_code == 200

    analyzer_page = await client.get("/ai-analyzer")
    assert analyzer_page.status_code == 200
    analyzer_token = extract_csrf_token(analyzer_page.text)

    monkeypatch.setattr(
        engine,
        "generate_clinical_response",
        lambda symptoms, patient_context="": {
            "answer": "Possible Diagnosis:\nTest\nDosha Imbalance:\nTest\nRelevant Herbs:\nTest\nDiet Recommendations:\nTest\nLifestyle Advice:\nTest\nAyurvedic Explanation:\nTest",
            "sources": ["charaka_samhita.pdf"],
            "context_passages": [{"source_file": "charaka_samhita.pdf", "chunk_id": "chunk-1", "score": 0.9}],
        },
    )
    analyze_response = await client.post(
        "/api/ai/analyze",
        json={"symptoms": "Burning after meals"},
        headers={"X-CSRF-Token": analyzer_token},
    )
    assert analyze_response.status_code == 200

    rebuild_status_response = await client.get("/api/ai/rebuild-status")
    assert rebuild_status_response.status_code == 200

    health_response = await client.get("/healthz")
    assert health_response.status_code == 200


@pytest.mark.asyncio
async def test_ai_analyzer_returns_graceful_response_when_engine_crashes(authenticated_client, monkeypatch):
    client = authenticated_client["client"]
    engine = get_rag_engine()

    analyzer_page = await client.get("/ai-analyzer")
    assert analyzer_page.status_code == 200

    from tests.conftest import extract_csrf_token

    analyzer_token = extract_csrf_token(analyzer_page.text)
    monkeypatch.setattr(
        engine,
        "generate_clinical_response",
        lambda symptoms, patient_context="": (_ for _ in ()).throw(RuntimeError("engine crash")),
    )

    response = await client.post(
        "/api/ai/analyze",
        json={"symptoms": "Burning after meals"},
        headers={"X-CSRF-Token": analyzer_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "temporarily unavailable" in payload["answer"]
    assert payload["sources"] == []
    assert payload["context_passages"] == []


@pytest.mark.asyncio
async def test_rebuild_endpoint_rejects_duplicate_queue_requests(authenticated_client):
    client = authenticated_client["client"]

    analyzer_page = await client.get("/ai-analyzer")
    assert analyzer_page.status_code == 200

    from tests.conftest import extract_csrf_token

    analyzer_token = extract_csrf_token(analyzer_page.text)
    rebuild_status.update({"running": True, "progress_message": "building_vector_store"})

    response = await client.post(
        "/api/ai/rebuild-knowledge",
        data={"csrf_token": analyzer_token},
    )

    assert response.status_code == 409
    assert response.json()["message"] == "Knowledge rebuild is already in progress."
