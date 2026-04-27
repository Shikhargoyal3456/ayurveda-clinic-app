from __future__ import annotations

import json

from app.database import SessionLocal, init_db, commit_with_retry
from models.emr import EMRAssessment, EMRAuditLog, EMRConsultation, EMROutcome, EMRPatientProfile
from services.emr_service import create_default_assessments, ensure_emr_profile, seed_emr_from_existing_records


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        report = seed_emr_from_existing_records(db)

        profiles = db.query(EMRPatientProfile).count()
        consultations = db.query(EMRConsultation).count()
        assessments = db.query(EMRAssessment).count()
        outcomes = db.query(EMROutcome).count()
        audits = db.query(EMRAuditLog).count()

        commit_with_retry(db)
        print(
            json.dumps(
                {
                    "migrated": True,
                    "seed_report": report,
                    "totals": {
                        "profiles": profiles,
                        "consultations": consultations,
                        "assessments": assessments,
                        "outcomes": outcomes,
                        "audit_logs": audits,
                    },
                },
                indent=2,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
