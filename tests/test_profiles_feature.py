import pytest
import uuid

from tests.conftest import extract_csrf_token


pytestmark = pytest.mark.asyncio


async def _register_and_login_patient(client, email: str = "family.patient@example.com", phone: str = "9876500001"):
    register_page = await client.get("/auth/register/patient")
    assert register_page.status_code == 200
    register_csrf = extract_csrf_token(register_page.text)

    register_response = await client.post(
        "/api/auth/register",
        data={
            "csrf_token": register_csrf,
            "role": "patient",
            "full_name": "Family Patient",
            "email": email,
            "phone": phone,
            "password": "PortalSecure123!",
        },
        headers={"X-CSRF-Token": register_csrf},
    )
    assert register_response.status_code == 200

    login_page = await client.get("/auth/login")
    assert login_page.status_code == 200
    login_csrf = extract_csrf_token(login_page.text)

    login_response = await client.post(
        "/auth/login",
        data={
            "csrf_token": login_csrf,
            "identifier": email,
            "password": "PortalSecure123!",
        },
        follow_redirects=False,
    )
    assert login_response.status_code == 303
    return login_response


async def _login_patient(client, email: str):
    login_page = await client.get("/auth/login")
    assert login_page.status_code == 200
    login_csrf = extract_csrf_token(login_page.text)

    login_response = await client.post(
        "/auth/login",
        data={
            "csrf_token": login_csrf,
            "identifier": email,
            "password": "PortalSecure123!",
        },
        follow_redirects=False,
    )
    assert login_response.status_code == 303
    return login_response


async def test_profile_pages_support_head_requests(client):
    for path in ("/profiles/select", "/profiles/add", "/profiles/manage"):
        response = await client.head(path, follow_redirects=False)
        assert response.status_code in {303, 307}


async def test_patient_with_multiple_profiles_redirects_to_selector_and_lists_profiles(client):
    unique_suffix = uuid.uuid4().hex[:8]
    unique_email = f"profile_test_{unique_suffix}@example.com"
    unique_phone = f"98765{unique_suffix[:5]}"
    first_login = await _register_and_login_patient(client, email=unique_email, phone=unique_phone)
    assert first_login.headers["location"] in {"/patient", "/profiles/add"}

    add_page = await client.get("/profiles/add")
    assert add_page.status_code == 200
    add_csrf = extract_csrf_token(add_page.text)

    first_add = await client.post(
        "/api/profiles/add",
        data={
            "csrf_token": add_csrf,
            "profile_name": "Test Patient",
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
    assert first_add.status_code == 303

    second_page = await client.get("/profiles/add")
    assert second_page.status_code == 200
    second_csrf = extract_csrf_token(second_page.text)
    second_add = await client.post(
        "/api/profiles/add",
        data={
            "csrf_token": second_csrf,
            "profile_name": "Dad",
            "relationship": "Father",
            "avatar": "👴",
            "date_of_birth": "",
            "gender": "",
            "blood_group": "",
            "medical_conditions": "",
            "allergies": "",
            "pin_code": "1234",
        },
        headers={"X-CSRF-Token": second_csrf},
        follow_redirects=False,
    )
    assert second_add.status_code == 303

    await client.get("/auth/logout", follow_redirects=False)
    relogin = await _login_patient(client, email=unique_email)
    assert relogin.headers["location"] == "/profiles/select"

    selector = await client.get("/profiles/select")
    assert selector.status_code == 200
    assert "Test Patient" in selector.text
    assert "Dad" in selector.text

    profiles_response = await client.get("/api/profiles/list")
    assert profiles_response.status_code == 200
    payload = profiles_response.json()
    assert len(payload["profiles"]) >= 2
    dad_profile = next(profile for profile in payload["profiles"] if profile["profile_name"] == "Dad")

    select_response = await client.post("/api/profiles/select", json={"profile_id": dad_profile["id"]})
    assert select_response.status_code == 200
    assert select_response.json()["requires_pin"] is True

    wrong_pin = await client.post("/api/profiles/verify-pin", json={"profile_id": dad_profile["id"], "pin": "0000"})
    assert wrong_pin.status_code == 401

    right_pin = await client.post("/api/profiles/verify-pin", json={"profile_id": dad_profile["id"], "pin": "1234"})
    assert right_pin.status_code == 200
    assert right_pin.json()["success"] is True
