# ARCHITECTURE

## Folder Structure

- `app/`: core FastAPI app setup, config, auth, database, middleware
- `routers/`: primary feature routers for doctor, dashboard, cases, auth, emergency, passports, and more
- `routes/`: additional route modules including prescriptions and payments
- `services/`: business logic and integrations such as AI, email, voice, prescriptions, emergency detection, and health passport updates
- `models/`: SQLAlchemy models for prescriptions and operational extensions
- `templates/`: Jinja-rendered UI templates
- `static/`: JavaScript and CSS assets used by the server-rendered app
- `shared-static/`: shared UI CSS and JS
- `public/`: PWA manifest, service worker, icons, and public assets
- `src/`: sidecar/frontend utility code including locale files and JS service modules

## Main Feature Connections

- Auth starts in `routers/auth.py` and is enforced through `app/auth.py`
- Dashboard data is assembled in `routers/patients.py` and `services/emr_service.py`
- Morning brief is served by `routers/dashboard.py` and generated in `services/ai_provider.py`
- Case sheets live in `routers/cases.py` and call `services/voice_ai.py` for transcription
- Prescriptions are created in `routes/prescription.py` and delivered via `services/prescription_service.py` and `services/email_service.py`
- Emergency detection spans `services/emergency_service.py`, `static/js/emergency_guard.js`, and `routers/emergency.py`
- Health passports are updated from case and prescription flows through `services/health_passport_service.py`

## Database Schema Overview

Core tables:

- `doctors`
- `patients`
- `case_sheets`
- `appointments`
- `prescriptions`
- `payments`
- `patient_queries`
- `pending_reviews`

Operational tables added or strengthened:

- `doctor_action_logs`
- `prescription_delivery_logs`
- `emergency_alert_logs`
- `patient_health_passports`

Important indexed fields:

- `patient_id`
- `doctor_id`
- `created_at`
- `followup_date`

## API Endpoints

- `GET /dashboard`: doctor dashboard
- `GET /api/dashboard/morning-brief`: AI morning brief
- `GET /api/dashboard/risk-patients`: AI risk list
- `POST /patients/{patient_id}/cases`: save case sheet
- `POST /patients/{patient_id}/cases/transcribe-audio`: upload audio transcription
- `POST /patients/{patient_id}/cases/transcribe-live`: live microphone transcription
- `GET /patients/{patient_id}/prescriptions/new`: prescription form
- `POST /prescriptions/create`: create prescription
- `GET /prescriptions/{prescription_id}`: prescription detail
- `GET /prescriptions/{prescription_id}/preview`: email preview
- `POST /prescriptions/{prescription_id}/send`: send prescription email
- `POST /prescriptions/{prescription_id}/download-preview`: generate preview PDF
- `GET /patients/{patient_id}/prescriptions/history`: prescription history
- `POST /prescriptions/{prescription_id}/resend`: resend prescription
- `POST /api/emergency/log`: log emergency alert
- `GET /emergency-log`: emergency log UI
- `GET /emergency-log/export`: emergency CSV export
- `GET /patient/{patient_id}/health-passport`: health passport page
- `GET /patient/{patient_id}/health-card`: shareable health card
