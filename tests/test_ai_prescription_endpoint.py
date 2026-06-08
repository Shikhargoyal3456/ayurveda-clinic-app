import pytest

import routers.ai as ai_router
import routers.cases as cases_router
from app.database import commit_with_retry
from app.models import CaseSheet, Patient
from tests.conftest import extract_csrf_token


pytestmark = pytest.mark.asyncio


class _DummyEngine:
    def generate_clinical_response(self, symptoms, patient_context="", specialty="ayurveda"):
        return {
            "answer": "Doctor review required. Support BP, monitor readings, and evaluate risk factors.",
            "sources": ["fallback"],
            "context_passages": [],
            "mode": "fallback",
        }


async def test_case_generate_ai_handles_structured_dict_payloads(
    authenticated_client,
    db_session,
    doctor_for_credentials,
    monkeypatch,
):
    client = authenticated_client["client"]
    doctor = doctor_for_credentials(authenticated_client["username"])

    patient = Patient(
        doctor_id=doctor.id,
        name="Structured Case Patient",
        age=51,
        gender="male",
        phone="9990001234",
        email="structured@example.com",
        address="Gurugram",
    )
    db_session.add(patient)
    commit_with_retry(db_session)

    case = CaseSheet(
        patient_id=patient.id,
        prakriti="vattaj",
        diagnosis="High BP",
        symptoms="{'complaint': 'High BP (Hypertension)', 'duration': None, 'severity': None}",
        notes="{'general_examination': None, 'medicines': [], 'notes': 'Patient has elevated blood pressure.'}",
    )
    db_session.add(case)
    commit_with_retry(db_session)

    monkeypatch.setattr(
        cases_router,
        "generate_role_based_prescription_sync",
        lambda case_data, mode: {
            "success": True,
            "prescription": f"Doctor review required. Mode={mode}. Support BP, monitor readings, and evaluate risk factors.",
            "mode": mode,
            "references": ["Charaka Samhita"],
        },
    )

    page = await client.get(f"/patients/{patient.id}/cases")
    csrf_token = extract_csrf_token(page.text)

    response = await client.post(
        f"/api/cases/{case.id}/generate-ai",
        json={},
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "Doctor review required" in payload["ai_view"]["raw_answer"]
    assert "Charaka Samhita" in payload["ai_view"]["sources"]


def test_case_generate_ai_normalizes_list_payloads_without_type_errors():
    payload = cases_router._normalize_case_ai_payload(
        {
            "prakriti": ["vata", "pitta"],
            "diagnosis": ["Migraine", "Tension headache"],
            "symptoms": ["Headache", {"complaint": "Nausea"}],
            "notes": {"notes": ["Sensitive to light", "Poor sleep"]},
            "followup_notes": ["Review in 5 days"],
        }
    )

    assert payload["prakriti"] == "vata, pitta"
    assert payload["diagnosis"] == "Migraine, Tension headache"
    assert payload["symptoms"] == "Headache, Nausea"
    assert payload["notes"] == "Sensitive to light, Poor sleep"
    assert payload["followup_notes"] == "Review in 5 days"


async def test_ai_prescription_endpoint_routes_mode_override(
    authenticated_client,
    db_session,
    doctor_for_credentials,
    monkeypatch,
):
    client = authenticated_client["client"]
    doctor = doctor_for_credentials(authenticated_client["username"])

    patient = Patient(
        doctor_id=doctor.id,
        name="Endpoint Patient",
        age=40,
        gender="female",
        phone="9990004567",
        email="endpoint@example.com",
        address="Delhi",
    )
    db_session.add(patient)
    commit_with_retry(db_session)

    case = CaseSheet(
        patient_id=patient.id,
        diagnosis="Migraine",
        symptoms="{'complaint': 'Migraine', 'duration': None}",
        notes="Normal exam",
    )
    db_session.add(case)
    commit_with_retry(db_session)

    async def _fake_role_based(case_data: dict[str, object], mode: str) -> dict[str, object]:
        return {
            "success": True,
            "prescription": f"Generated in {mode} mode",
            "mode": mode,
            "references": [],
        }

    monkeypatch.setattr(ai_router, "generate_role_based_prescription", _fake_role_based)

    analyzer_page = await client.get("/ai-analyzer")
    csrf_token = extract_csrf_token(analyzer_page.text)

    response = await client.post(
        f"/api/ai/prescription/{case.id}?mode=modern",
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "modern"
    assert "Generated in modern mode" in response.json()["prescription"]


async def test_ai_medicine_info_endpoint_returns_ai_details(authenticated_client, monkeypatch):
    client = authenticated_client["client"]

    async def _fake_medicine_info(medicine_name: str, context: dict[str, object] | None = None) -> dict[str, object]:
        assert medicine_name == "Paracetamol"
        return {
            "medicine_name": "Paracetamol",
            "benefits": ["Reduces fever", "Relieves pain"],
            "side_effects": {
                "common": ["Nausea"],
                "serious": ["Liver injury with overdose"],
                "management": "Use only as directed.",
            },
            "alternatives": [{"name": "Dolo 650", "why_recommended": "Similar composition", "estimated_savings": "Save Rs 8"}],
            "dosage": {
                "standard": "500 mg every 6 hours if needed",
                "max_daily": "4 g per day",
                "timing": "After meals",
                "food_instruction": "optional",
            },
            "precautions": ["Avoid overdose"],
            "interactions": ["Check other paracetamol products"],
            "what_to_do_if_missed": "Take when remembered unless close to the next dose.",
            "when_to_consult_doctor": "If fever persists or symptoms worsen.",
            "ai_confidence_percent": 91,
            "provider": "gemini",
            "source": "ai",
        }

    monkeypatch.setattr("services.medicine_info_ai.get_medicine_info_pure_ai", _fake_medicine_info)

    analyzer_page = await client.get("/ai-analyzer")
    csrf_token = extract_csrf_token(analyzer_page.text)

    response = await client.post(
        "/api/ai/medicine-info/pure",
        json={"medicine_name": "Paracetamol", "diagnosis": "Fever", "symptoms": "High fever"},
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["source"] == "ai"
    assert payload["data"]["benefits"]
    assert payload["data"]["alternatives"][0]["name"] == "Dolo 650"


async def test_ai_prescription_enhance_endpoint_returns_detailed_medicines(authenticated_client, monkeypatch):
    client = authenticated_client["client"]

    async def _fake_enhance(payload: dict[str, object]) -> dict[str, object]:
        return {
            **payload,
            "medicines": [
                {
                    "name": "Paracetamol",
                    "dosage": "500 mg",
                    "detailed_info": {
                        "benefits": ["Reduces fever"],
                        "side_effects": {"common": ["Nausea"], "serious": ["Overdose risk"], "management": "Take after meals."},
                        "alternatives": [{"name": "Dolo 650", "why_recommended": "Same active medicine", "estimated_savings": "Save Rs 8"}],
                        "dosage": {"standard": "500 mg", "max_daily": "4 g", "timing": "After meals", "food_instruction": "optional"},
                        "precautions": ["Avoid overdose"],
                        "interactions": ["Avoid duplicate paracetamol combinations"],
                        "what_to_do_if_missed": "Take when remembered unless close to the next dose.",
                        "when_to_consult_doctor": "If fever continues beyond 3 days.",
                        "ai_confidence_percent": 88,
                    },
                }
            ],
            "ai_generated": True,
            "source": "ai",
        }

    monkeypatch.setattr("services.medicine_info_ai.get_prescription_with_details", _fake_enhance)

    analyzer_page = await client.get("/ai-analyzer")
    csrf_token = extract_csrf_token(analyzer_page.text)

    response = await client.post(
        "/api/ai/prescription/enhance",
        json={"medicines": [{"name": "Paracetamol"}], "diagnosis": "Fever"},
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ai_generated"] is True
    assert payload["medicines"][0]["detailed_info"]["benefits"] == ["Reduces fever"]
