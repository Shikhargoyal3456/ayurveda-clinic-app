# Hospital Admission feature report

## Files created

- `app/routers/hospital_admission.py`
- `scripts/seed_hospitals.py`
- `templates/hospital/list.html`
- `templates/hospital/admission.html`
- `hospital_feature_audit.txt`
- `hospital_feature_report.md`

## Files modified

- `app/models/core.py` — added `Hospital` and `HospitalAdmission` with `extend_existing`.
- `app/models/__init__.py` — exported the new models.
- `app/database.py` — registered models in `init_db()` and added an additive compatibility step for the legacy admissions table’s missing `emergency` column.
- `app/main.py` — registered the router.

## Feature behavior

- `GET /hospital/list`, `GET /hospital/admission`, and `GET /hospital/api/hospitals` list current hospital/bed data.
- Admission creation verifies the patient and hospital, requires a signed-in doctor/admin, reserves a bed with a conditional atomic update, and creates the pending admission in the same transaction.
- Clinicians can only create requests for their own patients and read/update their own admissions. Admins can manage all admissions.
- Status updates support pending, admitted, discharged, and cancelled. Pending/admitted requests release their reserved bed exactly once when discharged or cancelled. Terminal admissions cannot be reopened.
- A WhatsApp link is returned when the patient has a phone number. It opens a prefilled message; it does not send one automatically.
- Hospital list remains public. Admission mutations and admission detail/status endpoints require an authenticated doctor/admin.
- The seed script inserts the five requested sample records when missing and leaves existing bed counts untouched.

## Confirmed tests

Tests ran with the available Python 3.13.12 runtime because the project `.venv` points to an inaccessible Python executable.

| Request | Result |
|---|---|
| `GET /hospital/list` | 200 HTML |
| `GET /hospital/admission` | 200 HTML |
| `GET /hospital/api/hospitals` | 200 JSON; five hospitals |
| Anonymous `POST /hospital/api/admission/request` | 401 |
| Authenticated admin `POST /hospital/api/admission/request` | 200; returned admission ID and WhatsApp link |
| `GET /hospital/api/admission/{id}` | 200; pending status |
| `PUT /hospital/api/admission/{id}` with `admitted` | 200 |
| `PUT /hospital/api/admission/{id}` with `discharged` | 200 |
| Repeated discharged update | 200; no second bed release |
| Request without a reason | 422 |

Bed count verified: 44 → 43 when the admission was requested, then 43 → 44 on discharge. The end-to-end test passed. `init_db()` completed and added the missing compatibility column. Seed rerun reported zero inserted because all five hospital name/city records already existed.

The legacy admissions table also required explicit `doctor_id`, `created_at`, and `updated_at` values. New requests associate an omitted doctor with the patient’s doctor and set timestamps explicitly. No legacy rows were deleted or reset.

## Sample curl commands

Use a valid signed-in doctor/admin session cookie in `cookies.txt`. Include the CSRF token from the authenticated page for POST/PUT requests.

```sh
curl -b cookies.txt http://127.0.0.1:8000/hospital/list
curl -b cookies.txt http://127.0.0.1:8000/hospital/admission
curl -b cookies.txt http://127.0.0.1:8000/hospital/api/hospitals

curl -b cookies.txt -H "Content-Type: application/json" -H "X-CSRF-Token: YOUR_CSRF_TOKEN" \
  -d '{"patient_id":1,"hospital_id":1,"reason":"Requires inpatient observation","diagnosis":"Clinical diagnosis","emergency":false}' \
  http://127.0.0.1:8000/hospital/api/admission/request

curl -b cookies.txt http://127.0.0.1:8000/hospital/api/admission/ADMISSION_ID
curl -b cookies.txt -X PUT -H "Content-Type: application/json" -H "X-CSRF-Token: YOUR_CSRF_TOKEN" \
  -d '{"status":"admitted"}' http://127.0.0.1:8000/hospital/api/admission/ADMISSION_ID
curl -b cookies.txt -X PUT -H "Content-Type: application/json" -H "X-CSRF-Token: YOUR_CSRF_TOKEN" \
  -d '{"status":"discharged"}' http://127.0.0.1:8000/hospital/api/admission/ADMISSION_ID
```

## Remaining notes

- Existing passlib/bcrypt version warnings still appear during app initialization; they did not prevent startup or feature requests.
- Browser automation was not available; the template pages rendered successfully and the admission form is wired to the API.
- The `.venv` should be repaired separately to use the repository’s intended environment. Verification used the existing external Python 3.13 runtime.
- The existing tables were created by legacy code not present in the repository. The compatibility helper adds only `hospital_admissions.emergency`; the legacy schema and rows otherwise remain intact.
