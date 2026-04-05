from pathlib import Path
import os
import uuid

import pytest

import app.rag_engine as rag_engine_module
from app.rag_engine import get_rag_engine
from tests.conftest import extract_csrf_token


@pytest.mark.asyncio
async def test_rebuild_endpoint_exposes_expected_status_fields(authenticated_client):
    client = authenticated_client["client"]
    engine = get_rag_engine()

    original_prepare = engine.prepare

    def fake_prepare(force_rebuild: bool = False):
        return {"rebuilt": True, "chunks": 2, "sources": ["demo.pdf"], "message": "ok"}

    engine.prepare = fake_prepare

    try:
        analyzer_page = await client.get("/ai-analyzer")
        assert analyzer_page.status_code == 200
        csrf_token = extract_csrf_token(analyzer_page.text)

        response = await client.post(
            "/api/ai/rebuild-knowledge",
            data={"csrf_token": csrf_token},
        )
        assert response.status_code == 200
        assert "message" in response.json()

        status_response = await client.get("/api/ai/rebuild-status")
        assert status_response.status_code == 200
        payload = status_response.json()
        assert set(payload) >= {"running", "last_started", "last_finished", "last_error", "progress_message"}
    finally:
        engine.prepare = original_prepare


def test_faiss_rebuild_lock_skips_prepare_when_lock_file_exists(monkeypatch):
    engine = get_rag_engine()
    temp_dir = Path("tests") / ".tmp"
    temp_dir.mkdir(exist_ok=True)
    lock_path = temp_dir / f".faiss_rebuild_{uuid.uuid4().hex}.lock"
    lock_path.write_text("locked", encoding="utf-8")

    monkeypatch.setattr(engine, "_faiss_rebuild_lock_path", lambda: lock_path)

    def fake_build_vector_store(force: bool = False):
        raise AssertionError("build_vector_store should not run while a rebuild lock already exists")

    monkeypatch.setattr(rag_engine_module, "build_vector_store", fake_build_vector_store)

    try:
        result = engine.prepare(True)
    finally:
        if lock_path.exists():
            lock_path.unlink()

    assert result["rebuilt"] is False
    assert result["chunks"] == 0
    assert result["message"] == "Rebuild already in progress."


def test_faiss_rebuild_removes_stale_lock_before_prepare(monkeypatch):
    engine = get_rag_engine()
    temp_dir = Path("tests") / ".tmp"
    temp_dir.mkdir(exist_ok=True)
    lock_path = temp_dir / f".faiss_rebuild_{uuid.uuid4().hex}.lock"
    lock_path.write_text("stale", encoding="utf-8")
    stale_timestamp = lock_path.stat().st_mtime - 601
    os.utime(lock_path, (stale_timestamp, stale_timestamp))

    monkeypatch.setattr(engine, "_faiss_rebuild_lock_path", lambda: lock_path)
    monkeypatch.setattr(
        rag_engine_module,
        "build_vector_store",
        lambda force=False: {"rebuilt": True, "chunks": 3, "sources": ["demo.pdf"]},
    )

    result = engine.prepare(True)

    assert result["rebuilt"] is True
    assert result["chunks"] == 3
    assert not lock_path.exists()
