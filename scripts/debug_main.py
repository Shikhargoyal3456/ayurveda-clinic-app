import traceback

from fastapi import FastAPI


_import_error = None

try:
    from app.main import app as app

    print("Successfully imported app.main")
except Exception as exc:  # pragma: no cover - debug bootstrap for Render
    _import_error = f"{type(exc).__name__}: {exc}"
    print("Failed to import app.main")
    traceback.print_exc()

    app = FastAPI()

    @app.get("/")
    async def root():
        return {"error": "Main app failed to load", "details": _import_error}

    @app.get("/health")
    async def health():
        return {"status": "degraded", "error": _import_error}
