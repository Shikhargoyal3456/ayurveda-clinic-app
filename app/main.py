from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from threading import Thread
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.analytics import track_event
from app.config import settings
from app.database import init_db
from app.health import build_health_report
from app.logging_config import clear_request_id, configure_logging, set_request_id
from app.pdf_loader import ensure_runtime_dirs
from app.rag_engine import get_rag_engine
from app.security import ensure_https_request
from routers.admin import router as admin_router
from routers.ai import router as ai_router
from routers.appointments import router as appointments_router
from routers.auth import router as auth_router
from routers.cases import router as cases_router
from routers.patients import router as patients_router
from routes.demo import router as demo_router
from routes.outcome import router as outcome_router
from routes.payment import router as payment_router
from routes.prescription import router as prescription_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)


configure_logging()
logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        set_request_id(request_id)
        request.state.request_id = request_id
        request.state.request_started_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        start = perf_counter()
        try:
            ensure_https_request(request)
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled error during request %s %s", request.method, request.url.path)
            raise
        finally:
            duration_ms = round((perf_counter() - start) * 1000, 2)
            logger.info(
                "request_completed method=%s path=%s status_code=%s duration_ms=%s",
                request.method,
                request.url.path,
                getattr(locals().get("response"), "status_code", 500),
                duration_ms,
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "script-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        clear_request_id()
        return response


def _run_startup_warmups() -> None:
    rag_engine = get_rag_engine()

    if settings.startup_rag_warmup:
        try:
            warmup_report = rag_engine.warm_up()
            logger.info("RAG startup warmup complete: %s", warmup_report)
        except Exception as exc:  # pragma: no cover
            logger.exception("RAG startup warmup failed: %s", exc)
    else:
        logger.info("RAG startup warmup disabled by configuration.")

    if settings.startup_llm_warmup and settings.ai_enabled:
        try:
            llm_warmup = rag_engine.warm_up_llm()
            logger.info("LLM startup warmup complete: %s", llm_warmup)
        except Exception as exc:  # pragma: no cover
            logger.exception("LLM startup warmup failed: %s", exc)
    else:
        logger.info("LLM startup warmup disabled by configuration.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_runtime_dirs()
    init_db()
    track_event("application_started", environment=settings.environment)
    Thread(target=_run_startup_warmups, name="startup-warmups", daemon=True).start()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="Ayurvedic Clinic Management System",
        version="1.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        max_age=settings.session_idle_timeout_minutes * 60,
        same_site=settings.session_same_site,
        https_only=settings.session_https_only,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts or ["*"])
    application.add_middleware(GZipMiddleware, minimum_size=512)
    application.add_middleware(RequestContextMiddleware)

    @application.middleware("http")
    async def https_redirect_middleware(request: Request, call_next):
        if settings.https_redirect_enabled and settings.is_production:
            forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
            if forwarded_proto != "https":
                secure_url = str(request.url.replace(scheme="https"))
                return RedirectResponse(url=secure_url, status_code=307)
        return await call_next(request)

    application.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
    application.include_router(auth_router)
    application.include_router(patients_router)
    application.include_router(cases_router)
    application.include_router(appointments_router)
    application.include_router(ai_router)
    application.include_router(admin_router)
    application.include_router(prescription_router)
    application.include_router(payment_router)
    application.include_router(outcome_router)
    application.include_router(demo_router)

    @application.get("/healthz")
    def healthcheck():
        return JSONResponse(build_health_report())

    @application.get("/health")
    def simple_healthcheck():
        return {"status": "ok"}

    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error during request %s %s", request.method, request.url.path, exc_info=exc)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})

    return application


app = create_app()
