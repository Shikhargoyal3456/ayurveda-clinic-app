from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _get_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except ValueError:
        return default


def _get_list(name: str, default: list[str] | None = None) -> list[str]:
    raw_value = os.getenv(name, "")
    if not raw_value:
        return list(default or [])
    return [item.strip() for item in raw_value.split(",") if item.strip()]


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    app_version: str
    environment: str
    debug: bool
    base_dir: Path
    templates_dir: Path
    static_dir: Path
    logs_dir: Path
    data_dir: Path
    backups_dir: Path
    samhita_pdfs_dir: Path
    vector_store_dir: Path
    database_url: str
    clinic_name: str
    ollama_api_url: str
    ollama_model: str
    embedding_model: str
    secret_key: str
    allow_public_signup: bool
    faiss_top_k: int
    chunk_size_words: int
    chunk_overlap_words: int
    ollama_timeout_seconds: int
    ollama_max_retries: int
    ollama_soft_timeout_seconds: int
    ollama_keep_alive: str
    gemini_api_key: str
    gemini_model: str
    # Google Maps API key for Places & Distance Matrix
    google_maps_api_key: str
    razorpay_key_id: str
    razorpay_key_secret: str
    whatsapp_access_token: str
    whatsapp_phone_number_id: str
    whatsapp_api_version: str
    whatsapp_template_name: str
    whatsapp_template_language_code: str
    email_user: str
    email_password: str
    redis_url: str
    ai_cache_enabled: bool
    ai_cache_ttl_seconds: int
    ai_enabled: bool
    ai_fallback_cache_ttl_seconds: int
    ai_failure_log_path: Path
    session_https_only: bool
    session_same_site: str
    session_idle_timeout_minutes: int
    session_refresh_window_minutes: int
    https_redirect_enabled: bool
    host: str
    port: int
    reload: bool
    startup_rag_warmup: bool
    startup_llm_warmup: bool
    allowed_origins: list[str]
    trusted_hosts: list[str]
    admin_usernames: list[str]
    analytics_log_path: Path
    audit_log_path: Path
    request_log_path: Path
    schema_log_path: Path
    verify_ollama_on_startup: bool
    require_https_in_production: bool
    runtime_python: str

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_testing(self) -> bool:
        return self.environment == "testing"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


def _detect_environment() -> str:
    explicit = os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or os.getenv("ENV") or ""
    if explicit:
        return explicit.strip().lower()
    if _get_bool("PYTEST_CURRENT_TEST", False):
        return "testing"
    return "development"


