# Business Requirements Document: Kash AI

## 1. Document Control

| Item | Details |
| --- | --- |
| Product | Kash AI |
| Project Type | Ayurveda-first healthcare superapp and clinic operating system |
| Version | 1.0 |
| Date | 2026-08-08 |
| Prepared For | Product, engineering, clinical operations, launch, and stakeholder review |
| Primary Codebase | FastAPI/Jinja application with supporting Node.js WhatsApp notification service |

## 2. Executive Summary

Kash AI is a production-oriented healthcare platform for Ayurvedic clinics and integrated care teams. The product combines doctor workflows, patient management, case sheets, appointments, prescriptions, EMR, AI-assisted Ayurveda analysis, voice consultation support, telemedicine, prescription OCR, patient tools, payments, medicine ordering, audit logging, analytics, and operations monitoring.

The core business goal is to help clinics deliver faster, safer, better-documented Ayurveda and integrated healthcare while creating follow-on revenue loops through medicine ordering, subscriptions, telemedicine, diagnostics, pharmacy operations, and marketplace extensions.

The clinic pilot scope prioritizes the doctor and patient care workflow: authentication, patient registry, consultations, AI assistance, prescriptions, follow-ups, voice capture, EMR, telemedicine, order medicines, payments, admin, audit, export, and analytics. Larger commerce and partner modules such as pharmacy owner, lab owner, delivery, marketplace, and subscriptions exist in the codebase but are marked as frozen for clinic pilot v1 in `app/main.py`.

## 3. Business Objectives

1. Digitize Ayurveda clinic operations from patient intake to follow-up.
2. Reduce doctor documentation time through AI, voice capture, and structured case sheets.
3. Improve quality of care with Samhita-grounded AI guidance, Ayurveda terminology support, herb-drug interaction checks, and outcome tracking.
4. Increase patient retention through follow-ups, prescriptions, health passports, communication, telemedicine, and medicine ordering.
5. Enable clinic administrators to monitor activity, system health, users, audit logs, and operational metrics.
6. Build a scalable foundation for pharmacy, diagnostics, delivery, panchakarma, marketplace, and subscription revenue lines.
7. Prepare the product for safe launch with role-based access, CSRF protection, rate limiting, security headers, backups, health checks, and deployment automation.

## 4. Product Vision

Kash AI should become an integrated Ayurveda and modern care operating system where a practitioner can register a patient, understand symptoms, capture consultation notes, receive AI-supported clinical assistance, prescribe treatment, share care instructions, collect payments, track outcomes, and continue care through medicines, diagnostics, and follow-ups.

## 5. Target Users

| User Group | Needs |
| --- | --- |
| Ayurveda doctors | Fast patient lookup, case sheets, Ayurveda assessment, AI support, prescriptions, follow-ups, outcomes |
| Integrated medicine practitioners | Ayurveda and modern consultation support, vitals, diagnostics, interaction checks |
| Clinic administrators | User management, audit logs, reports, payments, exports, health monitoring |
| Patients | Access to prescriptions, health records, telemedicine, medicine information, orders, follow-ups |
| Pharmacy partners | Medicine inventory, stock alerts, expiry tracking, orders, fulfillment |
| Lab partners | Diagnostic booking, result upload, patient-linked reports |
| Delivery partners | Delivery assignment, order tracking, fulfillment status |
| Platform operators | Deployment, monitoring, backups, security, usage analytics |

## 6. Current System Overview

Kash AI is built as a FastAPI application using SQLAlchemy models, Jinja templates, static JavaScript/CSS, and multiple feature routers. It includes:

- Server-rendered web portals for doctors, patients, admin, EMR, telemedicine, payments, prescriptions, and operations.
- API endpoints for EMR, consultations, prescriptions, diagnostics, appointments, reports, AI chat, and health checks.
- AI services for RAG, Samhita-aware answers, prescription analysis, image recognition, pharmacy assistance, business intelligence, diet guidance, order automation, and voice support.
- A Node.js sidecar service for WhatsApp notifications, reminders, Twilio integration, Redis queues, and prescription image workflows.
- Deployment support for local, Docker, Railway, Render, Google Cloud Run, Cloud SQL, Nginx, and system services.

## 7. In-Scope Modules

