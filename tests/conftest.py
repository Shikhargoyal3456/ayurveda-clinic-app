import os
import re
import shutil
import time
import uuid
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
import sys
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.models  # noqa: E402
sys.modules.setdefault("models", app.models)
import app.models.user  # noqa: E402
sys.modules.setdefault("models.user", app.models.user)
import app.models.supplier  # noqa: E402
sys.modules.setdefault("models.supplier", app.models.supplier)


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
os.environ["ADMIN_USERNAMES"] = "admin,admin@ayurveda.com"

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("TRUSTED_HOSTS", "127.0.0.1,localhost,testserver")
os.environ.setdefault("TEST_MODE", "true")
os.environ.setdefault("TEST_UPLOADS_DIR", str(PROJECT_ROOT / "temp" / "test-uploads"))

from app.database import SessionLocal, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.config import settings  # noqa: E402
object.__setattr__(settings, "admin_usernames", ("admin", "admin@ayurveda.com"))


from app.models import Doctor  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402

from app.auth import _RATE_LIMIT_BUCKETS, hash_password  # noqa: E402
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


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_uploads():
    upload_root = PROJECT_ROOT / "temp" / "test-uploads"
    upload_root.mkdir(parents=True, exist_ok=True)
    yield upload_root
    shutil.rmtree(upload_root, ignore_errors=True)


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
    assert signup_response.headers["location"] in {"/login", "/dashboard", "/auth/login", "/auth/signup", "/patient/dashboard", "/new/doctor", "/new/dashboard"}

    if signup_response.headers["location"] in {"/dashboard", "/patient/dashboard", "/new/dashboard", "/new/doctor"}:
        return {"username": username, "password": password}


    login_page = await client.get("/login", follow_redirects=False)
    if login_page.status_code in {302, 303}:
        return {"username": username, "password": password}


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
    assert login_response.headers["location"] in {"/dashboard", "/patient/dashboard", "/new/dashboard", "/doctor", "/v2/admin/accuracy-dashboard"}

    return {"username": username, "password": password}


@pytest_asyncio.fixture
async def authenticated_client(client: AsyncClient):
    credentials = await signup_and_login(client)
    return {"client": client, **credentials}


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient):
    admin_username = "admin@ayurveda.com"
    password = "VerySecurePass123!"

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == admin_username).first()
        if user:
            user.password_hash = hash_password(password)
            user.is_verified = True
            user.is_active = True
            user.role = UserRole.admin
            db.commit()
        else:
            user = User(
                email=admin_username,
                password_hash=hash_password(password),
                full_name="Admin Doctor",
                role=UserRole.admin,
                is_verified=True,
                is_active=True,
            )
            db.add(user)
            db.commit()

        doctor = db.query(Doctor).filter(Doctor.username == admin_username).first()
        if doctor:
            doctor.password_hash = hash_password(password)
            doctor.session_version = 1
            doctor.refresh_token_hash = None
            db.commit()

        else:
            doctor = Doctor(
                username=admin_username,
                full_name="Admin Doctor",
                password_hash=hash_password(password),
                session_version=1,
            )
            db.add(doctor)
            db.commit()
    client.cookies.clear()
    login_page = await client.get("/login", follow_redirects=True)

    login_token = extract_csrf_token(login_page.text)
    login_resp = await client.post(
        "/login",
        data={
            "username": admin_username,
            "password": password,
            "csrf_token": login_token,
        },
        follow_redirects=True,
    )
    assert login_resp.status_code == 200

    return {"client": client, "username": admin_username, "password": password}













@pytest.fixture
def doctor_for_credentials(db_session):
    def _lookup(username: str) -> Doctor:
        doctor = db_session.query(Doctor).filter(Doctor.username == username).one()
        return doctor

    return _lookup