def _build_settings() -> Settings:
    environment = _detect_environment()
    debug = _get_bool("DEBUG", environment != "production")
    base_dir = BASE_DIR
    logs_dir = base_dir / "logs"

    settings = Settings(
        app_version=os.getenv("APP_VERSION", "1.0.0").strip() or "1.0.0",
        environment=environment,
        debug=debug,
        base_dir=base_dir,
        templates_dir=base_dir / "templates",
        static_dir=base_dir / "static",
        logs_dir=logs_dir,
        data_dir=base_dir / "data",
        backups_dir=base_dir / "backups",
        samhita_pdfs_dir=base_dir / "samhita_pdfs",
        vector_store_dir=base_dir / "vector_store",
        database_url=os.getenv("DATABASE_URL", "sqlite:///./ayurveda_clinic.db"),
        clinic_name=os.getenv("CLINIC_NAME", "Kash AI"),
        ollama_api_url=os.getenv("OLLAMA_API_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "phi3:mini"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        secret_key=os.getenv("SECRET_KEY", "change-this-secret-before-production"),
        allow_public_signup=_get_bool("ALLOW_PUBLIC_SIGNUP", True),
        faiss_top_k=_get_int("FAISS_TOP_K", 3),
        chunk_size_words=_get_int("CHUNK_SIZE_WORDS", 360),
        chunk_overlap_words=_get_int("CHUNK_OVERLAP_WORDS", 60),
        ollama_timeout_seconds=_get_int("OLLAMA_TIMEOUT_SECONDS", _get_int("AI_TIMEOUT", 30)),
        ollama_max_retries=_get_int("OLLAMA_MAX_RETRIES", 2),
        ollama_soft_timeout_seconds=_get_int("OLLAMA_SOFT_TIMEOUT_SECONDS", 18),
        ollama_keep_alive=os.getenv("OLLAMA_KEEP_ALIVE", "30m"),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        google_maps_api_key=os.getenv("GOOGLE_MAPS_API_KEY", ""),
        razorpay_key_id=os.getenv("RAZORPAY_KEY_ID", ""),
        razorpay_key_secret=os.getenv("RAZORPAY_KEY_SECRET", ""),
        whatsapp_access_token=os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip(),
        whatsapp_phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip(),
        whatsapp_api_version=os.getenv("WHATSAPP_API_VERSION", "v23.0").strip() or "v23.0",
        whatsapp_template_name=os.getenv("WHATSAPP_TEMPLATE_NAME", "").strip(),
        whatsapp_template_language_code=os.getenv("WHATSAPP_TEMPLATE_LANGUAGE_CODE", "en_US").strip() or "en_US",
        email_user=os.getenv("EMAIL_USER", "").strip(),
        email_password=os.getenv("EMAIL_PASSWORD", "").strip(),
        redis_url=os.getenv("REDIS_URL", ""),
        ai_cache_enabled=_get_bool("AI_CACHE_ENABLED", False),
        ai_cache_ttl_seconds=_get_int("AI_CACHE_TTL_SECONDS", 3600),
        ai_enabled=_get_bool("AI_ENABLED", True),
        ai_fallback_cache_ttl_seconds=_get_int("AI_FALLBACK_CACHE_TTL_SECONDS", 1800),
        ai_failure_log_path=logs_dir / "ai_failures.jsonl",
        session_https_only=_get_bool("SESSION_HTTPS_ONLY", environment == "production"),
        session_same_site=os.getenv("SESSION_SAME_SITE", "lax"),
        session_idle_timeout_minutes=_get_int("SESSION_IDLE_TIMEOUT_MINUTES", 720),
        session_refresh_window_minutes=_get_int("SESSION_REFRESH_WINDOW_MINUTES", 30),
        https_redirect_enabled=_get_bool("HTTPS_REDIRECT_ENABLED", environment == "production"),
        host=os.getenv("HOST", "0.0.0.0"),
        port=_get_int("PORT", 8000),
        reload=_get_bool("UVICORN_RELOAD", False),
        startup_rag_warmup=_get_bool("STARTUP_RAG_WARMUP", environment != "production"),
        startup_llm_warmup=_get_bool("STARTUP_LLM_WARMUP", environment != "production"),
        allowed_origins=_get_list("ALLOWED_ORIGINS", ["http://127.0.0.1:8000", "http://localhost:8000"]),
        trusted_hosts=_get_list("TRUSTED_HOSTS", ["127.0.0.1", "localhost", "testserver"]),
        admin_usernames=_get_list("ADMIN_USERNAMES"),
        analytics_log_path=logs_dir / "analytics.jsonl",
        audit_log_path=logs_dir / "security_audit.jsonl",
        request_log_path=logs_dir / "application.log",
        schema_log_path=logs_dir / "schema_migrations.log",
        verify_ollama_on_startup=_get_bool("VERIFY_OLLAMA_ON_STARTUP", False),
        require_https_in_production=_get_bool("REQUIRE_HTTPS_IN_PRODUCTION", True),
        runtime_python=os.getenv(
            "RUNTIME_PYTHON",
            r"C:\Users\goyal\AppData\Local\ayurveda-runtime\Scripts\python.exe",
        ),
    )

    if settings.is_production:
        if settings.secret_key == "change-this-secret-before-production":
            raise ValueError("SECRET_KEY must be set to a strong value in production.")
        if settings.require_https_in_production and not settings.session_https_only:
            raise ValueError("SESSION_HTTPS_ONLY must be true in production.")

    return settings


settings = _build_settings()
