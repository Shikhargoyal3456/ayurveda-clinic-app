from __future__ import annotations

import json
from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def get_prescription_templates() -> list[dict[str, object]]:
    templates_path = settings.base_dir / "data" / "prescription_templates.json"
    if not templates_path.exists():
        return []
    return json.loads(templates_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def get_medicine_catalog() -> list[str]:
    catalog_path = settings.base_dir / "data" / "medicine_catalog.json"
    if not catalog_path.exists():
        return []
    return json.loads(catalog_path.read_text(encoding="utf-8"))


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