### 7.1 Authentication and Roles

Requirements:

- Support doctor signup and login.
- Support first admin/doctor onboarding when public signup is enabled.
- Support Google authentication where configured.
- Maintain secure sessions with idle timeout.
- Enforce role-based portal access.
- Support CSRF protection for mutating actions.
- Provide logout and session management behavior.

Primary users:

- Doctor
- Clinic admin
- Portal users

### 7.2 Doctor Dashboard

Requirements:

- Show daily clinical overview.
- Show patients, appointments, follow-ups, risk patients, and activity.
- Provide shortcuts into patient registration, consultation, prescriptions, and AI tools.
- Provide AI morning brief and risk patient lists where enabled.

### 7.3 Patient Registry and Profiles

Requirements:

- Register patients with demographics and clinical profile data.
- Search patients by query and system.
- View patient detail, timeline, history, and linked records.
- Update patient profile data.
- Manage patient profiles and selectors where multiple profiles are supported.
- Support patient linking and public clinic flows.

### 7.4 Case Sheets and Consultations

Requirements:

- Create and update case sheets.
- Support modern, Ayurveda, and integrated consultation types.
- Capture chief complaint, symptoms, vitals, notes, diagnosis, assessment, and plan.
- Support SOAP-style structured notes.
- Support Ayurveda-specific assessment such as prakriti, dosha, srotas, and panchakarma planning.
- Generate AI-assisted clinical suggestions and diet guidance.
- Preserve consultation history in the patient timeline.

### 7.5 AI Clinical Assistance

Requirements:

- Provide AI symptom analysis for Ayurveda use cases.
- Ground AI responses in Samhita knowledge where possible.
- Fall back to safe rule-based guidance when AI provider or local model is unavailable.
- Detect unsafe or prompt-injection-like input.
- Support AI chat with context and patient ID.
- Support AI doctor flows, pure AI flows, AI dashboard, and AI feature status pages.
- Log AI activity where required for audit and review.

### 7.6 Voice and Ambient EMR

Requirements:

- Support voice consultation page.
- Support audio upload transcription.
- Support live microphone transcription.
- Convert voice input into structured case-sheet content.
- Support ambient EMR/scribe workflows where enabled.
- Handle microphone permissions and device readiness checks.

### 7.7 Prescriptions

Requirements:

- Create Ayurveda and modern prescriptions.
- View prescription detail and history.
- Generate prescription preview.
- Send and resend prescriptions.
- Support downloadable prescription preview/PDF.
- Support prescription OCR and prescription analysis.
- Track prescription delivery logs.
- Support WhatsApp prescription sharing through the notification service where configured.

### 7.8 EMR

Requirements:

- Maintain patient EMR data.
- Support integrated medicine consultations.
- Support vitals, drug/herb data, active prescriptions, lab orders, result updates, and timelines.
- Support clinical reports, Ayurveda reports, financial reports, and audit logs.
- Provide templates for doctor dashboard, patient registry, integrated consultation, mobile EMR, clinical decisions, consent forms, audit trail, lab dashboard, billing integration, and panchakarma scheduling.

### 7.9 Appointments and Follow-Ups

Requirements:

- Book appointments.
- View today’s doctor appointments.
- Update appointment status.
- Track follow-ups due and overdue.
- Support reminders through queued communication integrations where configured.

### 7.10 Telemedicine

Requirements:

- Support patient and guest telemedicine booking.
- Support doctor consultation lists.
- Support video consultation pages.
- Provide telemedicine start endpoint/probe.
- Link telemedicine activity back to patient records.

### 7.11 Medicine Information and Ordering

Requirements:

- Search and display medicine details.
- Support medicine alternatives and price comparison.
- Support patient medicine order flows.
- Support order confirmation, invoice, and tracking pages.
- Maintain medicine catalog and supplier data.

### 7.12 Payments

Requirements:

- Support payment routes and daily payment views.
- Integrate Razorpay configuration in production environments.
- Avoid exposing payment secrets in logs.
- Support financial reporting and reconciliation needs.

### 7.13 Outcome Tracking

Requirements:

- Track patient outcomes.
- Provide outcome list and analytics.
- Connect outcomes to consultations, prescriptions, and follow-up workflows.
- Use outcome data to improve clinical trust, retention, and reporting.

