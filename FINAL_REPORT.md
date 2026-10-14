# KASH AI Final Verification Report

Date: 2026-10-15

## Final project location and copy

- Verified project copy: `C:\Projects\ayurveda_project`.
- The original OneDrive project remains intact as a backup.
- The source contains `ayurveda.db` at the project root, which was copied to the new project. The requested `instance\kash_ai.db` did not exist in the source, so no database was created or renamed at that path.
- `.env` was copied without displaying credentials. Only `GROQ_MODEL` was changed in the copy; the OneDrive source `.env` remains unchanged.

## Python environment

- Clean rebuild: **Yes**, at `C:\Projects\ayurveda_project\.venv`, Python 3.13.12.
- The supplied Python runtime does not include `venv.__main__`, so `python -m venv` failed. The installed `virtualenv` tool successfully created the new environment. All packages in `requirements.txt` installed successfully.
- Import verification: FastAPI, SQLAlchemy, Jinja2, and Groq imported successfully. `init_db()` completed and `app.main:app` imported with 632 registered routes.
- App startup: `uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload` started successfully. `GET /api` returned 200. The server was stopped after verification.

## Groq connectivity and model

- `GROQ_API_KEY` is loaded from the copied `.env` (value not shown). TCP connection to `api.groq.com:443` succeeded.
- The previous configured model `llama-3.3-70b-versatile` returned HTTP 404 `model_not_found` for this account.
- Queried the account's available model IDs and tested `openai/gpt-oss-20b`; it returned usable text (`OK`).
- Updated `GROQ_MODEL` in the copied `.env`, the default in `app/utils/groq_client.py`, and the default in `app/services/ai_provider.py` to `openai/gpt-oss-20b`.
- The exact Samhita sample returned HTTP 200, `success=true`, `provider=groq`, and nonempty `dosha_analysis`, `dietary_recommendations`, `herbal_formulations`, `lifestyle_regimen`, and `classical_reference` fields.

## Route and AI results

See `final_route_report_v2.txt` for every requested route and status. Summary:

- All requested page routes returned 200 or expected 303 authentication redirects.
- Samhita sample: PASS, live Groq, all five sections populated.
- Voice extraction: PASS, 200 with `success=true`.
- AI chat: PASS, 200 with `model=groq`.
- Tongue alias `/api/tongue/analyze`: PASS, 200 with `success=true` and `model=groq`.
- Churn prediction: PASS, 200 with `success=true`.
- Voice transcription route exists, but was not run because no valid audio fixture is present.
- Anonymous hospital admission request returned expected 401. Authenticated admin test session created and discharged an admission successfully.
- No 500s occurred.

## Hospital flow

Five hospitals were listed. On the copied database, the selected hospital had 44 available beds before the test, 43 after admission creation, 44 after discharge, and still 44 after repeating discharge. The duplicate discharge did not release another bed.

## Remaining notes

- Startup emits a nonfatal SQLAlchemy warning that SQLite URI option `cache` is ignored unless `uri=true` is set. It does not prevent initialization or serving requests.
- No valid voice audio sample was available for transcription verification.
- No `instance\\kash_ai.db` source file existed; the actual project database `ayurveda.db` is present in the copy.

## Run the copied app

```powershell
Set-Location C:\Projects\ayurveda_project
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Keep `.env` private. The selected Groq model setting is already in the copied `.env`.

## Vercel deployment

- Apply the same application source changes and configure `GROQ_API_KEY` and `GROQ_MODEL=openai/gpt-oss-20b` as Vercel environment variables; set the app's other production secrets there as well, not in source control.
- Use a persistent managed database such as PostgreSQL. Serverless local SQLite files do not provide reliable persistence across invocations.
- Configure the FastAPI entrypoint, Python dependencies, static/template assets, and writable temporary paths for the Vercel runtime.
- Exercise protected routes with valid doctor/admin sessions and CSRF tokens after deployment.
