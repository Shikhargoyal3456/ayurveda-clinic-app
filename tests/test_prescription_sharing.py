from __future__ import annotations

import pytest

from app.models import Patient
from models.prescription import Prescription
from routes import prescription as prescription_routes
from tests.conftest import extract_csrf_token


pytestmark = pytest.mark.asyncio


async def _create_patient_and_prescription(authenticated_client, doctor_for_credentials, db_session):
    doctor = doctor_for_credentials(authenticated_client["username"])
    patient = Patient(
        doctor_id=doctor.id,
        name="Share Test Patient",
        age=34,
        gender="Female",
        phone="9876543210",
        email="patient.share@testmail.local",
        address="Delhi",
    )
    db_session.add(patient)
    db_session.flush()

    prescription = Prescription(
        patient_id=patient.id,
        doctor_id=doctor.id,
        profile_name=patient.name,
        diagnosis="Pitta aggravation with headache",
        medicines=[
            {"name": "Guduchi", "dosage": "1 tablet", "frequency": "Twice daily", "duration": "7"},
            {"name": "Avipattikar", "dosage": "1 tsp", "frequency": "After meals", "duration": "5"},
        ],
        advice="Hydrate well and avoid spicy foods.",
        follow_up_days=7,
    )
    db_session.add(prescription)
    db_session.commit()
    db_session.refresh(prescription)
    return patient, prescription


async def test_prescription_share_email_endpoint_returns_success(authenticated_client, doctor_for_credentials, db_session, monkeypatch):
    client = authenticated_client["client"]
    _, prescription = await _create_patient_and_prescription(authenticated_client, doctor_for_credentials, db_session)

    async def fake_send_prescription_email(*, patient_email, patient_name, doctor_name, prescription_data):
        assert patient_email == "custom@example.org"
        assert patient_name == "Share Test Patient"
        assert doctor_name
        assert prescription_data["diagnosis"] == "Pitta aggravation with headache"
        return {"success": True, "message": "Email sent successfully"}

    monkeypatch.setattr(prescription_routes, "send_prescription_email", fake_send_prescription_email)

    detail_page = await client.get(f"/prescriptions/{prescription.id}")
    assert detail_page.status_code == 200
    csrf_token = extract_csrf_token(detail_page.text)

    response = await client.post(
        f"/prescriptions/{prescription.id}/share-email",
        json={"patient_email": "custom@example.org"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True


async def test_prescription_share_whatsapp_endpoint_returns_wa_me_link(authenticated_client, doctor_for_credentials, db_session):
    client = authenticated_client["client"]
    _, prescription = await _create_patient_and_prescription(authenticated_client, doctor_for_credentials, db_session)

    response = await client.post(f"/prescriptions/{prescription.id}/share-whatsapp")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["method"] == "wa_me_link"
    assert payload["whatsapp_link"].startswith("https://wa.me/91")
    assert "text=" in payload["whatsapp_link"]
