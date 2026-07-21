# CHANGELOG

## [Phase 1] Full audit completed | Files modified
- Audit completed against the existing FastAPI, Node, and Expo workspaces before code changes.

## [Phase 2] Foundation and security hardening | Files modified
- Consolidated environment-driven settings in `.env.example`, `.gitignore`, `app/config.py`, `deploy.sh`
- Added DB-backed audit logging and operational tables in `models/clinic_ops.py`, `app/audit.py`, `app/database.py`
- Added startup Gmail connection validation in `app/main.py`, `services/email_service.py`
- Removed hardcoded email/test values in `routes/prescription.py`, `routers/contact.py`, `templates/patient_simple_base.html`
- Tightened rate limit defaults in `app/config.py`, `src/config.js`
- Added follow-up and log indexes in `app/database.py`, `app/models.py`

## [Phase 3] Hindi voice scribe with Sarvam | Files modified
- Added Ayurvedic vocabulary correction in `services/ayurvedic_vocabulary.py`, `src/utils/ayurvedic_vocabulary.js`
- Switched voice transcription to Sarvam in `services/voice_ai.py`
- Enforced CSRF on live transcription in `routers/cases.py`
- Upgraded the voice scribe UI in `templates/add_case.html`

## [Phase 4] Prescription system rebuild | Files modified
- Added service module in `services/prescription_service.py`
- Added email preview, PDF generation, history, resend, and delivery logging in `routes/prescription.py`
- Added new templates `templates/prescriptions/preview.html`, `templates/prescriptions/history.html`
- Updated `templates/prescriptions/detail.html`, `templates/prescriptions/form.html`

## [Phase 5] PWA offline mode | Files modified
- Added `public/manifest.json`, `public/sw.js`, `static/js/pwa.js`
- Generated placeholder icons `public/icon-192.png`, `public/icon-512.png`
- Integrated offline queue UI and manifest links in `templates/base.html`

## [Phase 6] Dashboard upgrades | Files modified
- Added clickable stat cards, upgraded follow-up queue, mobile quick actions, and recent patient summaries in `templates/dashboard.html`
- Added dashboard patient pagination in `routers/patients.py`

## [Phase 7] Emergency detection upgrade | Files modified
- Added backend emergency detection service `services/emergency_service.py`
- Added frontend detector `src/services/emergency.service.js`, `static/js/emergency_guard.js`
- Added emergency logging routes and export in `routers/emergency.py`
- Added emergency log UI in `templates/emergency/log.html`
- Wired router and overlay styles in `app/main.py`, `templates/base.html`

## [Phase 8] Patient health passport | Files modified
- Added passport update service in `services/health_passport_service.py`
- Added routes in `routers/health_passport.py`
- Added UIs in `templates/patients/health_passport.html`, `templates/patients/health_card.html`
- Wired automatic passport updates from case and prescription creation in `routers/cases.py`, `routes/prescription.py`

## [Phase 9] Multilingual UI | Files modified
- Added locale files `src/locales/en.js`, `src/locales/hi.js`
- Added client i18n toggle in `static/js/i18n.js`
- Wired top-nav translation targets in `templates/base.html`
- Added language-aware morning brief generation in `routers/dashboard.py`, `services/ai_provider.py`, `templates/dashboard.html`

## [Phase 10] Performance improvements | Files modified
- Added patient list pagination in `routers/patients.py`, `templates/dashboard.html`
- Reused existing gzip middleware and added more lazy/offline-friendly shared assets in `templates/base.html`

## [Phase 11] Final documentation | Files modified
- Added `README.md`
- Added `CHANGELOG.md`
- Added `ARCHITECTURE.md`
- Added `ENV_SETUP.md`
