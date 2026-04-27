# EMR User Guide

## Quick Start: Modern Medicine Doctors
- Open `/emr/doctor-dashboard` for appointments, pending labs, and follow-up reminders.
- Use `/emr/patient-registry` to search or register patients.
- Start a SOAP workflow from `/emr/modern-consultation/<patient_id>`.
- Record vitals, draft SOAP notes, add prescription items, and save the consultation.

## Quick Start: Ayurveda Doctors
- Open `/emr/patient-registry` and choose `Ayurveda consult`.
- Use `/emr/ayurveda-consultation/<patient_id>` for prakriti, vikriti, agni, ama, and srotas capture.
- Use the prakriti questionnaire and formulation suggestions to structure the visit.
- Review panchakarma planning in `/emr/panchakarma-scheduler`.

## Consultation Workflow
- Modern:
  - capture vitals
  - complete SOAP sections
  - choose ICD-11 guidance
  - add lab and prescription items
- Ayurveda:
  - review constitution snapshot
  - complete ashtavidha prompts
  - evaluate agni, ama, and srotas
  - select formulations and follow-up direction
- Integrated:
  - use `/emr/integrated-consultation/<patient_id>`
  - check drug-herb interactions before finalizing

## Prescription Writing
- Use `/emr/prescription-viewer` to review active prescriptions.
- Modern prescriptions support chronic refill counts.
- Ayurveda prescriptions should document formulation, anupana, and timing.

## Lab Workflow
- `/emr/lab-dashboard` shows pending and completed orders.
- Use `/api/labs/order` to create orders from consultation flows.
- Update results with `/api/labs/result/<id>`.

## Panchakarma Scheduling
- Open `/emr/panchakarma-scheduler`.
- Assign staff, track dates, and document progress and outcomes.

## Reporting & Analytics
- Use `/emr/clinical-reporting` for revenue and dosha trend snapshots.
- Use `/emr/data-quality` to clean missing or duplicate records.
- Use `/emr/audit-trail` for access review.

## Troubleshooting
- If patient cards appear without UR numbers, run `python scripts/migrate_emr_data.py`.
- If no EMR data appears for older patients, re-run the migration helper.
- If audit logs stay empty, confirm doctor actions are reaching `/api/audit/log`.
