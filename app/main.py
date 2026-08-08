from __future__ import annotations
import atexit
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from threading import Thread
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.analytics import track_event
from app.auth import _apply_rate_limit, ensure_csrf_token
from app.cache.cache_manager import build_etag, get_cached_page, set_cached_page
from app.config import settings
from app.database import SessionLocal, init_db
from app.error_handlers import register_exception_handlers
from app.schemas import AIChatRequest
from app.utils.groq_client import groq_client
from app.utils.file_validator import validate_prompt_injection
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
from app.middleware.csrf import CSRFMiddleware
from app.middleware.rate_limiter import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.monitoring import PerformanceMonitoringMiddleware
from app.rate_limit import limiter
from middleware.role_middleware import RoleGuardMiddleware
from app.template_compat import patch_jinja2_templates
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
from routers.ai_doctor import router as ai_doctor_router
from routers.ai_dashboard import router as ai_dashboard_router
from routers.ai_pharmacy import router as ai_pharmacy_router
from routers.ai_features import router as ai_features_router
from routers.ayurveda_terms import router as ayurveda_terms_router
from routers.ambient_emr import router as ambient_emr_router
from routers.appointments import router as appointments_router
from routers.auth import router as auth_router
from routers.cases import router as cases_router
from routers.contact import router as contact_router
from routers.emr import router as emr_router
from routers.ecommerce import router as ecommerce_router
from routers.health import router as health_router
from routers.lab_owner import router as lab_owner_router
from routers.lab_analyzer import router as lab_analyzer_router
from routers.marketplace import router as marketplace_router
from routers.medicine_info import router as medicine_info_router
from routers.new_frontend import router as new_frontend_router
from routers.patients import router as patients_router
from routers.patient_tools import router as patient_tools_router
from routers.order_medicines import router as order_medicines_router
from routers.pharmacy_owner import router as pharmacy_owner_router
from routers.pharmacy import router as pharmacy_router
from routers.prescription_ocr import router as prescription_ocr_router
from routers.profiles import router as profiles_router
from routers.pure_ai import router as pure_ai_router
from routers.public_clinic import router as public_clinic_router
from routers.patient_agent import router as patient_agent_router
from routers.sales import router as sales_router
from routers.statistics import router as statistics_router
from routers.startup import router as startup_router
from routers.backup import backup_scheduler, router as backup_router
from routers.audit import router as audit_router
from routers.export import router as export_router
from routers.patient_linking import router as patient_linking_router
from routers.subscriptions import router as subscriptions_router
from routers.telemedicine import router as telemedicine_router
from routers.voice_consultation import router as voice_consultation_router
from routers.voice_transcribe import router as voice_router
from routers.delivery import router as delivery_router
from routers.debug import router as debug_router
from routers.dashboard import router as dashboard_router
from routers.doctor_review import router as doctor_review_router
from routers.google_auth import router as google_auth_router
from routers.consultation import router as consultation_router
from routers.device_check import router as device_check_router
from routes.demo import router as demo_router
from routes.outcome import router as outcome_router
from routes.payment import router as payment_router
from routes.prescription import router as prescription_router
from utils.subscription_utils import (
    build_paywall_response,
    check_subscription_access,
    increment_subscription_usage as increment_usage,
)
from services.ai_provider import close_genai_client

load_dotenv()

configure_logging()
logger = logging.getLogger(__name__)
patch_jinja2_templates()
atexit.register(close_genai_client)
templates = Jinja2Templates(directory=str(settings.templates_dir))


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
        return None
    if re.fullmatch(r"/cases/\d+/generate-ai", path) or re.fullmatch(r"/cases/\d+/generate-diet", path):
        return "ai_call"
    return None


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        set_request_id(request_id)
        request.state.request_id = request_id
        try:
            request.state.csrf_token = ensure_csrf_token(request)
        except Exception:
            request.state.csrf_token = ""
        request.state.request_started_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        start = perf_counter()
        forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        is_secure_request = forwarded_proto == "https"
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
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(self), geolocation=(self)"
        response.headers["Cache-Control"] = "no-store"
        if is_secure_request:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com https://fonts.gstatic.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
            "script-src 'self' 'unsafe-inline' https://checkout.razorpay.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https://checkout.razorpay.com; "
            "font-src 'self' data: https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
            "media-src 'self' https://d8j0ntlcm91z4.cloudfront.net; "
            "connect-src 'self' ws: wss: https://checkout.razorpay.com https://lumberjack.razorpay.com; "
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


class APIRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not settings.rate_limit_enabled or not path.startswith("/api/"):
            return await call_next(request)

        forwarded_for = request.headers.get("x-forwarded-for", "")
        client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else (request.client.host if request.client else "unknown")
        ip_retry_after = _apply_rate_limit(
            f"api-ip:{client_ip}:{request.method}",
            limit=max(1, settings.api_ip_rate_limit_requests),
            window_seconds=max(1, settings.api_ip_rate_limit_period),
        )
        if ip_retry_after is not None:
            return JSONResponse(
                status_code=429,
                content={"success": False, "error": "Too many requests. Please slow down.", "retry_after": ip_retry_after},
                headers={"Retry-After": str(ip_retry_after)},
            )

        session = request.scope.get("session")
        actor_id = None
        if isinstance(session, dict):
            actor_id = session.get("doctor_id") or session.get("portal_user_id")
        if actor_id:
            actor_retry_after = _apply_rate_limit(
                f"api-user:{actor_id}:{request.method}",
                limit=max(1, settings.api_user_rate_limit_requests),
                window_seconds=max(1, settings.api_user_rate_limit_period),
            )
            if actor_retry_after is not None:
                return JSONResponse(
                    status_code=429,
                    content={"success": False, "error": "Too many requests for this account. Please wait and try again.", "retry_after": actor_retry_after},
                    headers={"Retry-After": str(actor_retry_after)},
                )

        return await call_next(request)


class AttachSessionUserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.user = None
        session = request.scope.get("session")
        doctor_id = session.get("doctor_id") if isinstance(session, dict) else None
        if doctor_id:
            db = SessionLocal()
            try:
                request.state.user = db.get(Doctor, doctor_id)
            finally:
                db.close()
        return await call_next(request)


class SubscriptionEnforcementMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        feature = _subscription_feature_for_request(request)
        if not feature:
            return await call_next(request)

        try:
            session = request.scope.get("session")
            doctor_id = request.session.get("doctor_id") if isinstance(session, dict) else None
        except AssertionError:
            doctor_id = None

        if not doctor_id:
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


