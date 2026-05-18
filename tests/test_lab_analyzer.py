from __future__ import annotations

import re
from uuid import uuid4

import pytest

from routers import lab_analyzer as lab_analyzer_router
from services.lab_analyzer import LabReportAnalyzer, clean_extracted_text
from tests.conftest import extract_csrf_token


pytestmark = pytest.mark.asyncio


async def _register_and_login_patient(client, email: str = "lab.patient@example.com"):
    unique_email = email.replace("@", f".{uuid4().hex[:8]}@")
    unique_phone = f"98{uuid4().int % 10**8:08d}"
    register_page = await client.get("/auth/register/patient")
    csrf_token = extract_csrf_token(register_page.text)

    register_response = await client.post(
        "/api/auth/register",
        data={
            "csrf_token": csrf_token,
            "role": "patient",
            "full_name": "Lab Analyzer Patient",
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
    assert login_response.headers["location"] == "/patient"
    return login_csrf


async def test_lab_analyzer_page_renders_for_patient(client):
    await _register_and_login_patient(client, email="lab.page.patient@example.com")

    response = await client.get("/lab-analyzer")
    assert response.status_code == 200
    assert "AI Lab Report Analyzer" in response.text
    assert "/api/lab-analyzer/analyze" in response.text


async def test_lab_analyzer_endpoint_returns_ai_error_when_provider_fails(client, monkeypatch):
    await _register_and_login_patient(client, email="lab.api.patient@example.com")
    analyzer_page = await client.get("/lab-analyzer")
    csrf_match = re.search(r'const csrfToken = "([^"]+)"', analyzer_page.text)
    assert csrf_match is not None
    login_csrf = csrf_match.group(1)

    async def fail_ai(*args, **kwargs):
        raise RuntimeError("AI provider unavailable")

    monkeypatch.setattr(lab_analyzer_router.analyzer, "analyze_with_ai", fail_ai)

    report_text = (
        "Hemoglobin 10.2\n"
        "WBC 12.5\n"
        "Platelets 250\n"
        "Creatinine 0.9\n"
        "Vitamin D 18\n"
    ).encode("utf-8")

    response = await client.post(
        "/api/lab-analyzer/analyze",
        files={"report": ("lab-report.png", report_text, "image/png")},
        headers={"X-CSRF-Token": login_csrf},
    )
    assert response.status_code == 503
    payload = response.json()
    assert payload["success"] is False
    assert payload["source"] == "ai_error"
    assert "AI provider unavailable" in payload["error"]


async def test_lab_analyzer_handles_pdf_binary_stream_text_with_ai_response(client):
    await _register_and_login_patient(client, email="lab.pdf.patient@example.com")
    analyzer_page = await client.get("/lab-analyzer")
    csrf_match = re.search(r'const csrfToken = "([^"]+)"', analyzer_page.text)
    assert csrf_match is not None
    login_csrf = csrf_match.group(1)

    fake_pdf_stream = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Length 44 >>\nstream\n"
        b"x\x9c+\xca\xcfMU(I-.\x01\x00\x12\x8b\x03\x1d\n"
        b"endstream\nendobj\n%%EOF"
    )

    response = await client.post(
        "/api/lab-analyzer/analyze",
        files={"report": ("lab-report.pdf", fake_pdf_stream, "application/pdf")},
        headers={"X-CSRF-Token": login_csrf},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "summary" in payload
    assert isinstance(payload.get("recommendations"), list)


async def test_lab_report_extractor_ignores_pdf_binary_stream_text():
    analyzer = LabReportAnalyzer()
    fake_pdf_stream = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Length 44 >>\nstream\n"
        b"x\x9c+\xca\xcfMU(I-.\x01\x00\x12\x8b\x03\x1d\n"
        b"endstream\nendobj\n%%EOF"
    )

    extracted = analyzer.extract_text_from_bytes(fake_pdf_stream, file_type="application/pdf")
    assert extracted == ""


async def test_lab_report_extractor_repairs_spaced_letter_ocr_output():
    analyzer = LabReportAnalyzer()

    extracted = analyzer._normalize_extracted_text("H e m o g l o b i n  10.2\nW B C  12.5\nP l a t e l e t s  250")

    assert "Hemoglobin 10.2" in extracted
    assert "WBC 12.5" in extracted
    assert "Platelets 250" in extracted


async def test_clean_extracted_text():
    cleaned = clean_extracted_text("H e l l o   w o r l d")
    assert cleaned == "Hello   world"

    punctuated = clean_extracted_text("This . . . is a test .")
    assert "..." in punctuated
    assert punctuated.endswith(".")


async def test_lab_analyzer_parses_sample_cbc_values():
    analyzer = LabReportAnalyzer()
    sample_text = """
Hemoglobin (Hb): 10.2 g/dL (Reference: 13.5-17.5)
RBC Count: 3.8 million (Reference: 4.5-5.9)
WBC Count: 11,500/uL (Reference: 4,000-11,000)
HCT: 32 %
MCV: 78
MCH: 24
MCHC: 30
Lymphocytes: 18 %
ESR: 35
"""

    parsed = await analyzer.parse_lab_values(sample_text)
    detected = {item["test_name"]: item["status"] for item in parsed["tests"]}

    assert detected["Hemoglobin"] == "low"
    assert detected["RBC"] == "low"
    assert detected["WBC"] == "high"
    assert detected["Hematocrit"] == "low"
    assert detected["MCV"] == "low"
    assert detected["MCH"] == "low"
    assert detected["MCHC"] == "low"
    assert detected["Lymphocytes"] == "low"
    assert detected["ESR"] == "high"


async def test_lab_analyzer_builds_fallback_diagnosis_patterns():
    analyzer = LabReportAnalyzer()
    sample_text = """
Hemoglobin (Hb): 10.2 g/dL
RBC Count: 3.8 million
WBC Count: 11,500/uL
MCV: 78
MCH: 24
ESR: 35
Vitamin D: 18
"""

    parsed = await analyzer.parse_lab_values(sample_text)
    analysis = analyzer.build_fallback_analysis(sample_text, parsed)

    diagnoses = {item["condition"]: item for item in analysis["diagnosis"]}
    assert "Iron Deficiency Anemia" in diagnoses
    assert diagnoses["Iron Deficiency Anemia"]["confidence"] == "High"
    assert diagnoses["Iron Deficiency Anemia"]["evidence"]
    assert "Inflammatory Response" in diagnoses
    assert "Vitamin D Deficiency" in diagnoses
