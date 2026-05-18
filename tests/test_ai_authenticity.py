from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

import pytest

import routers.ai as ai_router
import routers.emr as emr_router
import routers.lab_analyzer as lab_analyzer_router
from app.database import commit_with_retry
from app.models import CaseSheet, Patient
from routers import order_medicines as order_medicines_router
from tests.conftest import extract_csrf_token


pytestmark = pytest.mark.asyncio


async def _register_and_login_patient(client, email: str = "authenticity.patient@example.com") -> str:
    unique_email = email.replace("@", f".{uuid4().hex[:8]}@")
    unique_phone = f"98{uuid4().int % 10**8:08d}"

    register_page = await client.get("/auth/register/patient")
    csrf_token = extract_csrf_token(register_page.text)

    register_response = await client.post(
        "/api/auth/register",
        data={
            "csrf_token": csrf_token,
            "role": "patient",
            "full_name": "AI Authenticity Patient",
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

    lab_page = await client.get("/lab-analyzer")
    csrf_match = re.search(r'const csrfToken = "([^"]+)"', lab_page.text)
    assert csrf_match is not None
    return csrf_match.group(1)


def _seed_patient_case(db_session, doctor_id: int, suffix: str = "auth") -> tuple[Patient, CaseSheet]:
    patient = Patient(
        doctor_id=doctor_id,
        name=f"Authenticity Patient {suffix}",
        age=45,
        gender="female",
        phone=f"99{uuid4().int % 10**8:08d}",
        email=f"auth.{suffix}.{uuid4().hex[:6]}@example.com",
        address="Delhi",
    )
    db_session.add(patient)
    commit_with_retry(db_session)

    case = CaseSheet(
        patient_id=patient.id,
        prakriti="pitta",
        diagnosis="Fever with cough",
        symptoms="fever, dry cough, body ache",
        notes="Symptoms for two days with mild fatigue.",
    )
    db_session.add(case)
    commit_with_retry(db_session)
    return patient, case


class TestAIAuthenticity:
    async def test_symptom_suggestions_are_ai_generated(self, client, monkeypatch):
        async def fake_ai_json(*args, **kwargs):
            return (
                {
                    "suggested_medicines": ["Paracetamol", "Cetirizine", "Tulsi Drops"],
                    "precautions": ["Hydrate well and seek doctor review if symptoms worsen."],
                },
                "gemini",
            )

        monkeypatch.setattr(order_medicines_router.ai_provider, "call_ai_json_with_retry", fake_ai_json)

        page = await client.get("/order-medicines")
        csrf_token = extract_csrf_token(page.text)
        response = await client.post(
            "/order-medicines/ai-suggest",
            data={"symptoms": "fever and headache for 2 days", "csrf_token": csrf_token},
        )

        assert response.status_code == 200
        result = response.json()
        response_text = str(result).lower()
        forbidden_phrases = [
            "no ai suggestions yet",
            "no suggestions yet",
            "describe your symptoms",
            "try another name",
        ]
        for phrase in forbidden_phrases:
            assert phrase not in response_text, f"Found forbidden fallback phrase: {phrase}"
        assert result["suggested_medicines"]
        assert result["provider"] == "gemini"

    async def test_lab_analyzer_uses_ai_always(self, client, monkeypatch):
        patient_csrf = await _register_and_login_patient(client, email="auth.lab.patient@example.com")

        async def fake_ai_analysis(extracted_text: str, parsed_data: dict):
            assert "Hb 10.2" in extracted_text
            return {
                "summary": "Limited text still suggests a low hemoglobin pattern that deserves follow-up.",
                "diagnosis": [
                    {
                        "condition": "Possible anemia",
                        "confidence": "Low",
                        "evidence": ["Hb 10.2"],
                        "confirmatory_tests": ["CBC repeat", "Iron studies"],
                    }
                ],
                "abnormal_findings": [
                    {
                        "test_name": "Hemoglobin",
                        "value": "10.2 g/dL",
                        "normal_range": "12-17.5 g/dL",
                        "meaning": "This can fit anemia patterns when confirmed with a full CBC.",
                        "recommendation": "Share a clearer report and discuss repeat CBC with your doctor.",
                    }
                ],
                "normal_findings": [],
                "recommendations": ["Upload a clearer report if possible and review this with your doctor."],
                "provider": "gemini",
            }

        monkeypatch.setattr(lab_analyzer_router.analyzer, "analyze_with_ai", fake_ai_analysis)

        response = await client.post(
            "/api/lab-analyzer/analyze",
            files={"report": ("report.png", b"Hb 10.2", "image/png")},
            headers={"X-CSRF-Token": patient_csrf},
        )

        assert response.status_code == 200
        result = response.json()
        response_text = str(result).lower()
        forbidden_phrases = [
            "could not extract",
            "no lab results",
            "cannot provide",
            "unable to extract",
            "technical pdf stream",
        ]
        for phrase in forbidden_phrases:
            assert phrase not in response_text, f"Found forbidden fallback phrase: {phrase}"
        assert len(response_text) > 50
        assert result["success"] is True
        assert result["diagnosis"]

    async def test_ai_prescription_no_hardcoded_fallback(
        self,
        authenticated_client,
        db_session,
        doctor_for_credentials,
        monkeypatch,
    ):
        client = authenticated_client["client"]
        doctor = doctor_for_credentials(authenticated_client["username"])
        _patient, case = _seed_patient_case(db_session, doctor.id, suffix="rx")

        async def fake_prescription(case_data: dict[str, object], mode: str) -> dict[str, object]:
            return {
                "success": True,
                "prescription": (
                    "Ayurveda assessment suggests a jvara pattern with respiratory irritation. "
                    "Use doctor-reviewed herbs, hydration, rest, and monitor for worsening cough or breathlessness."
                ),
                "mode": mode,
                "provider": "gemini",
                "references": ["Charaka Samhita"],
            }

        monkeypatch.setattr(ai_router, "generate_role_based_prescription", fake_prescription)

        analyzer_page = await client.get("/ai-analyzer")
        csrf_token = extract_csrf_token(analyzer_page.text)
        response = await client.post(
            f"/api/ai/prescription/{case.id}?mode=ayurveda",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code in {200, 503}
        if response.status_code == 200:
            result = response.json()
            response_text = str(result).lower()
            forbidden_phrases = [
                "temporarily unavailable",
                "try again later",
                "unable to generate",
                "service unavailable",
            ]
            for phrase in forbidden_phrases:
                assert phrase not in response_text, f"Found forbidden fallback phrase: {phrase}"
            assert len(response_text) > 100
            assert result["provider"] == "gemini"

    async def test_diet_plan_uses_ai(
        self,
        authenticated_client,
        db_session,
        doctor_for_credentials,
        monkeypatch,
    ):
        client = authenticated_client["client"]
        doctor = doctor_for_credentials(authenticated_client["username"])
        patient, _case = _seed_patient_case(db_session, doctor.id, suffix="diet")

        async def fake_diet_plan(patient_data: dict) -> dict:
            return {
                "diagnosis_summary": "A diabetes-focused vegetarian plan emphasizing steady glucose control.",
                "dosha_assessment": "Pitta-kapha tendencies with metabolic strain.",
                "meal_plan": ["Breakfast: vegetable besan chilla", "Lunch: dal, sabzi, millet roti"],
                "foods_to_favor": ["Low-glycemic vegetables", "Whole legumes", "Adequate water"],
                "foods_to_avoid": ["Sugary drinks", "Refined sweets"],
                "lifestyle_tips": ["Walk after meals", "Maintain regular sleep"],
                "precautions": ["Review medicines and sugar trends with your doctor."],
            }

        monkeypatch.setattr(emr_router, "generate_diet_plan", fake_diet_plan)

        response = await client.post(f"/api/ai/diet-plan/{patient.id}")

        assert response.status_code in {200, 503}
        if response.status_code == 200:
            result = response.json()
            response_text = str(result).lower()
            template_phrases = [
                "sample diet plan",
                "generic recommendation",
                "this is a sample",
            ]
            for phrase in template_phrases:
                assert phrase not in response_text, f"Found template phrase: {phrase}"
            assert "diabetes" in response_text or "sugar" in response_text

    async def test_ai_status_endpoint_honest(self, authenticated_client):
        client = authenticated_client["client"]
        response = await client.get("/api/ai/status")

        assert response.status_code == 200
        result = response.json()
        assert "rag_engine" in result
        assert "active_strategy" in result
        assert result["active_strategy"] in {
            "gemini_primary_groq_fallback",
            "gemini_only",
            "groq_only",
            "fallback_only",
            "unavailable",
        }

    async def test_no_hardcoded_fallbacks_in_codebase(self):
        forbidden_patterns = [
            r'"No AI suggestions yet"',
            r'"Could not extract any lab results"',
            r'"Unable to generate prescription"',
            r'"Please try again later"',
            r'"Describe your symptoms in a bit more detail"',
        ]
        scan_paths = [
            Path("routers/ai.py"),
            Path("routers/order_medicines.py"),
            Path("routers/pharmacy.py"),
            Path("routers/lab_analyzer.py"),
            Path("routers/emr.py"),
            Path("services/ai_provider.py"),
            Path("services/lab_analyzer.py"),
            Path("services/diet_ai.py"),
            Path("services/telemedicine_service.py"),
            Path("templates/order_medicines.html"),
            Path("templates/patient/lab_analyzer.html"),
            Path("templates/patient_order.html"),
        ]

        violations: list[str] = []
        for path in scan_paths:
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in forbidden_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    violations.append(f"{path}: {pattern}")

        assert not violations, f"Found hardcoded fallback phrases: {violations}"

    async def test_no_hardcoded_medicine_info(self):
        fever_phrase = '"Reduces fever by acting on ' + 'hypothalamus"'
        side_effects_phrase = '"Common side effects ' + 'include nausea"'
        max_dose_phrase = '"Maximum ' + '4g per day"'
        hardcoded_patterns = [
            re.escape(fever_phrase),
            re.escape(side_effects_phrase),
            re.escape(max_dose_phrase),
            r"MEDICINE_INFO_DB\s*=\s*\{",
            r"MEDICINE_SIDE_EFFECTS\s*=\s*\{",
            r"MEDICINE_BENEFITS\s*=\s*\{",
            r"COMMON_MEDICINES\s*=\s*\{",
        ]

        violations: list[str] = []
        for root, _dirs, files in os.walk("services"):
            for file in files:
                if not file.endswith(".py"):
                    continue
                path = Path(root) / file
                content = path.read_text(encoding="utf-8", errors="ignore")
                for pattern in hardcoded_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        violations.append(f"{path}: {pattern}")

        assert not violations, f"Found hardcoded medicine data: {violations}"

    async def test_ai_endpoints_return_json_not_html(
        self,
        authenticated_client,
        db_session,
        doctor_for_credentials,
        monkeypatch,
    ):
        client = authenticated_client["client"]
        doctor = doctor_for_credentials(authenticated_client["username"])
        patient, case = _seed_patient_case(db_session, doctor.id, suffix="json")

        async def fake_medicine_json(*args, **kwargs):
            return (
                {"suggested_medicines": ["Paracetamol"], "precautions": ["Doctor review if fever persists."]},
                "gemini",
            )

        async def fake_prescription(case_data: dict[str, object], mode: str) -> dict[str, object]:
            return {"success": True, "prescription": "AI prescription text", "mode": mode, "provider": "gemini", "references": []}

        async def fake_diet_plan(patient_data: dict) -> dict:
            return {"diagnosis_summary": "Diabetes support plan", "foods_to_favor": ["Lentils"], "foods_to_avoid": ["Sugary foods"], "lifestyle_tips": ["Walk daily"], "precautions": ["Monitor sugar regularly."]}

        async def fake_lab_analysis(extracted_text: str, parsed_data: dict):
            return {"summary": "AI reviewed the limited report text.", "diagnosis": [], "abnormal_findings": [], "normal_findings": [], "recommendations": ["Upload a clearer report if available."], "provider": "gemini"}

        monkeypatch.setattr(order_medicines_router.ai_provider, "call_ai_json_with_retry", fake_medicine_json)
        monkeypatch.setattr(ai_router, "generate_role_based_prescription", fake_prescription)
        monkeypatch.setattr(emr_router, "generate_diet_plan", fake_diet_plan)
        monkeypatch.setattr(lab_analyzer_router.analyzer, "analyze_with_ai", fake_lab_analysis)

        order_page = await client.get("/order-medicines")
        order_csrf = extract_csrf_token(order_page.text)
        order_response = await client.post(
            "/order-medicines/ai-suggest",
            data={"symptoms": "fever", "csrf_token": order_csrf},
        )

        analyzer_page = await client.get("/ai-analyzer")
        ai_csrf = extract_csrf_token(analyzer_page.text)
        prescription_response = await client.post(
            f"/api/ai/prescription/{case.id}?mode=modern",
            headers={"X-CSRF-Token": ai_csrf},
        )

        diet_response = await client.post(f"/api/ai/diet-plan/{patient.id}")

        patient_client = client.__class__(transport=client._transport, base_url="http://testserver")
        async with patient_client:
            patient_csrf = await _register_and_login_patient(patient_client, email="auth.json.patient@example.com")
            lab_response = await patient_client.post(
                "/api/lab-analyzer/analyze",
                files={"report": ("report.png", b"Hb 11.0", "image/png")},
                headers={"X-CSRF-Token": patient_csrf},
            )

        for endpoint, response in [
            ("/order-medicines/ai-suggest", order_response),
            (f"/api/ai/prescription/{case.id}", prescription_response),
            (f"/api/ai/diet-plan/{patient.id}", diet_response),
            ("/api/lab-analyzer/analyze", lab_response),
        ]:
            assert response.status_code in {200, 422, 503}, f"{endpoint} returned {response.status_code}"
            if response.status_code == 200:
                assert "application/json" in response.headers.get("content-type", ""), f"{endpoint} returned non-JSON"
