import uuid

import pytest

from tests.conftest import extract_csrf_token


pytestmark = pytest.mark.asyncio


async def test_signup_login_and_dashboard_session(client):
    signup_page = await client.get("/signup")
    assert signup_page.status_code == 200
    signup_token = extract_csrf_token(signup_page.text)

    signup_response = await client.post(
        "/signup",
        data={
            "username": (username := f"authflow_{uuid.uuid4().hex[:8]}"),
            "password": "VerySecurePass123!",
            "full_name": "Auth Flow Doctor",
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
            "password": "VerySecurePass123!",
            "csrf_token": login_token,
        },
        follow_redirects=False,
    )
    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/dashboard"
    assert "session" in client.cookies

    dashboard_response = await client.get("/dashboard")
    assert dashboard_response.status_code == 200
    assert "Auth Flow Doctor" in dashboard_response.text or "Dashboard" in dashboard_response.text


async def test_duplicate_patient_email_does_not_crash_dashboard_flow(authenticated_client):
    client = authenticated_client["client"]

    dashboard_page = await client.get("/dashboard")
    assert dashboard_page.status_code == 200

    from tests.conftest import extract_csrf_token

    csrf_token = extract_csrf_token(dashboard_page.text)
    payload = {
        "name": "Patient One",
        "age": "30",
        "gender": "Female",
        "phone": "9999999999",
        "email": "same@example.com",
        "address": "Bengaluru",
        "csrf_token": csrf_token,
    }

    first_response = await client.post("/patients", data=payload, follow_redirects=False)
    assert first_response.status_code == 303
    assert first_response.headers["location"] == "/dashboard"

    dashboard_page = await client.get("/dashboard")
    csrf_token = extract_csrf_token(dashboard_page.text)
    payload["csrf_token"] = csrf_token
    payload["name"] = "Patient Two"

    second_response = await client.post("/patients", data=payload, follow_redirects=False)
    assert second_response.status_code == 303
    assert second_response.headers["location"] == "/dashboard"

    final_dashboard = await client.get("/dashboard")
    assert final_dashboard.status_code == 200
    assert "already exists in your clinic" in final_dashboard.text
