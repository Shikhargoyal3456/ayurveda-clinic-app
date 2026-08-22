from __future__ import annotations

import sys

from sqlalchemy import text

from app.config import settings
from app.database import engine
from services.ai_provider import GROQ_API_KEY


REQUIRED_MODULES = {
    "fastapi": lambda: __import__("fastapi"),
    "uvicorn": lambda: __import__("uvicorn"),
    "sqlalchemy": lambda: __import__("sqlalchemy"),
    "jinja2": lambda: __import__("jinja2"),
    "passlib": lambda: __import__("passlib"),
    "requests": lambda: __import__("requests"),
    "numpy": lambda: __import__("numpy"),
    "google.genai": lambda: __import__("google.genai"),
    "groq": lambda: __import__("groq"),
}


def main() -> int:
    print("Kash ai environment verification")
    print(f"Python version: {sys.version}")
    if sys.version_info < (3, 13):
        print("[ERROR] Python 3.13+ is recommended.")
        return 1

    missing = []
    for module_name, import_module in REQUIRED_MODULES.items():
        try:
            import_module()
            print(f"[OK] {module_name}")
        except Exception as exc:
            print(f"[ERROR] {module_name}: {exc}")
            missing.append(module_name)

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("[OK] Database connectivity")
    except Exception as exc:
        print(f"[ERROR] Database connectivity: {exc}")
        return 1

    if settings.vertex_ai_project:
        print(f"[OK] Vertex AI configured for project: {settings.vertex_ai_project}")
    else:
        print("[WARN] Vertex AI is not configured")

    if GROQ_API_KEY:
        print("[OK] Groq API key configured")
    else:
        print("[WARN] Groq API key is not configured")

    if missing:
        print(f"[ERROR] Missing modules: {', '.join(missing)}")
        return 1

    print("[OK] Environment verification complete")
    print(f"Runtime Python: {settings.runtime_python}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
