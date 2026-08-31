# Security Remediation Summary

**Date:** 2026-08-22
**Scope:** Semgrep findings (228 total) for the Ayurveda telemedicine / e-commerce app (FastAPI backend + JS/HTML frontend).
**Objective:** Close all live authorization / IDOR / data-exposure gaps and make the codebase production-ready.

---

## Verification status

- **Static:** every changed Python file passes `python3 -m py_compile`. All new import symbols were confirmed to exist in their target modules; dependency ordering and variable-shadowing were checked by hand.
- **Runtime tests:** could **not** be executed in the build sandbox — `fastapi`/`pytest` are not installed there and outbound PyPI access is blocked (proxy 403). **Recommended next step: run `pytest` in your local 3.14 venv** where the full dependency tree is available.

---

## Fixes applied this remediation

Each fix derives identity from the server-side session instead of trusting client-supplied `user_id` / `doctor_id` / `store_id`, or requires authentication where the endpoint was fully anonymous.

| Area | File | Change |
|------|------|--------|
| Storefront IDOR | `routers/ecommerce.py` | Added `_effective_user_id(request)` (session-scoped identity) and `_require_order_owner(...)`; ~18 endpoints rewritten to stop trusting client `user_id`. Order track / location / cancel / reschedule and the tracking page are now ownership-checked. |
| Subscriptions | `routers/subscriptions.py` | Auth added to create (patient/admin; patient forced to own id), get-by-user (403 unless owner/admin), trigger-refill (admin only). Webhook already HMAC-SHA256 verified. |
| Subresource integrity | `shared/templates/layouts/portal_base.html` | Added SRI `integrity=` to the Font Awesome CDN link. |
| Debug PII leak | `routers/debug.py` | `/debug/session` (dumped full session + user email/phone/name/role anonymously) now requires `require_portal_roles("admin")` and returns 404 in production. |
| Appointment IDOR | `routers/pure_ai.py` | `/reschedule-appointment/{id}` now requires `get_current_doctor` + ownership check (`patient.doctor_id == doctor.id`). Was optional-auth, leaking appointment details and the doctor's 14-day schedule. |
| Clinical AI leaks | `routers/ai_features.py` | 7 endpoints gated with `get_current_doctor`: samhita/analyze, tongue-analyze, voice-to-action, predict-churn, generate-billing-codes, recommend-medicines, telemedicine/start. `doctor_id` now bound server-side. (Was leaking all patients' name/phone/email and other patients' outcomes.) |
| Public API v1 | `apps/api/routes.py` | Full rewrite: patient/orders → patient/admin (scoped to `user:{id}`); pharmacy inventory/orders/analytics → pharmacy_owner/admin with `_store_id_for_owner` that **ignores client `store_id`** (kills cross-tenant IDOR); doctor/consultations → `get_current_doctor` (also fixed a pre-existing dict-attribute bug); lab/tests → lab_owner/admin. |
| Telemedicine | `routers/telemedicine.py` | Added `require_authenticated_user` dependency on 8 endpoints that leaked consultation data or acted on arbitrary ids: room/{id}, summary/{id} page, create-session, ai-assist, summary (POST body + /{id}), order/process/{id}, refill/remind/{user_id}. |

### Deliberately left public (reviewed, low risk)

Generic AI transforms that operate only on client-supplied input and read no cross-user records: `pure-ai` medicine-info / prescription / schedule-followup; `ai_features` tongue-health-check / ai-chat / voice/extract; `telemedicine` analyze-symptoms / fraud-check / support-respond / route-ticket / medicine-alternatives / delivery-optimize; `api/v1` delivery/assignments (mock), notifications (used by the frontend), search.

---

## Findings that required no change

- **Logger "token" findings** (`google_auth.py:172`, `cases.py:482`, `pharmacy.py:516`) are false positives. The first logs an `OAuthError` from a **failed** token exchange (no token exists), the second logs a `BadSignature` ("Signature does not match", not the token value), and the third is in a **dead** router. The global `RedactingFormatter` (`app/logging_config.py`) additionally redacts secrets in both messages and exception tracebacks.
- **Already remediated by prior work** (verified by reading current code): SQL injection (parameterized + table allowlist), path traversal (resolve-within-base + token filenames), tainted redirects (`is_safe_relative_redirect`), CSRF (middleware + token verify), XSS (`tojson|safe`), pickle/eval/exec (none present), SHA-pinned GitHub Actions.

## Dead code (not mounted — findings are moot)

The following routers are commented out in `app/main.py` and therefore unreachable: `pharmacy.py`, `startup.py`, `pharmacy_owner`, `pharmacy_portal`, `ai_pharmacy`.

---

## Residual items needing a product decision

These are pre-existing design limitations, **not** defects introduced here, and were left unchanged to avoid scope creep / behavioral risk:

1. **`services/marketplace_service.py` → `patient_portal_payload()`** returns the globally-latest patient / appointments / deliveries rather than strictly the caller's records. The consuming endpoint is now authenticated, but the data scoping inside the demo service is coarse. Wiring true per-user scoping requires threading the authenticated user id through this service.
2. **Telemedicine has no participant-ownership model.** A `session_id` currently acts as a capability token. The fixes block **anonymous** access, but do not stop one authenticated user from reading another's session by guessing a `session_id`. Full participant checks require the session → patient/doctor mapping in `services/telemedicine_service.py`.

## Auth-model rationale

Doctor-facing endpoints use legacy `get_current_doctor` (matching the EMR module, since doctors authenticate via a `doctor_id` session). Pharmacy / lab / patient endpoints use `require_portal_roles(...)` (matching how those roles log in). Telemedicine uses `get_current_user` (accepts any authenticated portal **or** legacy user, since both patients and doctors join consults). This avoids locking out legitimate users of either auth system.
