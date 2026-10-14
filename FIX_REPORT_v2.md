# KASH AI Remediation and Verification Report v2

Date: 2026-10-15

## Issues found

- The checked-in `.venv` path was an invalid OneDrive reparse-point tree: it lacked a usable `pyvenv.cfg`, referenced an inaccessible Python 3.14 installation, and recursive removal stalled. It could not safely be replaced in place because OneDrive retained reparse-point children.
- AI table schemas already existed and were created in the active database; no missing AI tables were found. The current `AIConversationHistory` and `AIPrediction` schemas differ from the abbreviated role/content and patient/value/confidence examples in the request, but match application service usage and are preserved.
- Groq errors were silently swallowed, preventing useful diagnosis. Groq retries could also delay fallback responses when outbound networking was blocked.
- The tongue route alias `/api/tongue/analyze` was missing.
- A Vertex project id without ADC credentials was reported as a configured Gemini provider, causing avoidable Google credential discovery and retries.
- No valid audio fixture was available. The `/api/voice/transcribe` route already exists; a synthetic WAV placeholder reached the handler, but the provider was unreachable. There was no suitable tongue image fixture for multipart image verification.

## Fixes applied

- Created `.venv.rebuilt` with Python 3.13.12 and installed `requirements.txt`. App initialization, database initialization, imports, and compilation succeed in this environment. The old OneDrive-managed `.venv` tree was left intact because it could not be safely removed without a reparse-point operation.
- Confirmed all 73 registered SQLAlchemy model classes and five requested AI tables exist; wrote the complete table and column audit to `table_audit.txt`.
- Added hidden-schema alias `POST /api/tongue/analyze` for the existing tongue analysis handler.
- Added exception logging to `app/utils/groq_client.py`, and set bounded Groq timeout/retry behavior so provider failure returns to fallback promptly.
- Updated Gemini readiness detection in `app/services/ai_provider.py`: a Vertex project alone is not sufficient; explicit API key or ADC configuration is required.
- Preserved existing authenticated access requirements for Samhita and tongue analysis.
- Existing OAuth callback state handoff, voice extraction awaiting behavior, and hospital feature compatibility fixes were retained.

## Verification results

- Database: `init_db()` printed `DB ready`; all five AI tables are present. No missing tables.
- App: import succeeds and registers 632 routes. Changed Python modules compile. Uvicorn started on `127.0.0.1:8765`; `GET /api` returned HTTP 200, then the temporary server was stopped.
- Samhita exact sample: PASS, HTTP 200 with `success=true` and all five required analysis sections populated through fallback.
- Voice extraction: PASS, HTTP 200 with structured fallback response.
- AI chat: PASS, HTTP 200 with safe fallback response.
- Tongue alias/text flow: PASS, HTTP 200 with structured fallback response.
- Churn route: PASS, HTTP 200.
- Voice transcription: route exists and returned HTTP 200 for a synthetic multipart WAV placeholder, but `success=false` because Groq networking failed; a valid audio sample/provider connection is needed to verify actual transcription.
- Tongue multipart image path: SKIPPED because no suitable tongue image fixture is available; the new alias was verified with the supported text-input path.
- Templates: `/consultation/voice`, `/hospital/list`, `/hospital/admission`, `/new`, `/auth/login`, and `/auth/signup` rendered HTTP 200. `/dashboard` and `/new/doctor` returned expected 303 authentication redirects.
- Hospital end-to-end: PASS. Five hospitals listed; admission reduced bed availability from 44 to 43; discharge restored 44; repeated discharge left 44 unchanged.
- Full requested route sweep: all routes returned permitted statuses and no 500s; see `final_route_report.txt`.

## Provider and environment blockers

- An authenticated direct Groq request could not connect because Windows denied outbound socket access (`WinError 10013`), including when rerun with escalation. Therefore provider-backed generation is not verifiable in this environment; endpoint response contracts and fallback behavior are verified. Gemini and OpenAI API keys are absent, and Vertex ADC is not configured.
- `.venv` itself was not swapped in-place because the directory is managed as a reparse-point tree by OneDrive. Use `.venv.rebuilt\Scripts\python.exe` for this verification run. If the user needs the conventional `.venv` name, close processes using the old tree and move/replace it from OneDrive-aware Windows Explorer after confirming sync state.
- Startup emitted a non-fatal SQLAlchemy warning that SQLite URI query parameter `cache` is ignored without `uri=true`, and a non-fatal PyMuPDF `fitz` deprecation warning. The app still initialized and loaded.

## Vercel deployment recommendations

- Deploy a supported Python runtime with dependencies installed from the project requirements and ensure the deployment build is compatible with the app’s FastAPI entrypoint.
- Provide a strong `SECRET_KEY`, production database URL, and Groq API key as Vercel environment variables; add Gemini API credentials only if using that provider. Never commit `.env` or credentials.
- Provision persistent database storage (or a managed PostgreSQL service) because serverless filesystem storage is ephemeral; do not depend on local SQLite writes across invocations.
- Configure static/template asset packaging and verify runtime-created directories are writable or redirect them to an appropriate persistent/object store.
- Confirm routes that require authenticated doctor/admin sessions are exercised with valid deployment cookies and CSRF tokens.


