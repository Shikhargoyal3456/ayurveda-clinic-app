# Google OAuth Removal Report

**Project:** `C:\Projects\ayurveda_project`  
**Date:** 2026-10-15

## Result

Google OAuth login/signup is disabled. The Google router is no longer registered, Google CTAs were removed from login and signup pages, and the manual email/password account flow remains functional. Existing OAuth configuration and model/schema references were retained as requested.

## Files modified for this task

- `app/main.py` — commented out the Google OAuth router import and registration; the lines remain as comments.
- `app/middleware/csrf.py` — removed exemptions that applied only to the disabled OAuth routes.
- `app/routers/auth.py` — removed the Google CTA from generated legacy login markup and added `/auth/signup` as a route alias to the existing manual signup handler. Signup validation and account creation logic were not changed.
- `templates/auth/login.html`, `templates/auth/signup.html`, `templates/auth/portal_register.html`, `templates/login.html`, `templates/signup.html`, `templates/new_login.html`, and `templates/new_signup.html` — removed Google login/signup links, related script wiring, and OAuth-only button styles.
- `google_auth_audit.txt` — records the source references and endpoints found during the audit without including secret values.
- `google_auth_removal_report.txt` — records route and manual-auth verification results.
- `GOOGLE_AUTH_REMOVAL_REPORT.md` — this report.

## Files and data intentionally left intact

- `app/routers/google_auth.py` remains on disk, but its router is not registered by `app.main`.
- `templates/auth/google_choose_role.html` remains on disk and is unreachable because its router is disabled.
- `app/config.py` and `.env` retain Google OAuth settings/keys for a possible future re-enable. Secret values were not included in the audit or report.
- `app/models/user.py` retains `User.google_id`; `app/database.py` retains its compatibility reference. No database schema or OAuth model fields were removed.
- Hospital, AI provider, RAG, and Samhita implementation files were not modified for this task.

## Verification

- Python compile and `import app.main`: passed.
- Fresh Uvicorn startup on `127.0.0.1:8000`: completed successfully.
- Live server: `GET /auth/login` → 200, no Google CTA; `GET /auth/signup` → 200, no Google CTA; `GET /auth/google/login` → 404.
- Google route checks: `GET /auth/google/login`, `/callback`, and `/choose-role` returned 404; `POST /auth/google/complete-signup` returned 404.
- Manual login: `POST /auth/login` with a temporary verified email/password account returned 303 to `/dashboard` and set a session cookie.
- Manual signup: `POST /auth/signup` returned 303 to `/new/doctor` and set a session cookie. This URL is an alias to the existing manual signup handler; the handler logic was preserved.
- Logout: `GET /auth/logout` returned 303 to `/` and cleared the session.
- Temporary user and doctor records created for the auth checks were removed.

### Unaffected route sweep

| Route | Result |
|---|---|
| `GET /new` | 200 |
| `GET /dashboard` | 303, expected authentication redirect |
| `GET /new/doctor` | 303, expected authentication redirect |
| `GET /consultation/voice` | 200 |
| `GET /hospital/list` | 200 |
| `GET /hospital/admission` | 200 |
| `GET /hospital/api/hospitals` | 200, 5 hospitals |
| `GET /api` | 200 |
| `POST /api/samhita/analyze` | 303, expected doctor authentication redirect |
| `POST /api/voice/extract` | 200 |
| `POST /api/ai-chat` | 200 |

No HTTP 500 responses occurred in the listed checks.

## Remaining Google references

OAuth-specific route implementation, dormant settings, environment keys, the `google_id` model/schema compatibility code, and the unreachable Google role-selection template remain intentionally. Google provider font URLs are unrelated to OAuth. See `google_auth_audit.txt` for the detailed audit.
