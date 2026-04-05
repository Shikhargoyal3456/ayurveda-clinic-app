import os
import re
import time
import uuid
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
PYTEST_TEMP_ROOT = PROJECT_ROOT / "logs" / "pytest-temp-root"
PYTEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("TMP", str(PYTEST_TEMP_ROOT))
os.environ.setdefault("TEMP", str(PYTEST_TEMP_ROOT))
os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", str(PYTEST_TEMP_ROOT))

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

TEST_DB_PATH = TESTS_DIR / ".pytest_ayurveda.db"

os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DB_PATH.as_posix()}")
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

from app.database import SessionLocal, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.config import settings  # noqa: E402
from app.models import Doctor  # noqa: E402
from app.auth import _RATE_LIMIT_BUCKETS  # noqa: E402
from routers.ai import _AI_RATE_LIMIT_BUCKETS, rebuild_status  # noqa: E402


def _unlink_with_retry(
    path: Path,
    retries: int = 5,
    delay_seconds: float = 0.2,
    ignore_final_permission_error: bool = False,
) -> None:
    for attempt in range(retries):
        if not path.exists():
            return
        try:
            path.unlink()
            return
        except PermissionError:
            if attempt == retries - 1:
                if ignore_final_permission_error:
                    return
                raise
            time.sleep(delay_seconds * (attempt + 1))


def extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if match is None:
        match = re.search(r'value="([^"]+)"\s+name="csrf_token"', html)
    if match is None:
        raise AssertionError("CSRF token not found in response HTML.")
    return match.group(1)


@pytest.fixture(scope="session", autouse=True)
def initialized_database():
    engine.dispose()
    for suffix in ("", "-shm", "-wal"):
        db_file = Path(f"{TEST_DB_PATH}{suffix}")
        _unlink_with_retry(db_file, ignore_final_permission_error=True)
    init_db()
    yield
    engine.dispose()
    for suffix in ("", "-shm", "-wal"):
        db_file = Path(f"{TEST_DB_PATH}{suffix}")
        _unlink_with_retry(db_file, ignore_final_permission_error=True)


@pytest.fixture(autouse=True)
def reset_runtime_state():
    _RATE_LIMIT_BUCKETS.clear()
    _AI_RATE_LIMIT_BUCKETS.clear()
    rebuild_status.update(
        {
            "running": False,
            "last_started": None,
            "last_finished": None,
            "last_error": None,
            "progress_message": "idle",
        }
    )
    yield


@pytest_asyncio.fixture
async def client(initialized_database):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


@pytest.fixture
def db_session(initialized_database):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


async def signup_and_login(client: AsyncClient, username: str | None = None, password: str | None = None) -> dict[str, str]:
    username = username or f"doctor_{uuid.uuid4().hex[:10]}"
    password = password or "VerySecurePass123!"

    signup_page = await client.get("/signup")
    assert signup_page.status_code == 200
    signup_token = extract_csrf_token(signup_page.text)

    signup_response = await client.post(
        "/signup",
        data={
            "username": username,
            "password": password,
            "full_name": "Test Doctor",
            "csrf_token": signup_token,
        },
        follow_redirects=False,
    )
    assert signup_response.status_code == 303
    assert signup_response.headers["location"] == "/login"

    login_page = await client.get("/login")
    assert login_page.status_code == 200
    login_token = extract_csrf_token(login_page.text)

    login_response = await client.post(
        "/login",
        data={
            "username": username,
            "password": password,
            "csrf_token": login_token,
        },
        follow_redirects=False,
    )
    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/dashboard"

    return {"username": username, "password": password}


@pytest_asyncio.fixture
async def authenticated_client(client: AsyncClient):
    credentials = await signup_and_login(client)
    return {"client": client, **credentials}


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient):
    admin_username = (settings.admin_usernames[0] if settings.admin_usernames else "admin@ayurveda.com")
    password = "VerySecurePass123!"

    signup_page = await client.get("/signup")
    assert signup_page.status_code == 200
    signup_token = extract_csrf_token(signup_page.text)

    signup_response = await client.post(
        "/signup",
        data={
            "username": admin_username,
            "password": password,
            "full_name": "Admin Doctor",
            "csrf_token": signup_token,
        },
        follow_redirects=False,
    )
    assert signup_response.status_code == 303
    assert signup_response.headers["location"] in {"/login", "/signup"}

    login_page = await client.get("/login")
    assert login_page.status_code == 200
    login_token = extract_csrf_token(login_page.text)

    login_response = await client.post(
        "/login",
        data={
            "username": admin_username,
            "password": password,
            "csrf_token": login_token,
        },
        follow_redirects=False,
    )
    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/dashboard"

    return {"client": client, "username": admin_username, "password": password}


@pytest.fixture
def doctor_for_credentials(db_session):
    def _lookup(username: str) -> Doctor:
        doctor = db_session.query(Doctor).filter(Doctor.username == username).one()
        return doctor

    return _lookup
