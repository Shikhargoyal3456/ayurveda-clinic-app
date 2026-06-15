from __future__ import annotations

import pytest

from app.models import CaseSheet, Patient
from models.prescription import Prescription
from routers import patient_agent as patient_agent_router


pytestmark = pytest.mark.asyncio


async def test_patient_agent_emergency_fallback_creates_doctor_alert(authenticated_client, doctor_for_credentials, db_session, monkeypatch):
    client = authenticated_client["client"]
    doctor = doctor_for_credentials(authenticated_client["username"])

    patient = Patient(
        doctor_id=doctor.id,
        name="Emergency Test Patient",
        age=52,
        gender="Male",
        phone="9876543211",
        email="emergency@test.local",
        address="Jaipur",
    )
    db_session.add(patient)
    db_session.flush()

    db_session.add(
        CaseSheet(
            patient_id=patient.id,
            diagnosis="Hypertension",
            symptoms="Headache and fatigue",
            notes="Known BP fluctuations.",
        )
    )
    db_session.add(
        Prescription(
            patient_id=patient.id,
            doctor_id=doctor.id,
            profile_name=patient.name,
            diagnosis="Hypertension",
            medicines=[{"name": "Amlodipine", "dosage": "5 mg", "frequency": "Once daily", "duration": "30"}],
            advice="Monitor blood pressure.",
            follow_up_days=7,
        )
    )
    db_session.commit()

    async def fake_call_gemini(*args, **kwargs):
        return "[NORMAL] Please rest and monitor symptoms."

    async def fake_notify_doctor_of_alert(doctor, patient, query):
        return {"success": True}

    monkeypatch.setattr(patient_agent_router, "call_gemini", fake_call_gemini)
    monkeypatch.setattr(patient_agent_router, "notify_doctor_of_alert", fake_notify_doctor_of_alert)
    monkeypatch.setattr(patient_agent_router, "is_gemini_configured", lambda: True)

    response = await client.post(
        "/api/patient-agent/ask",
        json={
            "patient_id": patient.id,
            "message": "I have chest pain and difficulty breathing since this morning.",
            "channel": "app",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["severity"] == "emergency"
    assert payload["doctor_alerted"] is True
    assert "112" in payload["reply"]

    alerts_response = await client.get(f"/api/doctor/{doctor.id}/alerts")
    assert alerts_response.status_code == 200
    alerts_payload = alerts_response.json()
    assert alerts_payload["success"] is True
    assert any(item["patient_name"] == "Emergency Test Patient" and item["severity"] == "emergency" for item in alerts_payload["alerts"])
