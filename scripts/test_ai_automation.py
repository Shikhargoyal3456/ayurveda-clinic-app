from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(PROJECT_ROOT / 'tests' / '.ai_automation_script.db').as_posix()}")
os.environ.setdefault("ALLOW_PUBLIC_SIGNUP", "true")
os.environ.setdefault("AI_CACHE_ENABLED", "false")
os.environ.setdefault("AI_ENABLED", "true")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("SESSION_HTTPS_ONLY", "false")
os.environ.setdefault("HTTPS_REDIRECT_ENABLED", "false")
os.environ.setdefault("UVICORN_RELOAD", "false")
os.environ.setdefault("ADMIN_USERNAMES", "")
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("TRUSTED_HOSTS", "127.0.0.1,localhost,testserver")

from app.main import app  # noqa: E402
from app.database import init_db  # noqa: E402


def main() -> int:
    init_db()
    client = TestClient(app)

    create = client.post(
        "/api/telemedicine/create-session",
        json={"patient_id": 1, "doctor_id": 1, "session_type": "video"},
    )
    assert create.status_code == 200, create.text
    session = create.json()

    symptom = client.post(
        "/api/telemedicine/analyze-symptoms",
        json={"symptoms": "I have fever and headache"},
    )
    assert symptom.status_code == 200, symptom.text

    ai_support = client.post(
        "/api/ai/support/respond",
        json={"query": "where is my order", "user_context": {"last_order_id": 42}},
    )
    assert ai_support.status_code == 200, ai_support.text

    summary = client.post("/api/telemedicine/summary", json={"session_id": session["session_id"]})
    assert summary.status_code == 200, summary.text

    print("AI automation and telemedicine smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
