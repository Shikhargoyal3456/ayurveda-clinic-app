from __future__ import annotations

from uuid import uuid4

import pytest

from routers import prescription_ocr
from tests.conftest import extract_csrf_token


pytestmark = pytest.mark.asyncio


async def _register_and_login_patient(client, email: str = "handwriting.patient@example.com"):
    unique_email = email.replace("@", f".{uuid4().hex[:8]}@")
    unique_phone = f"98{uuid4().int % 10**8:08d}"
    register_page = await client.get("/auth/register/patient")
    csrf_token = extract_csrf_token(register_page.text)

    register_response = await client.post(
        "/api/auth/register",
        data={
            "csrf_token": csrf_token,
            "role": "patient",
            "full_name": "Handwriting Patient",
            "email": unique_email,
            "phone": unique_phone,
            "password": "PortalSecure123!",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    token = register_response.json()["verification_token"]
    await client.get(f"/auth/verify-email?token={token}", follow_redirects=False)

    login_page = await client.get("/auth/login/patient")
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


async def test_handwriting_decoder_page_renders_for_patient(client):
    await _register_and_login_patient(client)

    response = await client.get("/prescription/decode-handwriting")
    assert response.status_code == 200
    assert "Decode Handwritten Prescription" in response.text
    assert "/api/prescription/decode-handwriting" in response.text


async def test_handwriting_decoder_api_returns_mocked_decode_result(client, monkeypatch):
    await _register_and_login_patient(client, email="handwriting.api.patient@example.com")

    page = await client.get("/prescription/decode-handwriting")
    csrf_token = extract_csrf_token(page.text)

    async def fake_decode(_image_data: str, mime_type: str = "image/jpeg"):
        assert mime_type == "image/png"
        return {
            "doctor_name": "Dr Test",
            "patient_name": "Portal Patient",
            "date": "2026-05-24",
            "medicines": [
                {
                    "medicine_name": "Paracetamol 500mg",
                    "dosage": "500mg",
                    "frequency": "Twice daily",
                    "duration": "5 days",
                    "special_instructions": "After food",
                    "confidence": 88,
                }
            ],
            "raw_decoded_text": "Paracetamol 500mg twice daily after food for 5 days.",
            "unreadable_parts": [],
            "confidence_overall": 84,
        }

    async def fake_enhance(medicines):
        medicines[0]["medicine_info"] = {
            "uses": ["Fever relief"],
            "side_effects": ["Nausea"],
            "prescription_required": False,
        }
        return medicines

    monkeypatch.setattr(prescription_ocr.ocr_service, "decode_prescription", fake_decode)
    monkeypatch.setattr(prescription_ocr.ocr_service, "enhance_with_medicine_info", fake_enhance)

    response = await client.post(
        "/api/prescription/decode-handwriting",
        files={"prescription_image": ("rx.png", b"fake-image-bytes", "image/png")},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["doctor_name"] == "Dr Test"
    assert payload["data"]["medicines"][0]["medicine_name"] == "Paracetamol 500mg"