### 7.14 Patient Tools

Requirements:

- Provide patient-facing AI assistant.
- Provide health passport and health card pages.
- Provide symptom analyzer, diet analyzer, lab analyzer, handwriting decoder, medicine detail, and alternatives pages where enabled.
- Support simple patient dashboard and patient home flows.

### 7.15 Admin and Operations

Requirements:

- Provide admin dashboard.
- Show system health, active sessions, database size, metrics, and analytics totals.
- Manage users and orders where implemented.
- Provide growth dashboard, fallback pages, audit logs, medicine database admin, and bulk upload.
- Support backup, export, audit, health, statistics, sales, and debug routes.

### 7.16 Notifications and Communication

Requirements:

- Support email prescription delivery.
- Support WhatsApp notifications and patient updates.
- Support Twilio webhook/reminder services in the Node sidecar.
- Support queue-based reminders with Redis/BullMQ where configured.
- Log communication delivery events.

### 7.17 Security, Compliance, and Trust

Requirements:

- Apply security headers, HTTPS enforcement in production, session protection, CSRF protection, rate limits, trusted hosts, and CORS configuration.
- Support audit logs for sensitive user and patient actions.
- Protect uploaded files with validation.
- Avoid leaking API keys, secrets, and PHI in logs.
- Provide privacy, terms, and trust pages.
- Provide emergency detection/logging support where enabled.

## 8. Frozen or Future Expansion Modules

The following modules exist in the codebase but are marked as frozen or not needed for clinic pilot v1 in `app/main.py`. They should be treated as future expansion unless explicitly reactivated:

- Pharmacy owner portal
- Pharmacy portal
- AI pharmacy routes
- Lab owner portal
- Lab portal
- Lab analyzer route
- Delivery portal
- Delivery route
- Marketplace route
- Ecommerce route
- Subscription route
- Startup/demo route

Future business opportunities:

- Panchakarma marketplace
- Personalized Ayurveda kits
- Pharmacy network fulfillment
- Diagnostics booking and lab result exchange
- Delivery partner operations
- Clinic subscription tiers
- Verified practitioner marketplace
- Community and wellness retention loops

## 9. Functional Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-001 | Users shall be able to sign up, log in, and maintain secure sessions. | Must |
| FR-002 | Doctors shall be able to register, search, view, and update patients. | Must |
| FR-003 | Doctors shall be able to create consultations and case sheets. | Must |
| FR-004 | The system shall support Ayurveda, modern, and integrated consultation data. | Must |
| FR-005 | The system shall provide AI-assisted Ayurveda guidance with fallback behavior. | Must |
| FR-006 | The system shall support voice transcription for consultation documentation. | Should |
| FR-007 | Doctors shall be able to create, preview, send, resend, and view prescriptions. | Must |
| FR-008 | Patients shall be able to access patient-facing pages and health records where enabled. | Should |
| FR-009 | The system shall support appointments and follow-up tracking. | Must |
| FR-010 | The system shall support telemedicine booking and consultation flows. | Should |
| FR-011 | The system shall support medicine information and patient order flows. | Should |
| FR-012 | The system shall support payment capture and payment reporting. | Should |
| FR-013 | Admins shall be able to view system health, users, metrics, and audit logs. | Must |
| FR-014 | The system shall log clinically and operationally significant events. | Must |
| FR-015 | The system shall support backup and export workflows. | Must |
| FR-016 | The system shall provide health check endpoints for deployment monitoring. | Must |
| FR-017 | The system shall support multilingual patient/doctor interactions where locale files exist. | Could |
| FR-018 | The system shall support prescription OCR and image analysis. | Should |
| FR-019 | The system shall support outcome tracking and reporting. | Should |
| FR-020 | The system shall expose documented EMR APIs for integrations. | Should |

## 10. Non-Functional Requirements

### 10.1 Security

- Enforce CSRF protection on mutating requests.
- Enforce session timeout.
- Enforce role-based route access.
- Apply security headers including frame, content type, referrer, permissions, and CSP controls.
- Support HTTPS redirect in production.
- Validate uploaded files and AI prompts.
- Avoid logging secrets and sensitive patient data.

### 10.2 Privacy and Compliance