def _run_startup_warmups() -> None:
    if not settings.startup_rag_warmup and not (settings.startup_llm_warmup and settings.ai_enabled):
        logger.info("Startup warmups disabled by configuration.")
        return
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
    if settings.enable_auto_backup:
        backup_scheduler.start_background()
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
    application.add_middleware(PerformanceMonitoringMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RateLimitMiddleware, requests_per_minute=60)
    application.add_middleware(APIRateLimitMiddleware)
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(OverloadProtectionMiddleware)
    application.add_middleware(AttachSessionUserMiddleware)
    application.add_middleware(SubscriptionEnforcementMiddleware)
    application.add_middleware(RoleGuardMiddleware)
    application.add_middleware(CSRFMiddleware)

    @application.middleware("http")
    async def session_timeout_middleware(request: Request, call_next):
        try:
            session = request.scope.get("session")
            if isinstance(session, dict):
                last_activity = session.get("last_activity")
                now = datetime.now().timestamp()
                timeout_seconds = max(60, int(settings.session_idle_timeout_minutes or 15) * 60)
                if last_activity and (now - float(last_activity)) > timeout_seconds:
                    session.clear()
                    return RedirectResponse(url="/new/login?message=Session%20expired", status_code=303)
                session["last_activity"] = now
        except Exception:
            pass
        return await call_next(request)

    # Starlette executes the last-added middleware first, so SessionMiddleware must
    # be added after session-dependent middleware declarations in source order.
    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        max_age=settings.session_idle_timeout_minutes * 60,
        same_site=settings.session_same_site,
        https_only=settings.session_https_only,
    )

    @application.middleware("http")
    async def https_redirect_middleware(request: Request, call_next):
        if settings.https_redirect_enabled and settings.is_production:
            forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
            host = request.headers.get("host", "")
            if forwarded_proto != "https" and "." in host and not host.replace(".", "").isdigit():
                secure_url = str(request.url.replace(scheme="https"))
                return RedirectResponse(url=secure_url, status_code=307)
        return await call_next(request)

    @application.get("/favicon.ico", include_in_schema=False)
    async def favicon_redirect():
        return RedirectResponse(url="/static/images/favicon.svg", status_code=307)

    @application.get("/", include_in_schema=False)
    async def root():
        """Redirect to the full starting page."""
        return RedirectResponse(url="/new", status_code=302)

    @application.get("/api")
    async def api_root():
        return {
            "message": "Kash AI API is running!",
            "version": settings.app_version or "1.0.0",
            "status": "healthy",
            "docs": "/docs",
        }

    @application.get("/index", include_in_schema=False)
    async def index_page():
        return RedirectResponse(url="/new", status_code=302)

    @application.get("/landing", include_in_schema=False)
    async def landing_page(request: Request):
        return templates.TemplateResponse(
            "landing.html",
            {
                "request": request,
                "app_url": "/new",
            },
        )

    @application.get("/doctor/dashboard", include_in_schema=False)
    async def old_doctor_dashboard():
        return RedirectResponse(url="/new/doctor", status_code=301)

    @application.get("/patient", include_in_schema=False)
    async def old_patient_dashboard():
        return RedirectResponse(url="/new/patient", status_code=301)

    @application.get("/patient/dashboard", include_in_schema=False)
    async def patient_dashboard_redirect():
        return RedirectResponse(url="/new/patient", status_code=301)

    @application.get("/admin", include_in_schema=False)
    async def old_admin_dashboard():
        return RedirectResponse(url="/new/admin", status_code=301)

    @application.get("/feature-status", include_in_schema=False)
    async def feature_status_page(request: Request):
        cached = get_cached_page("feature-status")
        if cached is not None:
            if request.headers.get("if-none-match") == cached.etag:
                return HTMLResponse(status_code=304, content="")
            response = HTMLResponse(content=str(cached.content))
            response.headers["ETag"] = cached.etag
            response.headers["Cache-Control"] = "public, max-age=300"
            return response
        response = templates.TemplateResponse("feature_status.html", {"request": request, "csrf_token": getattr(request.state, "csrf_token", "")})
        body = getattr(response, "body", b"").decode("utf-8", errors="ignore")
        if body:
            set_cached_page("feature-status", body)
            response.headers["ETag"] = build_etag(body)
        response.headers["Cache-Control"] = "public, max-age=300"
        return response

    @application.get("/device-check", include_in_schema=False)
    async def device_check_page(request: Request):
        cached = get_cached_page("device-check")
        if cached is not None:
            if request.headers.get("if-none-match") == cached.etag:
                return HTMLResponse(status_code=304, content="")
            response = HTMLResponse(content=str(cached.content))
            response.headers["ETag"] = cached.etag
            response.headers["Cache-Control"] = "public, max-age=300"
            return response
        response = templates.TemplateResponse("device_check.html", {"request": request, "csrf_token": getattr(request.state, "csrf_token", "")})
        body = getattr(response, "body", b"").decode("utf-8", errors="ignore")
        if body:
            set_cached_page("device-check", body)
            response.headers["ETag"] = build_etag(body)
        response.headers["Cache-Control"] = "public, max-age=300"
        return response

    @application.get("/consultation/voice", include_in_schema=False)
    async def voice_consultation_page(request: Request):
        return templates.TemplateResponse("consultation/voice_consultation.html", {"request": request, "csrf_token": getattr(request.state, "csrf_token", "")})

    @application.get("/portal", include_in_schema=False)
    async def portal_redirect():
        return RedirectResponse(url="/dashboard", status_code=302)

    application.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
    application.mount("/shared-static", StaticFiles(directory=settings.shared_static_dir), name="shared-static")
    public_dir = settings.base_dir / "public"
    if public_dir.exists():
        application.mount("/public", StaticFiles(directory=public_dir), name="public")
    application.include_router(public_clinic_router)
    # FROZEN: not needed for clinic pilot v1
    # application.include_router(startup_router)
    application.include_router(health_router)
    application.include_router(backup_router)
    application.include_router(export_router)
    application.include_router(audit_router)
    application.include_router(patient_linking_router)
    application.include_router(auth_router)
    application.include_router(google_auth_router)
    application.include_router(new_frontend_router)
    application.include_router(patients_router)
    application.include_router(patient_tools_router)
    application.include_router(patient_agent_router)
    application.include_router(cases_router)
    application.include_router(contact_router)
    application.include_router(appointments_router)
    application.include_router(ai_router)
    application.include_router(ai_doctor_router)
    application.include_router(ai_dashboard_router)
    application.include_router(ayurveda_terms_router)
    application.include_router(dashboard_router)
    application.include_router(doctor_review_router)
    application.include_router(consultation_router)
    application.include_router(device_check_router)
    application.include_router(voice_consultation_router)
    application.include_router(voice_router)
    # FROZEN: not needed for clinic pilot v1
    # application.include_router(ai_pharmacy_router)
    application.include_router(ai_features_router)
    application.include_router(api_v1_router)
    # FROZEN: not needed for clinic pilot v1
    # application.include_router(marketplace_router)
    application.include_router(patient_portal_router)
    application.include_router(doctor_portal_router)
    # FROZEN: not needed for clinic pilot v1
    # application.include_router(pharmacy_portal_router)
    # FROZEN: not needed for clinic pilot v1
    # application.include_router(lab_portal_router)
    # FROZEN: not needed for clinic pilot v1
    # application.include_router(delivery_portal_router)
    application.include_router(medicine_info_router)
    # FROZEN: not needed for clinic pilot v1
    # application.include_router(delivery_router)
    application.include_router(debug_router)
    # FROZEN: not needed for clinic pilot v1
    # application.include_router(pharmacy_owner_router)
    # FROZEN: not needed for clinic pilot v1
    # application.include_router(lab_owner_router)
    # FROZEN: not needed for clinic pilot v1
    # application.include_router(lab_analyzer_router)
    # FROZEN: not needed for clinic pilot v1
    # application.include_router(pharmacy_router)
    application.include_router(prescription_ocr_router)
    application.include_router(profiles_router)
    application.include_router(pure_ai_router)
    # FROZEN: not needed for clinic pilot v1
    # application.include_router(ecommerce_router)
    # Enable medicine ordering
    application.include_router(order_medicines_router)
    # FROZEN: not needed for clinic pilot v1
    # application.include_router(subscriptions_router)
    application.include_router(admin_router)
    application.include_router(emr_router)
    application.include_router(ambient_emr_router)
    application.include_router(telemedicine_router)
    application.include_router(prescription_router)
    application.include_router(payment_router)
    application.include_router(outcome_router)
    # FROZEN: not needed for clinic pilot v1
    # application.include_router(demo_router)
    application.include_router(sales_router)
    application.include_router(statistics_router)

    @application.post("/api/ai-chat")
    async def ai_chat(payload: AIChatRequest):
        if not validate_prompt_injection(payload.message):
            return JSONResponse(status_code=400, content={"detail": "Invalid input detected"})
        prompt = f"""
        You are Dr. Kash, an AI assistant for Ayurvedic doctors.
        Context: {payload.context}
        Patient ID: {payload.patient_id or "New patient"}

        User query: {payload.message}

        Provide helpful Ayurvedic advice. Be concise, professional, and evidence-based.
        Focus on Ayurvedic principles, herbal remedies, and lifestyle recommendations.
        """
        response = await groq_client.chat([{"role": "user", "content": prompt}], temperature=0.7, max_tokens=500)
        if not response:
            normalized = payload.message.lower()
            if any(term in normalized for term in ["fever", "bukhar", "ज्वर", "ताप"]):
                response = "आपके लक्षणों से शरीर में गर्मी या संक्रमण जैसा संकेत मिल रहा है. पर्याप्त आराम करें, तरल लें, और तेज बुखार हो तो तुरंत डॉक्टर से मिलें."
            elif any(term in normalized for term in ["gas", "acidity", "stomach", "पेट"]):
                response = "पाचन असंतुलन की संभावना है. हल्का भोजन, समय पर खाना, और गुनगुना पानी लाभकारी हो सकता है."
            else:
                response = "मैं आपकी बात समझ गया. लक्षणों के पैटर्न, दिनचर्या, और आहार के आधार पर आगे बेहतर सलाह बनाई जा सकती है."

        actions = {}
        if "prescribe" in payload.message.lower() or "medicine" in payload.message.lower():
            actions["prescription"] = "Consider Triphala Churna 5g twice daily or as directed by your doctor."
        if "follow" in payload.message.lower() or "appointment" in payload.message.lower():
            actions["follow_up"] = "7 days from today"
        if "summary" in payload.message.lower():
            actions["summary"] = "Patient reported symptoms. Further evaluation recommended."

        return JSONResponse(
            {
                "response": response,
                "actions": actions or {
                    "summary": "संक्षिप्त आयुर्वेदिक सलाह: नियमित दिनचर्या और हल्का आहार रखें।",
                    "prescription": "त्रिफला, गुनगुना पानी, और तले हुए भोजन से परहेज़ पर विचार करें।",
                    "follow_up": "7 दिन के भीतर फॉलो-अप रखें।",
                },
            }
        )

    @application.get("/api/ai-chat", include_in_schema=False)
    async def ai_chat_probe(message: str = "Hello"):
        return await ai_chat(AIChatRequest(message=message))

    @application.get("/telemedicine/start", include_in_schema=False)
    async def telemedicine_start_probe():
        return {"success": True, "message": "Telemedicine initiation endpoint is available"}

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
