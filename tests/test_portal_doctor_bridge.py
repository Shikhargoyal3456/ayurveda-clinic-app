from __future__ import annotations

from uuid import uuid4

import pytest

from app.models import Doctor, Patient
from models.emr import EMRConsultation, EMRPrescription
from models.user import User

from tests.conftest import extract_csrf_token


@pytest.mark.asyncio
async def test_portal_doctor_login_provisions_legacy_session(client, db_session):
    unique_suffix = uuid4().hex[:8]
    doctor_email = f"portal-doctor-{unique_suffix}@example.com"
    doctor_phone = f"98{uuid4().int % 10**8:08d}"
    registration_number = f"DOC-PORTAL-{unique_suffix.upper()}"

    register_page = await client.get("/auth/register/doctor")
    assert register_page.status_code == 200
    register_token = extract_csrf_token(register_page.text)

    register_response = await client.post(
        "/api/auth/register",
        data={
            "full_name": "Portal Doctor",
            "email": doctor_email,
            "phone": doctor_phone,
            "password": "VerySecurePass123!",
            "role": "doctor",
            "specialization": "ayurveda",
            "qualification": "BAMS",
            "registration_number": registration_number,
            "experience_years": "5",
            "csrf_token": register_token,
        },
        headers={"X-CSRF-Token": register_token},
    )
    assert register_response.status_code == 200
    verification_token = register_response.json()["verification_token"]

    verify_response = await client.get(f"/auth/verify-email?token={verification_token}", follow_redirects=False)
    assert verify_response.status_code == 303

    login_page = await client.get("/auth/login/doctor")
    assert login_page.status_code == 200
    login_token = extract_csrf_token(login_page.text)

    login_response = await client.post(
        "/auth/login",
        data={
            "identifier": doctor_email,
            "password": "VerySecurePass123!",
            "role": "doctor",
            "csrf_token": login_token,
        },
        follow_redirects=False,
    )
    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/doctor/dashboard"

    legacy_doctor = db_session.query(Doctor).filter(Doctor.username == doctor_email).one()
    portal_user = db_session.query(User).filter(User.email == doctor_email).one()
    assert legacy_doctor.full_name == "Portal Doctor"
    assert portal_user.role.value == "doctor"

    registry_response = await client.get("/emr/patient-registry")
    assert registry_response.status_code == 200
    assert "Patient Registry" in registry_response.text

    appointments_response = await client.get("/appointments")
    assert appointments_response.status_code == 200


