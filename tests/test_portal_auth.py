import pytest

from tests.conftest import extract_csrf_token


pytestmark = pytest.mark.asyncio


async def test_patient_portal_registration_and_smart_login(client):
    register_page = await client.get("/auth/register/patient")
    assert register_page.status_code == 200
    csrf_token = extract_csrf_token(register_page.text)

    register_response = await client.post(
        "/api/auth/register",
        data={
            "csrf_token": csrf_token,
            "role": "patient",
            "full_name": "Portal Patient",
            "email": "portal.patient@example.com",
            "phone": "9876543210",
            "password": "PortalSecure123!",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert register_response.status_code == 200
    register_payload = register_response.json()
    assert register_payload["success"] is True
    assert register_payload["redirect_url"] == "/auth/login"

    login_page = await client.get("/auth/login")
    login_csrf = extract_csrf_token(login_page.text)
    login_response = await client.post(
        "/auth/login",
        data={
            "csrf_token": login_csrf,
            "identifier": "portal.patient@example.com",
            "password": "PortalSecure123!",
        },
        follow_redirects=False,
    )
    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/patient"

    dashboard_response = await client.get("/patient")
    assert dashboard_response.status_code == 200
    assert "Kash AI" in dashboard_response.text

    account_type_response = await client.post("/api/auth/account-type", json={"identifier": "portal.patient@example.com"})
    assert account_type_response.status_code == 200
    assert account_type_response.json()["roles"] == ["Patient"]


async def test_portal_dashboard_redirects_without_matching_role(client):
    patient_login_page = await client.get("/auth/login")
    patient_csrf = extract_csrf_token(patient_login_page.text)
    register_response = await client.post(
        "/api/auth/register",
        data={
            "csrf_token": patient_csrf,
            "role": "patient",
            "full_name": "Role Guard User",
            "email": "role.guard@example.com",
            "phone": "9876543211",
            "password": "PortalSecure123!",
        },
        headers={"X-CSRF-Token": patient_csrf},
    )

    login_page = await client.get("/auth/login")
    login_csrf = extract_csrf_token(login_page.text)
    await client.post(
        "/auth/login",
        data={
            "csrf_token": login_csrf,
            "identifier": "role.guard@example.com",
            "password": "PortalSecure123!",
        },
        follow_redirects=False,
    )

    denied = await client.get("/portal/pharmacy", follow_redirects=False)
    assert denied.status_code == 303
    assert denied.headers["location"] == "/patient"


async def test_smart_login_accepts_legacy_admin_workspace_credentials(admin_client):
    client = admin_client["client"]

    login_page = await client.get("/auth/login?role=doctor")
    login_csrf = extract_csrf_token(login_page.text)
    response = await client.post(
        "/auth/login",
        data={
            "csrf_token": login_csrf,
            "identifier": admin_client["username"],
            "password": admin_client["password"],
            "role": "doctor",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] in {"/admin", "/dashboard"}
