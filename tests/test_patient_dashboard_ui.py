from __future__ import annotations

from uuid import uuid4

import pytest

from tests.conftest import extract_csrf_token


pytestmark = pytest.mark.asyncio


async def _register_and_login_patient(client, email: str = "dashboard.patient@example.com") -> str:
    unique_email = email.replace("@", f".{uuid4().hex[:8]}@")
    unique_phone = f"98{uuid4().int % 10**8:08d}"

    register_page = await client.get("/auth/register/patient")
    assert register_page.status_code == 200
    register_csrf = extract_csrf_token(register_page.text)

    register_response = await client.post(
        "/api/auth/register",
        data={
            "csrf_token": register_csrf,
            "role": "patient",
            "full_name": "Dashboard Patient",
            "email": unique_email,
            "phone": unique_phone,
            "password": "PortalSecure123!",
        },
        headers={"X-CSRF-Token": register_csrf},
    )
    assert register_response.status_code == 200
    verification_token = register_response.json()["verification_token"]
    await client.get(f"/auth/verify-email?token={verification_token}", follow_redirects=False)

    login_page = await client.get("/auth/login/patient")
    assert login_page.status_code == 200
    login_csrf = extract_csrf_token(login_page.text)

    login_response = await client.post(
        "/auth/login",
        data={
            "csrf_token": login_csrf,
            "identifier": unique_email,
            "password": "PortalSecure123!",
            "role": "patient",
        },
        follow_redirects=False,
    )
    assert login_response.status_code == 303
    assert login_response.headers["location"] in {"/patient", "/profiles/add"}
    return login_csrf


async def _ensure_patient_profile(client) -> None:
    add_page = await client.get("/profiles/add")
    assert add_page.status_code == 200
    add_csrf = extract_csrf_token(add_page.text)

    add_response = await client.post(
        "/api/profiles/add",
        data={
            "csrf_token": add_csrf,
            "profile_name": "Dashboard Patient",
            "relationship": "Self",
            "avatar": "👤",
            "date_of_birth": "",
            "gender": "",
            "blood_group": "",
            "medical_conditions": "",
            "allergies": "",
            "pin_code": "",
        },
        headers={"X-CSRF-Token": add_csrf},
        follow_redirects=False,
    )
    assert add_response.status_code == 303


async def test_lab_analyzer_button_visible_on_patient_dashboard(client):
    """Verify that the Lab Analyzer button is present on patient dashboard."""

    await _register_and_login_patient(client, email="dashboard.lab.patient@example.com")
    await _ensure_patient_profile(client)

    dashboard_response = await client.get("/patient")
    assert dashboard_response.status_code == 200

    html = dashboard_response.text
    assert "lab analyzer" in html.lower() or "🔬" in html, "Lab Analyzer button missing from patient dashboard"
    assert "/lab-analyzer" in html, "Lab Analyzer link missing '/lab-analyzer' URL"


async def test_lab_analyzer_redirects_to_login_when_unauthenticated(client):
    """Verify that unauthenticated users are redirected to login."""

    response = await client.get("/lab-analyzer", follow_redirects=False)
    assert response.status_code in {302, 303}, f"Expected redirect, got {response.status_code}"

    location = response.headers.get("location", "")
    assert "login" in location.lower(), f"Should redirect to login, got {location}"


async def test_lab_analyzer_accessible_to_authenticated_patient(client):
    """Verify that authenticated patients can access lab analyzer page."""

    await _register_and_login_patient(client, email="dashboard.lab.access@example.com")

    response = await client.get("/lab-analyzer")
    assert response.status_code == 200, f"Lab analyzer page returned {response.status_code}"

    html = response.text
    assert "lab report" in html.lower() or "analyzer" in html.lower(), "Lab analyzer page content missing"
