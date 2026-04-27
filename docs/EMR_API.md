# EMR API

## Authentication
- All endpoints assume the existing doctor session and CSRF/session middleware.
- API routes use the logged-in doctor context from `get_current_doctor`.

## Patient Management
- `GET /api/patients/search?q=&system=`
  - Returns filtered patient summaries with EMR profile data.
- `POST /api/patients/register`
  - Creates a patient and EMR profile.
- `GET /api/patients/{id}`
  - Returns full EMR patient detail.
- `PUT /api/patients/{id}`
  - Updates demographics and profile blocks.
- `GET /api/patients/{id}/timeline`
  - Returns merged appointment, case, consultation, and prescription timeline items.

## Consultations
- `POST /api/consultations/modern`
- `POST /api/consultations/ayurveda`
- `POST /api/consultations/integrated`
  - Example body:
```json
{
  "patient_id": 1,
  "status": "finalized",
  "title": "Integrated consultation",
  "chief_complaint": "Acidity and stress",
  "notes": {
    "subjective": "Burning after meals",
    "objective": "Mild epigastric tenderness",
    "assessment": "GERD with pitta aggravation",
    "plan": "Diet, medication, follow-up"
  },
  "vitals": {
    "bp_systolic": 124,
    "bp_diastolic": 82,
    "heart_rate": 76
  }
}
```
- `GET /api/consultations/{id}`
- `PUT /api/consultations/{id}`
- `GET /api/consultations/patient/{patient_id}`

## Prescriptions
- `POST /api/prescriptions/modern`
- `POST /api/prescriptions/ayurveda`
- `GET /api/prescriptions/{id}`
- `GET /api/prescriptions/patient/{patient_id}/active`
- `POST /api/prescriptions/{id}/refill`

## Diagnostics
- `POST /api/labs/order`
- `PUT /api/labs/result/{id}`
- `GET /api/labs/patient/{patient_id}`
- `POST /api/ayurveda/prakriti/assess`
- `POST /api/ayurveda/srotas/examine`

## Clinical Decisions
- `GET /api/interactions/check?drugs=Aspirin&herbs=Turmeric`
- `GET /api/icd11/search?q=diabetes`
- `POST /api/analytics/outcomes`

## Reports
- `GET /api/reports/clinical?from=2026-04-01&to=2026-04-27`
- `GET /api/reports/ayurveda/dosha_distribution`
- `GET /api/reports/financial/daily`
- `GET /api/audit/logs?patient=1`

## Appointments
- `GET /api/appointments/doctor/{doctor_id}/today`
- `POST /api/appointments/book`
- `PUT /api/appointments/{id}/status`

## Errors
- `404`: record not found or not accessible to the logged-in doctor
- `422`: validation error
- `500`: unexpected server error handled by the global FastAPI exception handler
