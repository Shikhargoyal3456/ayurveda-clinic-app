# KASH AI audit and fix report

## Summary of issues found

- The project `.venv` points to an inaccessible Python 3.14 executable. The app was diagnosable using the existing Python 3.13 runtime at `C:\Users\goyal\AppData\Local\ayurveda-runtime\Scripts\python.exe`.
- The Samhita route already called the shared AI provider chain and had a mock fallback, but model responses could leave required sections empty, and malformed optional patient/consultation IDs could raise an exception. Its existing doctor-session requirement redirects unauthenticated callers.
- The voice consultation page had a results container but used a different button ID and lacked the analysis/render functions.
- The active voice extraction route passed an async Groq coroutine through a synchronous helper without awaiting it, causing an unhandled coroutine warning.
- Google OAuth callback did not copy the returned state query parameter into the session before token exchange.
- The requested hospital routes, model, and seed script are absent. Hospital/admission behavior has no existing schema or business rules to preserve.
- Runtime startup logs a passlib/bcrypt version warning. It does not stop startup.

## Fixes applied

- Completed missing Samhita analysis fields with existing local fallback content and tolerated invalid optional IDs.
- Wired the Samhita button, request/loading/error handling, and result rendering in the voice consultation template.
- Made voice case-sheet structuring asynchronous, awaited Groq correctly, and moved synchronous Gemini work to a thread.
- Added the requested Google OAuth state handoff before token exchange.
- Did not create hospital schema, records, or admission policy because the repository contains no hospital data model or policy to ground those changes.

## Files modified

- `app/routers/ai_features.py`
- `app/routers/google_auth.py`
- `app/routers/voice_consultation.py`
- `app/services/voice_ai.py`
- `templates/consultation/voice_consultation.html`

## Verification and remaining issues

The app imported with 625 routes and started on localhost. Database startup reported schema version 2 already compatible. No 500 response occurred in the requested route pass.

- `/new`, `/auth/login`, `/auth/signup`, `/consultation/voice`, and `/api`: 200.
- `/dashboard` and `/new/doctor`: 303 to login because the test had no authenticated session. This is the current access-control behavior.
- `/api/samhita/analyze`: 303 to login for the same doctor-session requirement. A successful persisted analysis was not verified without a doctor session.
- `/api/voice/extract` and `/api/ai-chat`: 200 with fallback content. Groq outbound access failed in this environment (WinError 10013); API availability is not proven.
- `/api/voice/transcribe`: 422 because the diagnostic request intentionally did not contain an audio file.
- `/hospital/list`, `/hospital/admission`, `/api/hospitals`, `/api/admission/request`: 404; routes do not exist.
- Google OAuth state handoff was implemented, but completing a real Google redirect/token exchange was not possible in the localhost check.
- Browser console automation was unavailable. The voice page returned 200 and the required IDs/functions/listener are present in the template.
- `.env` keys present: GROQ, SECRET, DATABASE_URL, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET. GEMINI and OPENAI keys are missing. Values were not copied to either report.
- Full runtime verification through the repository `.venv` remains unavailable until its Python interpreter is repaired. A system Python 3.13 environment was used for this pass.

Full route statuses and startup notes are in `diagnostic_report.txt`.

## Test URLs and expected results

| Method | URL | Expected result |
|---|---|---|
| GET | `http://127.0.0.1:8000/new` | 200 |
| GET | `http://127.0.0.1:8000/auth/login` | 200 |
| GET | `http://127.0.0.1:8000/auth/signup` | 200 |
| GET | `http://127.0.0.1:8000/dashboard` | 200 with an authenticated user; 303 to login when anonymous |
| GET | `http://127.0.0.1:8000/new/doctor` | 200 with an authenticated doctor; 303 to login when anonymous |
| GET | `http://127.0.0.1:8000/consultation/voice` | 200 |
| POST | `http://127.0.0.1:8000/api/samhita/analyze` | JSON analysis for an authenticated doctor; 400 for missing symptoms; 303 to login anonymously |
| POST | `http://127.0.0.1:8000/api/voice/transcribe` | 400/422 for invalid or missing audio; provider-dependent result for valid audio |
| POST | `http://127.0.0.1:8000/api/voice/extract` | 200 structured extraction/fallback |
| POST | `http://127.0.0.1:8000/api/ai-chat` | 200 AI/fallback response |
| GET | `http://127.0.0.1:8000/hospital/list` | Currently 404 |
| GET | `http://127.0.0.1:8000/hospital/admission` | Currently 404 |
| GET | `http://127.0.0.1:8000/api/hospitals` | Currently 404 |
| POST | `http://127.0.0.1:8000/api/admission/request` | Currently 404 |
| GET | `http://127.0.0.1:8000/api` | 200 |

## Vercel deployment notes

- Configure `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `SECRET_KEY`, and the production `DATABASE_URL` as Vercel environment variables; never copy local `.env` values into source or deployment notes.
- Configure `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI` to match the deployed HTTPS callback URL registered with Google. Then test the complete OAuth redirect in the deployed environment.
- Confirm the deployment uses a supported Python runtime and installs dependencies from the project manifest. The local `.venv` is currently broken, so do not use it as a deployment artifact.
- The current database URL is SQLite. Vercel serverless storage is ephemeral; use a persistent hosted database before relying on saved Samhita analyses or admissions across invocations.
- No Vercel endpoint behavior was exercised in this audit. Hospital features need an approved data model, hospital records, bed update semantics, and admission validation before deployment.

Post-fix validation: all five changed Python files compiled successfully under Python 3.13.12; voice extraction returned 200 with no unawaited-coroutine warning. Static checks found the required Samhita button, results container, request, renderer, loading label, error logger, and DOM-ready listener. The existing CRLF template produces `git diff --check` carriage-return warnings on added lines; line endings were left unchanged to avoid a broad unrelated rewrite.