- Store patient data only for authorized users.
- Maintain audit trails for sensitive access and changes.
- Provide privacy and terms pages.
- Support export and backup controls.
- Treat AI-generated content as assistive and subject to clinician review.

### 10.3 Reliability

- Provide `/health`, `/healthz`, and production health metrics.
- Support graceful AI fallback when external providers fail.
- Use overload protection for excessive concurrent requests.
- Support background backup scheduling.
- Use deployment checklists and runbooks before production release.

### 10.4 Performance

- Use gzip compression.
- Cache selected public/system pages with ETags.
- Rate-limit API traffic by IP and authenticated actor.
- Maintain responsive page rendering for clinic workflows.

### 10.5 Scalability

- Support SQLite for local/pilot use and PostgreSQL/Cloud SQL for production migration.
- Use Redis-backed queue capability for reminders and notifications where configured.
- Keep modules router-based so pilot and future expansion routes can be enabled selectively.

### 10.6 Usability

- Provide fast access to common doctor tasks.
- Keep clinical workflows structured but efficient.
- Support mobile-friendly patient and EMR pages.
- Provide device checks for microphone/camera-dependent workflows.

## 11. Data Requirements

Core entities:

- Doctors
- Patients
- Case sheets
- Appointments
- Prescriptions
- Payments
- Patient queries
- Pending reviews
- Audit logs
- AI logs
- Patient health passports
- Prescription delivery logs
- Emergency alert logs
- Medicines
- Suppliers
- Orders
- Outcomes
- Subscriptions
- Care plans
- EMR consultations
- Lab orders and results

Important data characteristics:

- Patient and doctor IDs must be indexed for retrieval.
- Created/updated timestamps must support reporting and auditability.
- Follow-up dates must support reminders and dashboards.
- Clinical notes must preserve structured and free-text fields.
- AI outputs should retain traceability where AI logs are enabled.

## 12. Integrations

| Integration | Purpose |
| --- | --- |
| Groq | AI chat and transcription-related AI support |
| Google GenAI/Gemini | AI provider capability |
| OpenAI | AI provider capability |
| Ollama/local models | Local fallback or offline AI mode |
| Razorpay | Payment collection |
| Twilio | WhatsApp/SMS messaging and webhooks |
| Redis/BullMQ | Reminder and notification queues |
| Email service | Prescription and patient communication |
| Sentry | Production error tracking where configured |
| Cloud Run/Cloud SQL | Production deployment target |
| Docker/Railway/Render/Nginx | Deployment options |

## 13. Reporting and Analytics

Required reports:

- Clinical reports by date range.
- Ayurveda dosha distribution.
- Daily financial reports.
- Patient timelines.
- Appointment summaries.
- Follow-up summaries.
- Audit log reports.
- Admin metrics.
- AI usage/status reports.
- Outcome analytics.

## 14. Launch Scope

### Pilot Must-Haves

- Secure login/session flow.
- Patient registration and registry.
- Doctor dashboard.
- Case sheet and consultation workflow.
- AI symptom analyzer with fallback.
- Prescription creation and preview.
- Appointment/follow-up tracking.
- EMR patient timeline.
- Admin health/metrics.
- Backup and export.
- Health checks.
- Basic payment and order-medicine flow if required for pilot.

### Pilot Should-Haves

- Voice consultation transcription.
- Telemedicine.
- Prescription OCR.
- WhatsApp prescription sharing.
- Outcome tracking.
- Health passport.

### Post-Pilot

- Full pharmacy portal.
- Full lab portal.
- Delivery portal.
- Marketplace.
- Subscriptions.
- Ecommerce expansion.
- Personalized kits and panchakarma marketplace.

## 15. User Journeys

### Doctor Consultation Journey

1. Doctor logs in.
2. Doctor searches or registers a patient.
3. Doctor opens patient detail.
4. Doctor creates a case sheet or consultation.
5. Doctor uses AI, voice capture, or Ayurveda tools for assistance.
6. Doctor creates prescription and care plan.
7. Doctor sends prescription and schedules follow-up.
8. System updates patient timeline and health passport.

### Patient Continuity Journey

1. Patient receives prescription or portal link.
2. Patient views health information, prescriptions, or recommendations.
3. Patient books telemedicine or follow-up where enabled.
4. Patient orders medicine if needed.
5. Patient outcomes are tracked over time.

