# Deployment Guide

## System Requirements
- Windows 11 for local clinic installs or Docker-compatible Linux for server deployment
- Working Python runtime at `C:\Users\goyal\AppData\Local\ayurveda-runtime\Scripts\python.exe`
- Ollama installed locally if AI generation should run in primary mode
- 4 GB RAM minimum, 8 GB recommended

## Installation
1. Copy the project to the target machine.
2. Copy `.env.example` to `.env`.
3. Set a strong `SECRET_KEY`.
4. Update `ADMIN_USERNAMES` with your clinic admin accounts.
5. Run `.\install.ps1` as Administrator for a desktop-style installation.
6. Run `.\launch_helper.bat` or `.\start_local.ps1`.

## Configuration
- `APP_ENV=production` enables stricter validation.
- `DATABASE_URL` can remain SQLite for small clinics or move to PostgreSQL for multi-user deployments.
- `SESSION_HTTPS_ONLY=true` and `HTTPS_REDIRECT_ENABLED=true` are recommended behind TLS.
- `AI_ENABLED=false` forces rule-based fallback mode when a clinic does not use Ollama.

## Verification
1. Run `C:\Users\goyal\AppData\Local\ayurveda-runtime\Scripts\python.exe verify_environment.py`
2. Run `powershell -ExecutionPolicy Bypass -File scripts\run_tests.ps1`
3. Open `/healthz`, `/api/ai/status`, and `/api/admin/metrics`

## Backups and Restore
- Run `scripts\backup_db.py` for manual backups.
- Run `scripts\schedule_backup.ps1` to register daily backups.
- Restore by replacing the SQLite database with a backup archive contents.
- `scripts\migrate_db.py --rollback` is not a CLI yet; use the most recent `*_premigration_*` backup if needed.

## Troubleshooting
- If the app will not start, confirm the runtime Python exists.
- If AI stays in fallback mode, verify Ollama is running and reachable at `OLLAMA_API_URL`.
- If schema warnings appear, run `python scripts\migrate_db.py` with the working runtime.
- If temp-path errors appear in tests, use `scripts\run_tests.ps1` only.

## Security Checklist
- Set a strong `SECRET_KEY`
- Use HTTPS in production
- Disable public signup when onboarding is complete
- Review `logs/security_audit.jsonl` and `logs/analytics.jsonl`
- Configure admin usernames explicitly
