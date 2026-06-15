from __future__ import annotations

from datetime import date, timedelta
import uuid

import pytest

from app.database import commit_with_retry
from app.models import Appointment, CaseSheet, Patient
from tests.conftest import extract_csrf_token


pytestmark = pytest.mark.asyncio


async def _signup_and_login_current_flow(client) -> dict[str, str]:
    username = f"doctor_ai_{uuid.uuid4().hex[:10]}"
    password = "VerySecurePass123!"

    signup_page = await client.get("/signup")
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
    assert signup_response.headers["location"] in {"/login", "/dashboard"}

    if signup_response.headers["location"] == "/login":
        login_page = await client.get("/login")
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


async def test_dashboard_morning_brief_endpoint_and_ui(client, db_session, doctor_for_credentials, monkeypatch):
    credentials = await _signup_and_login_current_flow(client)
    doctor = doctor_for_credentials(credentials["username"])
    doctor.full_name = "Morning Doctor"
    commit_with_retry(db_session)

    patient_followup = Patient(
        doctor_id=doctor.id,
        name="Riya Followup",
        age=41,
        gender="Female",
        phone="9999999991",
        email="riya.followup@example.com",
    )
    patient_new = Patient(
        doctor_id=doctor.id,
        name="Arjun New",
        age=28,
        gender="Male",
        phone="9999999992",
        email="arjun.new@example.com",
    )
    db_session.add_all([patient_followup, patient_new])
    commit_with_retry(db_session)

    db_session.add_all(
        [
            Appointment(patient_id=patient_followup.id, date=date.today(), time="09:00", reason="Follow-up"),
            Appointment(patient_id=patient_new.id, date=date.today(), time="10:00", reason="First consult"),
            CaseSheet(
                patient_id=patient_followup.id,
                prakriti="Vata",
                diagnosis="Migraine",
                symptoms="Headache",
                notes="Prior visit",
                followup_date=date.today() - timedelta(days=3),
            ),
        ]
    )
    commit_with_retry(db_session)

    async def fake_call_gemini(prompt: str, **kwargs):
        assert "Today's patients: 2" in prompt
        assert "Riya Followup" in prompt
        return (
            "Good morning Dr. Morning Doctor. You have 2 patients today. "
            "Riya Followup's follow-up is overdue by 3 days and Arjun New is new with no prior history."
        )

    monkeypatch.setattr("services.ai_provider.call_gemini", fake_call_gemini)

    dashboard_response = await client.get("/dashboard")
    assert dashboard_response.status_code == 200
    assert "AI Morning Brief" in dashboard_response.text

    response = await client.get("/api/dashboard/morning-brief")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert "Good morning Dr. Morning Doctor" in payload["data"]["brief"]
    assert payload["data"]["appointments_count"] == 2
    assert payload["data"]["overdue_count"] == 1


async def test_structure_for_field_returns_symptom_suggestions(
    client,
    db_session,
    doctor_for_credentials,
    monkeypatch,
):
    credentials = await _signup_and_login_current_flow(client)
    doctor = doctor_for_credentials(credentials["username"])

    patient = Patient(
        doctor_id=doctor.id,
        name="Voice Patient",
        age=35,
        gender="Female",
        phone="9999999993",
        email="voice.patient@example.com",
    )
    db_session.add(patient)
    commit_with_retry(db_session)

    monkeypatch.setattr("routers.ai_doctor._assert_ai_configured", lambda: None)

    async def fake_call_gemini(prompt: str, **kwargs):
        assert "Transcribed symptoms description" in prompt
        return '{"symptoms":["Bloating after meals","Acidity at night"],"dosha":"Pitta-Kapha","prakriti_insight":"Pitta tendency","vikriti":"Amla-pitta pattern"}'

    monkeypatch.setattr("routers.ai_doctor.call_gemini", fake_call_gemini)

    add_case_page = await client.get(f"/patients/{patient.id}/cases/new")
    assert add_case_page.status_code == 200
    csrf_token = extract_csrf_token(add_case_page.text)

    response = await client.post(
        "/api/ai/structure-for-field",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "field_name": "symptoms",
            "transcribed_text": "Patient says bloating after meals and acidity at night",
            "patient_id": patient.id,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert "- Bloating after meals" in payload["structured_text"]
    assert payload["suggestions"]["dosha"] == "Pitta-Kapha"
    assert payload["suggestions"]["vikriti"] == "Amla-pitta pattern"


async def test_structure_for_field_rejects_missing_csrf(client, db_session, doctor_for_credentials):
    credentials = await _signup_and_login_current_flow(client)
    doctor = doctor_for_credentials(credentials["username"])

    patient = Patient(
        doctor_id=doctor.id,
        name="CSRF Patient",
        age=32,
        gender="Male",
        phone="9999999994",
        email="csrf.patient@example.com",
    )
    db_session.add(patient)
    commit_with_retry(db_session)

    response = await client.post(
        "/api/ai/structure-for-field",
        json={
            "field_name": "diagnosis",
            "transcribed_text": "Vata-Pitta imbalance with Ama",
            "patient_id": patient.id,
        },
    )
    assert response.status_code == 403