@pytest.mark.asyncio
async def test_portal_doctor_can_register_patient_in_emr(client, db_session):
    unique_suffix = uuid4().hex[:8]
    doctor_email = f"emr-doctor-{unique_suffix}@example.com"
    doctor_phone = f"98{uuid4().int % 10**8:08d}"
    registration_number = f"DOC-EMR-{unique_suffix.upper()}"

    register_page = await client.get("/auth/register/doctor")
    register_token = extract_csrf_token(register_page.text)

    register_response = await client.post(
        "/api/auth/register",
        data={
            "full_name": "EMR Doctor",
            "email": doctor_email,
            "phone": doctor_phone,
            "password": "VerySecurePass123!",
            "role": "doctor",
            "specialization": "ayurveda",
            "qualification": "BAMS",
            "registration_number": registration_number,
            "experience_years": "7",
            "csrf_token": register_token,
        },
        headers={"X-CSRF-Token": register_token},
    )
    verification_token = register_response.json()["verification_token"]
    await client.get(f"/auth/verify-email?token={verification_token}")

    login_page = await client.get("/auth/login/doctor")
    login_token = extract_csrf_token(login_page.text)
    await client.post(
        "/auth/login",
        data={
            "identifier": doctor_email,
            "password": "VerySecurePass123!",
            "role": "doctor",
            "csrf_token": login_token,
        },
    )

    patient_registration_page = await client.get("/emr/patient-registration")
    assert patient_registration_page.status_code == 200
    patient_token = extract_csrf_token(patient_registration_page.text)

    create_response = await client.post(
        "/emr/patient-registration",
        data={
            "first_name": "Asha",
            "last_name": "Sharma",
            "gender": "Female",
            "age": "32",
            "mobile": "9998887776",
            "email": "asha@example.com",
            "address": "Jaipur",
            "emergency_contact_name": "Ravi Sharma",
            "emergency_contact_number": "9998887775",
            "consent_privacy": "true",
            "consent_telemedicine": "true",
            "prakriti_type": "Vata-Pitta",
            "agni_type": "Vishama",
            "medical_conditions": "Acidity",
            "csrf_token": patient_token,
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 303
    assert create_response.headers["location"].startswith("/emr/patient/")

    patient = db_session.query(Patient).filter(Patient.email == "asha@example.com").one()
    assert patient.name == "Asha Sharma"
    assert patient.phone == "9998887776"


@pytest.mark.asyncio
async def test_doctor_dashboard_uses_logged_in_doctor_data(client, db_session):
    register_page = await client.get("/auth/register/doctor")
    register_token = extract_csrf_token(register_page.text)

    register_response = await client.post(
        "/api/auth/register",
        data={
            "full_name": "Dashboard Doctor",
            "email": "dashboard-doctor@example.com",
            "phone": "9876543212",
            "password": "VerySecurePass123!",
            "role": "doctor",
            "specialization": "ayurveda",
            "qualification": "BAMS",
            "csrf_token": register_token,
        },
    )
    verification_token = register_response.json()["verification_token"]
    await client.get(f"/auth/verify-email?token={verification_token}")

    login_page = await client.get("/auth/login/doctor")
    login_token = extract_csrf_token(login_page.text)
    await client.post(
        "/auth/login",
        data={
            "identifier": "dashboard-doctor@example.com",
            "password": "VerySecurePass123!",
            "role": "doctor",
            "csrf_token": login_token,
        },
    )

    patient_registration_page = await client.get("/emr/patient-registration")
    patient_token = extract_csrf_token(patient_registration_page.text)
    await client.post(
        "/emr/patient-registration",
        data={
            "first_name": "Neha",
            "last_name": "Kapoor",
            "gender": "Female",
            "age": "29",
            "mobile": "9998887774",
            "email": "neha@example.com",
            "address": "Delhi",
            "csrf_token": patient_token,
        },
    )

    dashboard_response = await client.get("/doctor/dashboard")
    assert dashboard_response.status_code == 200
    assert "Dashboard Doctor" in dashboard_response.text
    assert "Neha Kapoor" in dashboard_response.text
    assert "/emr/patient-registration" in dashboard_response.text


@pytest.mark.asyncio
async def test_emr_patient_detail_page_renders_for_logged_in_doctor(client, db_session):
    register_page = await client.get("/auth/register/doctor")
    register_token = extract_csrf_token(register_page.text)

    register_response = await client.post(
        "/api/auth/register",
        data={
            "full_name": "Patient Detail Doctor",
            "email": "patient-detail-doctor@example.com",
            "phone": "9876543215",
            "password": "VerySecurePass123!",
            "role": "doctor",
            "specialization": "ayurveda",
            "qualification": "BAMS",
            "csrf_token": register_token,
        },
    )
    verification_token = register_response.json()["verification_token"]
    await client.get(f"/auth/verify-email?token={verification_token}")

    login_page = await client.get("/auth/login/doctor")
    login_token = extract_csrf_token(login_page.text)
    await client.post(
        "/auth/login",
        data={
            "identifier": "patient-detail-doctor@example.com",
            "password": "VerySecurePass123!",
            "role": "doctor",
            "csrf_token": login_token,
        },
    )

    patient_registration_page = await client.get("/emr/patient-registration")
    patient_token = extract_csrf_token(patient_registration_page.text)
    create_response = await client.post(
        "/emr/patient-registration",
        data={
            "first_name": "Kiran",
            "last_name": "Joshi",
            "gender": "Male",
            "age": "41",
            "mobile": "9998887773",
            "email": "kiran@example.com",
            "address": "Pune",
            "csrf_token": patient_token,
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 303
    detail_url = create_response.headers["location"]

    detail_response = await client.get(detail_url)
    assert detail_response.status_code == 200
    assert "Kiran Joshi" in detail_response.text
    assert "Demographics & contact" in detail_response.text


@pytest.mark.asyncio
async def test_emr_test_page_buttons_open_real_workflows(client):
    register_page = await client.get("/auth/register/doctor")
    register_token = extract_csrf_token(register_page.text)

    register_response = await client.post(
        "/api/auth/register",
        data={
            "full_name": "EMR Test Doctor",
            "email": "emr-test-doctor@example.com",
            "phone": "9876543216",
            "password": "VerySecurePass123!",
            "role": "doctor",
            "specialization": "ayurveda",
            "qualification": "BAMS",
            "csrf_token": register_token,
        },
    )
    verification_token = register_response.json()["verification_token"]
    await client.get(f"/auth/verify-email?token={verification_token}")

    login_page = await client.get("/auth/login/doctor")
    login_token = extract_csrf_token(login_page.text)
    await client.post(
        "/auth/login",
        data={
            "identifier": "emr-test-doctor@example.com",
            "password": "VerySecurePass123!",
            "role": "doctor",
            "csrf_token": login_token,
        },
    )

    registration_redirect = await client.get("/emr/test-emr/registration", follow_redirects=False)
    assert registration_redirect.status_code == 303
    assert registration_redirect.headers["location"] == "/emr/patient-registration"

    soap_without_patient = await client.get("/emr/test-emr/soap", follow_redirects=False)
    assert soap_without_patient.status_code == 303
    assert soap_without_patient.headers["location"] == "/emr/patient-registration"

    patient_registration_page = await client.get("/emr/patient-registration")
    patient_token = extract_csrf_token(patient_registration_page.text)
    create_response = await client.post(
        "/emr/patient-registration",
        data={
            "first_name": "Aman",
            "last_name": "Verma",
            "gender": "Male",
            "age": "35",
            "mobile": "9998887772",
            "email": "aman@example.com",
            "address": "Noida",
            "csrf_token": patient_token,
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 303

    soap_with_patient = await client.get("/emr/test-emr/soap", follow_redirects=False)
    assert soap_with_patient.status_code == 303
    assert soap_with_patient.headers["location"].startswith("/emr/integrated-consultation/")

    prakriti_with_patient = await client.get("/emr/test-emr/prakriti", follow_redirects=False)
    assert prakriti_with_patient.status_code == 303
    assert prakriti_with_patient.headers["location"].startswith("/emr/ayurveda-consultation/")


@pytest.mark.asyncio
async def test_ayurveda_doctor_consultation_router_avoids_modern_only_page(client):
    register_page = await client.get("/auth/register/doctor")
    register_token = extract_csrf_token(register_page.text)

    register_response = await client.post(
        "/api/auth/register",
        data={
            "full_name": "Router Doctor",
            "email": "router-doctor@example.com",
            "phone": "9876543217",
            "password": "VerySecurePass123!",
            "role": "doctor",
            "specialization": "ayurveda",
            "qualification": "BAMS",
            "csrf_token": register_token,
        },
    )
    verification_token = register_response.json()["verification_token"]
    await client.get(f"/auth/verify-email?token={verification_token}")

    login_page = await client.get("/auth/login/doctor")
    login_token = extract_csrf_token(login_page.text)
    await client.post(
        "/auth/login",
        data={
            "identifier": "router-doctor@example.com",
            "password": "VerySecurePass123!",
            "role": "doctor",
            "csrf_token": login_token,
        },
    )

    patient_registration_page = await client.get("/emr/patient-registration")
    patient_token = extract_csrf_token(patient_registration_page.text)
    create_response = await client.post(
        "/emr/patient-registration",
        data={
            "first_name": "Ira",
            "last_name": "Menon",
            "gender": "Female",
            "age": "34",
            "mobile": "9998887771",
            "email": "ira@example.com",
            "address": "Bengaluru",
            "csrf_token": patient_token,
        },
        follow_redirects=False,
    )
    patient_id = int(create_response.headers["location"].rsplit("/", 1)[-1])

    router_response = await client.get(f"/emr/consultation/{patient_id}", follow_redirects=False)
    assert router_response.status_code == 303
    assert router_response.headers["location"] == f"/emr/ayurveda-consultation/{patient_id}"

    routed_page = await client.get(router_response.headers["location"])
    assert routed_page.status_code == 200
    assert "Ayurveda Consultation" in routed_page.text


@pytest.mark.asyncio
async def test_emr_patient_registration_redirects_existing_duplicate_instead_of_crashing(client):
    register_page = await client.get("/auth/register/doctor")
    register_token = extract_csrf_token(register_page.text)

    register_response = await client.post(
        "/api/auth/register",
        data={
            "full_name": "Duplicate Guard Doctor",
            "email": "duplicate-guard-doctor@example.com",
            "phone": "9876543218",
            "password": "VerySecurePass123!",
            "role": "doctor",
            "specialization": "ayurveda",
            "qualification": "BAMS",
            "csrf_token": register_token,
        },
    )
    verification_token = register_response.json()["verification_token"]
    await client.get(f"/auth/verify-email?token={verification_token}")

    login_page = await client.get("/auth/login/doctor")
    login_token = extract_csrf_token(login_page.text)
    await client.post(
        "/auth/login",
        data={
            "identifier": "duplicate-guard-doctor@example.com",
            "password": "VerySecurePass123!",
            "role": "doctor",
            "csrf_token": login_token,
        },
    )

    patient_registration_page = await client.get("/emr/patient-registration")
    patient_token = extract_csrf_token(patient_registration_page.text)
    first_create = await client.post(
        "/emr/patient-registration",
        data={
            "first_name": "Shikhar",
            "last_name": "Goyal",
            "gender": "male",
            "age": "53",
            "mobile": "+91 93503 97175",
            "email": "goyalshikhar67@gmail.com",
            "address": "Palwal",
            "csrf_token": patient_token,
        },
        follow_redirects=False,
    )
    assert first_create.status_code == 303
    first_location = first_create.headers["location"]

    second_registration_page = await client.get("/emr/patient-registration")
    second_token = extract_csrf_token(second_registration_page.text)
    second_create = await client.post(
        "/emr/patient-registration",
        data={
            "first_name": "Shikhar",
            "last_name": "Goyal",
            "gender": "male",
            "age": "53",
            "mobile": "+91 93503 97175",
            "email": "goyalshikhar67@gmail.com",
            "address": "Palwal",
            "csrf_token": second_token,
        },
        follow_redirects=False,
    )
    assert second_create.status_code == 303
    assert second_create.headers["location"] == first_location


@pytest.mark.asyncio
async def test_portal_doctor_can_download_generated_prescription_pdf(client):
    register_page = await client.get("/auth/register/doctor")
    register_token = extract_csrf_token(register_page.text)

    register_response = await client.post(
        "/api/auth/register",
        data={
            "full_name": "Prescription Doctor",
            "email": "prescription-doctor@example.com",
            "phone": "9876543213",
            "password": "VerySecurePass123!",
            "role": "doctor",
            "specialization": "ayurveda",
            "qualification": "BAMS",
            "csrf_token": register_token,
        },
    )
    verification_token = register_response.json()["verification_token"]
    await client.get(f"/auth/verify-email?token={verification_token}")

    login_page = await client.get("/auth/login/doctor")
    login_token = extract_csrf_token(login_page.text)
    await client.post(
        "/auth/login",
        data={
            "identifier": "prescription-doctor@example.com",
            "password": "VerySecurePass123!",
            "role": "doctor",
            "csrf_token": login_token,
        },
    )

    generate_response = await client.post(
        "/api/doctor/e-prescription/generate",
        json={
            "patient_name": "Portal Patient",
            "medicines": [
                {"name": "Paracetamol 500mg", "dosage": "500mg", "duration": "5 days", "instructions": "After food", "suggested_quantity": 10},
            ],
        },
    )
    assert generate_response.status_code == 200
    download_url = generate_response.json()["download_url"]

    pdf_response = await client.get(download_url)
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.headers["content-disposition"].startswith('attachment; filename="prescription-')


@pytest.mark.asyncio
async def test_portal_doctor_otp_login_bridges_emr_and_appointments(client):
    register_page = await client.get("/auth/register/doctor")
    register_token = extract_csrf_token(register_page.text)

    register_response = await client.post(
        "/api/auth/register",
        data={
            "full_name": "OTP Doctor",
            "email": "otp-doctor@example.com",
            "phone": "9876543214",
            "password": "VerySecurePass123!",
            "role": "doctor",
            "specialization": "ayurveda",
            "qualification": "BAMS",
            "csrf_token": register_token,
        },
    )
    verification_token = register_response.json()["verification_token"]
    await client.get(f"/auth/verify-email?token={verification_token}")

    login_page = await client.get("/auth/login/doctor")
    login_token = extract_csrf_token(login_page.text)

    otp_response = await client.post(
        "/api/auth/send-otp",
        json={"identifier": "otp-doctor@example.com", "role": "doctor"},
        headers={"X-CSRF-Token": login_token},
    )
    assert otp_response.status_code == 200
    otp_code = otp_response.json()["otp_preview"]

    verify_response = await client.post(
        "/api/auth/verify-otp",
        json={"identifier": "otp-doctor@example.com", "role": "doctor", "otp": otp_code},
        headers={"X-CSRF-Token": login_token},
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["redirect_url"] == "/doctor/dashboard"

    dashboard_response = await client.get("/doctor/dashboard")
    assert dashboard_response.status_code == 200
    assert "OTP Doctor" in dashboard_response.text

    appointments_response = await client.get("/appointments")
    assert appointments_response.status_code == 200

    registry_response = await client.get("/emr/patient-registry")
    assert registry_response.status_code == 200
    assert "Patient Registry" in registry_response.text


@pytest.mark.asyncio
async def test_portal_doctor_can_capture_and_save_ambient_emr_session(client, db_session):
    register_page = await client.get("/auth/register/doctor")
    register_token = extract_csrf_token(register_page.text)

    register_response = await client.post(
        "/api/auth/register",
        data={
            "full_name": "Ambient Doctor",
            "email": "ambient-doctor@example.com",
            "phone": "9876543220",
            "password": "VerySecurePass123!",
            "role": "doctor",
            "specialization": "ayurveda",
            "qualification": "BAMS",
            "csrf_token": register_token,
        },
    )
    verification_token = register_response.json()["verification_token"]
    await client.get(f"/auth/verify-email?token={verification_token}")

    login_page = await client.get("/auth/login/doctor")
    login_token = extract_csrf_token(login_page.text)
    await client.post(
        "/auth/login",
        data={
            "identifier": "ambient-doctor@example.com",
            "password": "VerySecurePass123!",
            "role": "doctor",
            "csrf_token": login_token,
        },
    )

    patient_registration_page = await client.get("/emr/patient-registration")
    patient_token = extract_csrf_token(patient_registration_page.text)
    create_response = await client.post(
        "/emr/patient-registration",
        data={
            "first_name": "Riya",
            "last_name": "Sharma",
            "gender": "Female",
            "age": "37",
            "mobile": "9998887769",
            "email": "riya@example.com",
            "address": "Gurugram",
            "csrf_token": patient_token,
        },
        follow_redirects=False,
    )
    patient_id = int(create_response.headers["location"].rsplit("/", 1)[-1])

    page_response = await client.get(f"/emr/ambient-scribe?patient_id={patient_id}")
    assert page_response.status_code == 200
    assert "Ambient EMR Scribe" in page_response.text

    start_response = await client.post("/api/ambient-emr/session/start", json={"patient_id": patient_id})
    assert start_response.status_code == 200
    session_id = start_response.json()["session_id"]

    segment_one = await client.post(
        "/api/ambient-emr/process-segment",
        data={
            "session_id": session_id,
            "speaker": "patient",
            "transcript_text": "My name is Riya Sharma. I am 37 years old female. I have fever and body ache for 3 days. I have history of hypertension and I am taking Amlodipine.",
        },
    )
    assert segment_one.status_code == 200
    extracted_one = segment_one.json()["extracted_data"]
    assert extracted_one["patient_name"] == "Riya Sharma"
    assert extracted_one["age"] == "37"

    segment_two = await client.post(
        "/api/ambient-emr/process-segment",
        data={
            "session_id": session_id,
            "speaker": "doctor",
            "transcript_text": "On examination temperature is 100 degree Fahrenheit. I think you have viral fever. Treatment plan is hydration, rest, and paracetamol 500 mg twice daily for 3 days.",
        },
    )
    assert segment_two.status_code == 200

    finalize_response = await client.post(f"/api/ambient-emr/session/{session_id}/finalize")
    assert finalize_response.status_code == 200
    finalized = finalize_response.json()["emr_data"]
    assert "viral fever" in finalized["diagnosis"].lower()

    save_response = await client.post(
        "/api/ambient-emr/save",
        json={
            "session_id": session_id,
            "patient_id": patient_id,
            "system_type": "ayurveda",
            "emr_data": {
                "prescription": [
                    {"name": "Paracetamol 500 mg", "dosage": "1 tablet", "frequency": "Twice daily", "duration": "3 days"}
                ]
            },
        },
    )
    assert save_response.status_code == 200
    payload = save_response.json()
    assert payload["success"] is True
    assert payload["redirect_url"] == f"/emr/patient/{patient_id}"

    consultation = (
        db_session.query(EMRConsultation)
        .filter(EMRConsultation.patient_id == patient_id, EMRConsultation.title == "Ambient AI Scribe Consultation")
        .one()
    )
    assert consultation.chief_complaint
    assert consultation.diagnosis_json

    prescription = db_session.query(EMRPrescription).filter(EMRPrescription.consultation_id == consultation.id).one()
    assert prescription.items_json[0]["name"] == "Paracetamol 500 mg"
