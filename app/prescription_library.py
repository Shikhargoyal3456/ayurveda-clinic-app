from __future__ import annotations

import json
from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def get_prescription_templates() -> list[dict[str, object]]:
    return []


@lru_cache(maxsize=1)
def _base_medicine_catalog() -> list[str]:
    return []


def get_medicine_catalog(specialty: str = "ayurveda") -> list[str]:
    return list(_base_medicine_catalog())


def build_prescription_share_message(
    patient_name: str,
    diagnosis: str,
    medicines: list[dict[str, str]],
    advice: str,
) -> str:
    medicine_lines = []
    for medicine in medicines:
        name = medicine.get("name", "").strip()
        dosage = medicine.get("dosage", "").strip()
        frequency = medicine.get("frequency", "").strip()
        if not name:
            continue
        details = ", ".join(part for part in [dosage, frequency] if part)
        medicine_lines.append(f"- {name}" + (f" ({details})" if details else ""))

    medicines_block = "\n".join(medicine_lines) if medicine_lines else "- No medicines listed"
    advice_block = advice.strip() or "No additional advice."
    return (
        f"Patient: {patient_name}\n"
        f"Diagnosis: {diagnosis.strip()}\n"
        f"Medicines:\n{medicines_block}\n"
        f"Advice: {advice_block}"
    )
