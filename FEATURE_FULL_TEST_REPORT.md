# KASH AI Full Feature Test Report

## 1. Summary

- **Date:** 2026-10-15
- **Overall result:** All recorded routes passed after the health-card fix; zero final 500 responses.
- **HTTP requests recorded:** 97 across the comprehensive route sweep and post-fix regression checks (including repeated lifecycle checks).
- **AI endpoints tested:** 7
- **Templates audited:** 170
- **Final route table has zero 500s or transport errors:** True

The pre-fix health-card 500 is documented below and in `health_card_traceback.txt`; the same authenticated route returned 200 after the fix.

## 2. Route-by-route results

| Route | Method | Status | Notes |
|---|---:|---:|---|
| `/` | GET | 302 | No server error |
| `/new` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/auth/login` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/auth/signup` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/auth/logout` | GET | 303 | No server error |
| `/dashboard` | GET | 303 | Expected authentication redirect |
| `/new/doctor` | GET | 303 | Expected authentication redirect |
| `/new/patient` | GET | 303 | Expected authentication redirect |
| `/new/admin` | GET | 303 | Expected authentication redirect |
| `/consultation/voice` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/patients` | GET | 303 | Expected authentication redirect |
| `/appointments` | GET | 303 | Expected authentication redirect |
| `/followups` | GET | 303 | Expected authentication redirect |
| `/hospital/list` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/hospital/admission` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/hospital/api/hospitals` | GET | 200 | No server error; body: {"success":true,"hospitals":[{"id":1,"name":"Apollo Hospital","address":"123 Main Road, Near City Ce |
| `/emr/doctor-dashboard` | GET | 303 | Expected authentication redirect |
| `/emr/patient-registry` | GET | 303 | Expected authentication redirect |
| `/emr/lab-dashboard` | GET | 303 | Expected authentication redirect |
| `/feature-status` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/device-check` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/analytics` | GET | 401 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/payments/daily` | GET | 303 | Expected authentication redirect |
| `/api` | GET | 200 | No server error; body: {"message":"Kash AI API is running!","version":"1.0.0","status":"healthy","docs":"/docs"} |
| `/demo` | GET | 303 | No server error |
| `/new/profile` | GET | 303 | Expected authentication redirect |
| `/emergency-log` | GET | 303 | Expected authentication redirect |
| `/emergency-log/export` | GET | 303 | Expected authentication redirect |
| `/v2/dashboard` | GET | 303 | No server error |
| `/v2/patients` | GET | 303 | No server error |
| `/auth/signup` | POST | 303 | Expected authentication redirect |
| `/new/doctor` | GET | 303 | Expected authentication redirect |
| `/consultation/voice` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/patients` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/appointments` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/followups` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/hospital/list` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/hospital/admission` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/emr/doctor-dashboard` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/emr/patient-registry` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/emr/lab-dashboard` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/analytics` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/payments/daily` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/emergency-log` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/emergency-log/export` | GET | 200 | No server error; body: Date,Patient,Keyword,Severity,Action  |
| `/patient/16/health-passport` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/patient/{test_patient_id}/health-card` | GET | 200 | Authenticated post-fix retest passed; <!DOCTYPE html> Health Card |
| `/patient/{test_patient_id}/health-card/qr` | GET | 200 | Authenticated post-fix retest passed; image/svg+xml health card QR |
| `/hospital/api/admission/request` | POST | 200 | No server error; body: {"success":true,"message":"Admission request submitted.","admission_id":9,"status":"pending","remain |
| `/hospital/api/admission/9` | GET | 200 | No server error; body: {"success":true,"admission":{"id":9,"patient_id":16,"doctor_id":11,"hospital_id":1,"admission_type": |
| `/hospital/api/admission/9` | PUT | 200 | No server error; body: {"success":true,"status":"discharged","available_beds":44} |
| `/auth/logout` | GET | 303 | No server error |
| `/auth/login` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/auth/login` | POST | 303 | Expected authentication redirect |
| `/new/doctor` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/consultation/voice` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/patients` | GET | 303 | No server error |
| `/appointments` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/followups` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/hospital/list` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/emr/doctor-dashboard` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/emr/patient-registry` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/emr/lab-dashboard` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/analytics` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/payments/daily` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/emergency-log` | GET | 200 | No server error; body: <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width= |
| `/emergency-log/export` | GET | 200 | No server error; body: Date,Patient,Keyword,Severity,Action  |
| `/v2/dashboard` | GET | 303 | No server error |
| `/v2/patients` | GET | 303 | No server error |
| `/api/samhita/analyze` | POST | 200 | No server error; body: {"success":true,"analysis":{"summary":"**Ayurvedic Analysis for a 30‑year‑old male with 2‑day fever, |
| `/api/voice/extract` | POST | 200 | No server error; body: {"success":true,"extracted":{"patient_name":"Patient","age":null,"gender":"","symptoms":[],"duration |
| `/api/voice/transcribe` | POST | 200 | No server error; body: {"success":true,"transcript":"प्रफ़ब","model":"whisper-large-v3-turbo"} |
| `/api/ai-chat` | POST | 200 | No server error; body: {"response":"**Jwara (Fever) in Ayurveda**\n\n\| Aspect \| Ayurvedic View \|\n\|--------\|--------------- |
| `/api/predict-churn` | POST | 200 | No server error; body: {"success":true,"at_risk_patients":[{"patient_id":1,"patient_name":"Anaya Mehta","phone":"9876543210 |
| `/api/predict-churn` | GET | 200 | No server error; body: {"success":true,"at_risk_patients":[{"patient_id":1,"patient_name":"Anaya Mehta","phone":"9876543210 |
| `/api/tongue/analyze` | POST | 200 | No server error; body: {"success":true,"model":"groq","diagnosis":"The tongue shows dry, cracked coating, indicating a Vata |
| `/api/samhita/analyze` | POST | 303 | Expected authentication redirect |
| `/api/voice/extract` | POST | 200 | No server error; body: {"success":true,"extracted":{"patient_name":"Patient","age":null,"gender":"","symptoms":[],"duration |
| `/api/voice/transcribe` | POST | 200 | No server error; body: {"success":true,"transcript":"प्रफ़ब","model":"whisper-large-v3-turbo"} |
| `/api/ai-chat` | POST | 200 | No server error; body: {"response":"Hello! I’m Dr. Kash, your Ayurvedic assistant. How can I support you today with persona |
| `/api/tongue/analyze` | POST | 303 | Expected authentication redirect |
| `/api/predict-churn` | POST | 303 | Expected authentication redirect |
| `/hospital/api/admission/request` | POST | 401 | No server error; body: {"success":false,"error":"Sign in to manage hospital admissions.","detail":"Sign in to manage hospit |

## 3. AI endpoint results

| Endpoint | Status | Result |
|---|---:|---|
| `POST /api/samhita/analyze` | 200 | Pass: `rag_used=true`, five analysis sections populated, five RAG sources. Snippet: `{"success": true, "rag_used": true, "sections": {"dosha_analysis": true, "dietary_recommendations": true, "herbal_formulations": true, "lifestyle_regimen": true, "classical_reference": true}, "sources": ["Astanga-hrdayam…` |
| `POST /api/voice/extract` | 200 | Pass: extracted object has patient_name, age, gender, symptoms, and duration. Missing demographics remain empty rather than fabricated. Snippet: `{"success": true, "extracted": {"patient_name": "Patient", "age": null, "gender": "", "symptoms": [], "duration": ""}}` |
| `POST /api/voice/transcribe` | 200 | Pass: generated WAV accepted; endpoint returned a valid response without a 500. Snippet: `{"success": true, "transcript": "प्रफ़ब", "model": "whisper-large-v3-turbo"}` |
| `POST /api/ai-chat` | 200 | Pass: non-empty response and actions object. Snippet: `{"response": "**Jwara (Fever) in Ayurveda**\n\n\| Aspect \| Ayurvedic View \|\n\|--------\|----------------\|\n\| **Definition** \| “Jwara” is the Sanskrit term for fever, a sudden rise in body temperature due to an imbalance of the three doshas—Va…` |
| `POST /api/predict-churn` | 200 | Pass: patients array returned (19 entries). Snippet: `{"success": true, "patients_count": 19, "total_at_risk": 19}` |
| `POST /api/tongue/analyze` | 200 | Pass: dummy PNG analyzed and structured result returned. Snippet: `{"success": true, "model": "groq", "diagnosis": "The tongue shows dry, cracked coating, indicating a Vata‑Pitta imbalance with dryness.", "prakriti": "Vata-Pitta", "confidence": 0.7}` |

## 4. Hospital flow result

| Stage | Available beds | Result |
|---|---:|---|
| Initial | 44 | Baseline |
| After admission | 43 | Request returned HTTP 200 and reserved one bed |
| After discharge | 44 | Discharge returned HTTP 200 and released the bed |
| After repeat discharge | 44 | Returned HTTP 200; no additional bed change |

**Pass:** yes. Temporary admission and patient rows were removed after the test.

## 5. Navigation audit result

- **Templates checked:** 170
- **Internal targets checked:** 407
- **Broken internal links:** 0
- **External navigation links:** `https://wa.me/919350397175`, `https://wa.me/{{ order.patient_phone }}`
- External fonts and icons also load from Google Fonts and cdnjs.
- **Disabled OAuth target:** `/auth/google/complete-signup` remains in a dormant Google role-choice template; the Google OAuth router is intentionally not mounted per project configuration.
- **Primary controls inspected:** Voice recording controls call start/pause/stop/clear handlers; save, WhatsApp, and reset call their existing functions; Samhita analysis listener is attached. Hospital admission form submits to its API. Login form posts to the manual auth route. Signup page is a working role selector that continues to role registration. Dashboard action handlers are defined and bound. The voice page uses existing button IDs and has editable patient fields rather than a separate manual-fill button.

The machine-readable audit is in `navigation_report.txt`.

## 6. Authenticated flow result

- **Signup works:** yes (HTTP 303 to the doctor workspace; temporary doctor created and removed).
- **Manual login works:** yes (HTTP 303 to `/new/dashboard` after CSRF validation).
- **Dashboard loads:** yes, with expected role redirects to the doctor workspace.
- **Patient and clinician pages load:** yes; protected patient paths redirect by role where appropriate.
- **Health card fix verified:** yes (authenticated health-card page and QR endpoint returned 200).
- **Logout works:** yes (HTTP 303 to the login page).

See `authenticated_route_results.json` for per-route statuses.

## 7. Health-card fix

- **Original error:** `AttributeError: 'Settings' object has no attribute 'doctor_name'` while constructing the health-card template context in `health_card_page`.
- **Root cause:** the handler accessed an optional setting as a required attribute; the `Settings` instance does not define it.
- **Route and template:** `app/routers/patient_health_routes.py` handles `GET /patient/{patient_id}/health-card` and renders `templates/patients/health_card.html`.
- **File modified for the fix:** `app/routers/patient_health_routes.py`.
- **Fix:** use `getattr(settings, "doctor_name", "")`, then fall back to the doctor’s full name or username.
- **Verification:** authenticated `GET /patient/{test_patient_id}/health-card` returned HTTP 200; QR returned HTTP 200. The original traceback is saved in `health_card_traceback.txt`.

## 8. Files modified in this run

- `app/main.py` — registered the emergency log and patient health-card routers.
- `app/routers/ai_features.py` — added the requested Samhita `sources` response alias and POST churn alias.
- `app/routers/emergency_log.py` — added authenticated emergency log page and CSV export.
- `app/routers/emr.py` — added `/patients` route alias.
- `app/routers/hospital_admission.py` — resolved doctor portal identity to its legacy doctor record.
- `app/routers/new_frontend.py` — added `/new/profile` alias.
- `app/routers/patient_health_routes.py` — implemented health passport/card routes and fixed missing optional setting access.
- `app/routers/patients.py` — added `/demo` redirect alias.
- `app/routers/statistics.py` — added `/analytics` route alias.
- `app/routers/v2.py` — added redirects for legacy v2 navigation targets.
- `app/routers/voice_consultation.py` and `app/services/voice_ai.py` — removed fabricated voice-extraction defaults and kept absent fields empty.
- `app/routes/prescription.py` — implemented the prescription preview send handler.
- `templates/dashboard/superapp_dashboard.html`, `templates/doctor/complete_dashboard.html`, and `templates/patient/legacy_portal.html` — corrected links to existing destinations.
- `templates/prescriptions/history.html` and `templates/prescriptions/preview.html` — corrected preview, resend, and PDF actions.
- `feature_test_report.txt`, `authenticated_route_results.json`, `ai_endpoint_responses.json`, `navigation_report.txt` — refreshed test evidence.
- `health_card_traceback.txt` — saved the pre-fix traceback.
- `FEATURE_FULL_TEST_REPORT.md` — this final report.

## 9. Remaining issues

- No remaining broken internal navigation links or 500 responses were found in the tested routes.
- Google OAuth is intentionally disabled; its dormant role-choice template still contains a callback link, documented in the navigation audit.
- Automated click testing was not performed in a browser; button wiring was inspected from template event handlers and form actions.
- Startup logs include a nonfatal SQLAlchemy warning that the SQLite URL `cache` option is ignored; startup completes successfully.

## 10. Commands to run the app

```powershell
cd C:\Projects\ayurveda_project
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
