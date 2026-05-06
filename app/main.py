from __future__ import annotations
import logging
import re
import uuid
from contextlib import asynccontextmanager
from threading import Thread
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.analytics import track_event
from app.config import settings
from app.database import SessionLocal, init_db
from app.exception_handlers import register_exception_handlers
try:
    from app.health import build_health_report, production_launch_metrics
    from services.cache_service import redis_ping
except Exception as exc:
    _health_import_error = str(exc)

    def build_health_report() -> dict[str, str]:
        return {"status": "degraded", "error": f"Health report unavailable: {_health_import_error}"}

    def production_launch_metrics() -> dict[str, object]:
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "sentry": False,
            "cloud_run_detected": False,
            "cloud_run_service": "",
            "medicines_count": 0,
            "suppliers_count": 0,
            "patients_active": 0,
            "timestamp": "",
        }

    async def redis_ping() -> bool:
        return False
from app.logging_config import clear_request_id, configure_logging, set_request_id
from app.monitoring import PerformanceMonitoringMiddleware
from app.rate_limit import limiter
from app.models import Doctor
from models.care_plan import PatientCarePlan  # noqa: F401
from models.subscription import ClinicSubscription  # noqa: F401
try:
    from app.pdf_loader import ensure_runtime_dirs
except Exception:
    def ensure_runtime_dirs() -> None:
        settings.samhita_pdfs_dir.mkdir(parents=True, exist_ok=True)
        settings.vector_store_dir.mkdir(parents=True, exist_ok=True)
        settings.logs_dir.mkdir(parents=True, exist_ok=True)
        (settings.static_dir / "images").mkdir(parents=True, exist_ok=True)
from app.runtime import request_load_controller
try:
    from app.rag_engine import get_rag_engine
except Exception as exc:
    _rag_import_error = str(exc)

    def get_rag_engine():
        raise RuntimeError(f"RAG engine unavailable: {_rag_import_error}")
from app.security import ensure_https_request
from apps.api.routes import router as api_v1_router
from apps.delivery.routes import router as delivery_portal_router
from apps.doctor.routes import router as doctor_portal_router
from apps.lab.routes import router as lab_portal_router
from apps.patient.routes import router as patient_portal_router
from apps.pharmacy.routes import router as pharmacy_portal_router
from routers.admin import router as admin_router
from routers.ai import router as ai_router
from routers.ai_features import router as ai_features_router
from routers.appointments import router as appointments_router
from routers.auth import router as auth_router
from routers.cases import router as cases_router
from routers.contact import router as contact_router
from routers.emr import router as emr_router
from routers.ecommerce import router as ecommerce_router
from routers.health import router as health_router
from routers.lab_owner import router as lab_owner_router
from routers.marketplace import router as marketplace_router
from routers.medicine_info import router as medicine_info_router
from routers.patients import router as patients_router
from routers.order_medicines import router as order_medicines_router
from routers.pharmacy_owner import router as pharmacy_owner_router
from routers.pharmacy import router as pharmacy_router
from routers.profiles import router as profiles_router
from routers.public_clinic import router as public_clinic_router
from routers.startup import router as startup_router
from routers.subscriptions import router as subscriptions_router
from routers.telemedicine import router as telemedicine_router
from routers.delivery import router as delivery_router
from routers.debug import router as debug_router
from routes.demo import router as demo_router
from routes.outcome import router as outcome_router
from routes.payment import router as payment_router
from routes.prescription import router as prescription_router
from utils.subscription_utils import (
    build_paywall_response,
    check_subscription_access,
    increment_subscription_usage as increment_usage,
)


configure_logging()
logger = logging.getLogger(__name__)


def _masked_setting(name: str, value: str) -> str:
    if not value:
        return f"{name}=missing"
    return f"{name}={value[:6]}..."


def _log_production_startup_warnings() -> None:
    if not settings.is_production:
        return
    # PROD-FIX-5: Production secrets rotation notice without printing full secret values.
    detected = [
        _masked_setting("RAZORPAY_KEY_ID", settings.razorpay_key_id),
        _masked_setting("DATABASE_URL", settings.database_url),
    ]
    logger.warning(
        "PRODUCTION: Rotate all API keys immediately if .env was ever committed/shared. Current keys detected: %s",
        ", ".join(detected),
    )


def _subscription_feature_for_request(request: Request) -> str | None:
    path = request.url.path
    if request.method != "POST":
        return None
    if path in {"/api/ai/analyze"}:
        return None
    if path.endswith("/cases/transcribe-audio") or path.endswith("/cases/transcribe-live"):
        return "voice"
    if re.fullmatch(r"/cases/\d+/generate-ai", path) or re.fullmatch(r"/cases/\d+/generate-diet", path):
        return "ai_call"
    return None


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
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=(self)"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com https://fonts.gstatic.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
            "script-src 'self' 'unsafe-inline' https://checkout.razorpay.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://checkout.razorpay.com; "
            "font-src 'self' data: https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
            "connect-src 'self' https://checkout.razorpay.com https://lumberjack.razorpay.com; "
            "frame-src https://api.razorpay.com https://checkout.razorpay.com; "
            "frame-ancestors 'none';"
        )
        clear_request_id()
        return response


class OverloadProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/health", "/healthz"}:
            return await call_next(request)
        acquired = await request_load_controller.acquire()
        if not acquired:
            logger.warning("Overload protection rejected request path=%s", request.url.path)
            return JSONResponse(
                status_code=503,
                content={"success": False, "error": "Too many people are using the app right now. Please try again shortly."},
                headers={"Retry-After": "2"},
            )
        try:
            response = await call_next(request)
        finally:
            await request_load_controller.release()
        snapshot = request_load_controller.snapshot()
        response.headers["X-In-Flight-Requests"] = str(snapshot.in_flight)
        response.headers["X-Request-Capacity"] = str(snapshot.limit)
        return response


def _run_startup_warmups() -> None:
    try:
        rag_engine = get_rag_engine()
    except Exception as exc:
        logger.exception("Startup warmups skipped because RAG engine is unavailable: %s", exc)
        return

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
    _log_production_startup_warnings()
    init_db()
    track_event("application_started", environment=settings.environment)
    Thread(target=_run_startup_warmups, name="startup-warmups", daemon=True).start()
    yield


def create_app() -> FastAPI:
    if settings.sentry_dsn:
        try:
            import sentry_sdk  # type: ignore

            # PROD-LAUNCH-1: Capture full traces for first production launch, no-op if SDK is unavailable.
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                traces_sample_rate=1.0 if settings.is_production else 0.1,
                environment=settings.environment,
            )
            logger.info("Sentry error tracking configured.")
        except Exception as exc:
            logger.warning("Sentry configuration skipped: %s", exc)

    application = FastAPI(
        title="Kash AI",
        version=settings.app_version,
        description=(
            "Kash AI is a production-ready healthcare superapp covering consultations, EMR, "
            "pharmacy commerce, telemedicine, diagnostics, growth systems, and admin operations."
        ),
        lifespan=lifespan,
    )
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    register_exception_handlers(application)
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
    if settings.is_production:
        allowed_hosts = list(dict.fromkeys((settings.trusted_hosts or []) + ["127.0.0.1", "localhost", "testserver"]))
    else:
        allowed_hosts = ["*"]
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    application.add_middleware(GZipMiddleware, minimum_size=512)
    application.add_middleware(SlowAPIMiddleware)
    application.add_middleware(PerformanceMonitoringMiddleware)
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(OverloadProtectionMiddleware)

    @application.middleware("http")
    async def https_redirect_middleware(request: Request, call_next):
        if settings.https_redirect_enabled and settings.is_production:
            forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
            if forwarded_proto != "https":
                secure_url = str(request.url.replace(scheme="https"))
                return RedirectResponse(url=secure_url, status_code=307)
        return await call_next(request)

    @application.middleware("http")
    async def attach_session_user(request: Request, call_next):
        request.state.user = None
        try:
            doctor_id = request.session.get("doctor_id")
        except AssertionError:
            doctor_id = None
        if doctor_id:
            db = SessionLocal()
            try:
                request.state.user = db.get(Doctor, doctor_id)
            finally:
                db.close()
        return await call_next(request)

    @application.middleware("http")
    async def subscription_enforcement_middleware(request: Request, call_next):
        feature = _subscription_feature_for_request(request)
        try:
            doctor_id = request.session.get("doctor_id")
        except AssertionError:
            return await call_next(request)
        if not feature or not doctor_id:
            return await call_next(request)

        db = SessionLocal()
        try:
            doctor = db.get(Doctor, doctor_id)
            if doctor is None:
                return await call_next(request)
            access = check_subscription_access(doctor, feature)
            logger.info("Subscription check: user=%s, feature=%s, allowed=%s", doctor.id, feature, access["allowed"])
            if not access["allowed"]:
                return JSONResponse(build_paywall_response(doctor, feature), status_code=403)
            response = await call_next(request)
            if 200 <= response.status_code < 400:
                increment_usage(doctor, feature)
            return response
        finally:
            db.close()

    application.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
    application.mount("/shared-static", StaticFiles(directory=settings.shared_static_dir), name="shared-static")
    public_dir = settings.base_dir / "public"
    if public_dir.exists():
        application.mount("/public", StaticFiles(directory=public_dir), name="public")
    application.include_router(public_clinic_router)
    application.include_router(startup_router)
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(patients_router)
    application.include_router(cases_router)
    application.include_router(contact_router)
    application.include_router(appointments_router)
    application.include_router(ai_router)
    application.include_router(ai_features_router)
    application.include_router(api_v1_router)
    application.include_router(marketplace_router)
    application.include_router(patient_portal_router)
    application.include_router(doctor_portal_router)
    application.include_router(pharmacy_portal_router)
    application.include_router(lab_portal_router)
    application.include_router(delivery_portal_router)
    application.include_router(medicine_info_router)
    application.include_router(delivery_router)
    application.include_router(debug_router)
    application.include_router(pharmacy_owner_router)
    application.include_router(lab_owner_router)
    application.include_router(pharmacy_router)
    application.include_router(profiles_router)
    application.include_router(ecommerce_router)
    application.include_router(order_medicines_router)
    application.include_router(subscriptions_router)
    application.include_router(admin_router)
    application.include_router(emr_router)
    application.include_router(telemedicine_router)
    application.include_router(prescription_router)
    application.include_router(payment_router)
    application.include_router(outcome_router)
    application.include_router(demo_router)

    return application


app = create_app()
