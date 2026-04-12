# Kash ai

![status](https://img.shields.io/badge/status-launch--prep-green)
![tests](https://img.shields.io/badge/tests-17%20passed%20%2F%202%20skipped-brightgreen)

FastAPI-based AI EMR for Ayurvedic clinics. The system covers doctor authentication, patient and case workflows, appointments, follow-ups, audit logging, analytics, and a Samhita-grounded AI analyzer with graceful fallback mode.

## Quick Start
1. Copy `.env.example` to `.env`
2. Set `SECRET_KEY`
3. Start the app with `.\start_local.ps1` or `.\launch_helper.bat`
4. Run tests with `powershell -ExecutionPolicy Bypass -File scripts\run_tests.ps1`

## Demo Credentials
- Create the first doctor account through `/signup` when `ALLOW_PUBLIC_SIGNUP=true`
- Switch `ALLOW_PUBLIC_SIGNUP=false` after onboarding admins

## Documentation
- Deployment: [DEPLOYMENT.md](DEPLOYMENT.md)
- User guide: [USER_MANUAL.md](USER_MANUAL.md)

## Operations
- Environment check: `verify_environment.py`
- Admin metrics: `/api/admin/metrics`
- Health check: `/healthz`
- AI status: `/api/ai/status`