### Admin Operations Journey

1. Admin logs in.
2. Admin reviews users, metrics, audit logs, system health, and backups.
3. Admin exports data or reviews reports.
4. Admin monitors launch readiness and resolves operational issues.

## 16. Business Rules

- AI output is advisory and must not replace clinician judgment.
- Public signup should be disabled after initial admin onboarding in production unless intentionally enabled.
- Production secrets must be rotated if ever committed or shared.
- Subscription feature enforcement should block paid feature usage when limits are reached.
- Patient data must only be accessible to authorized roles.
- Frozen modules must not be presented as live pilot capabilities unless routes are re-enabled and tested.
- Payment configuration must be validated before production payments are accepted.
- Communication delivery failures must be logged and retryable where supported.

## 17. Acceptance Criteria

The project is launch-ready for pilot when:

- A doctor can complete login, patient registration, consultation, prescription, and follow-up without errors.
- AI analyzer returns useful output and displays safe fallback messaging when AI provider is unavailable.
- Patient timeline correctly reflects consultations, prescriptions, appointments, and relevant events.
- Admin can view health, metrics, audit logs, and operational data.
- Health check endpoints return expected status in the target environment.
- Security middleware is active in production.
- Backup and restore process is documented and tested.
- Payment and communication integrations are either configured and tested or clearly disabled.
- Frozen modules are hidden or clearly excluded from pilot workflows.

## 18. Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| AI hallucination or unsafe advice | Clinical trust and safety risk | Ground in Samhita/RAG, provide fallback, require doctor review |
| Misconfigured production secrets | Security and payment risk | Use `.env.example`, secret rotation scripts, production startup warnings |
| Incomplete frozen module behavior | User confusion | Keep routes disabled for pilot, document post-pilot scope |
| Patient data exposure | Legal and trust risk | Role guard, CSRF, sessions, audit logs, secure headers |
| External provider downtime | Broken AI/communication workflows | Graceful fallback, health checks, retry queues |
| Local SQLite production limits | Scale and reliability risk | Migrate to PostgreSQL/Cloud SQL for production |
| Payment integration errors | Revenue and reconciliation risk | Test Razorpay keys, daily report, transaction logs |
| Voice/camera permission issues | Consultation workflow disruption | Device-check page and manual entry fallback |

## 19. Success Metrics

- Patient registration completion rate.
- Average consultation documentation time.
- Number of prescriptions generated and sent.
- Follow-up completion rate.
- AI feature usage and fallback rate.
- Telemedicine booking completion rate.
- Medicine order conversion rate.
- Payment success rate.
- Active doctors/clinics.
- Patient retention and repeat visits.
- Outcome improvement records completed.
- System uptime and error rate.

## 20. Dependencies

- Python 3 runtime and dependencies in `requirements.txt`.
- Node.js 20+ for WhatsApp notification service.
- Database: SQLite for local/pilot, PostgreSQL/Cloud SQL for production.
- Environment variables from `.env.example`.
- Static/template assets in `static/`, `templates/`, `shared/`, and `public/`.
- Optional Redis service for reminders/queues.
- Optional AI provider keys.
- Optional Razorpay and Twilio credentials.

## 21. Open Questions

1. Which clinic pilot features are mandatory for the first live clinic: telemedicine, payments, WhatsApp, medicine orders, or only EMR/prescription?
2. Which AI provider is the preferred production default?
3. Should the platform be branded only as Kash AI or as a clinic-white-label product?
4. What regulatory/compliance standard should be used for production handling of patient data?
5. What payment and subscription model should be active in the first commercial launch?
6. Which frozen modules should be reactivated first after pilot validation?

## 22. Appendix: Key Local Documents

- `README.md`
- `ARCHITECTURE.md`
- `USER_MANUAL.md`
- `docs/EMR_API.md`
- `docs/COMPETITIVE_ADVANTAGE.md`
- `DEPLOYMENT.md`
- `QA_CHECKLIST.md`
- `OPERATIONS_RUNBOOK.md`
- `SECURITY.md`
- `VOICE_CONSULTATION_GUIDE.md`
- `WHATSAPP_ROUTING.md`
