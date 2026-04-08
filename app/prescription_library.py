from __future__ import annotations

import json
from functools import lru_cache

from app.config import settings


SPECIALTY_MEDICINE_FALLBACKS: dict[str, list[str]] = {
    "modern_medicine": [
        "Paracetamol 500 mg",
        "Cetirizine 10 mg",
        "Pantoprazole 40 mg",
        "Azithromycin 500 mg",
        "Amoxicillin 500 mg",
        "Ibuprofen 400 mg",
        "Ondansetron 4 mg",
        "ORS Sachet",
        "Vitamin B Complex",
        "Calcium + Vitamin D3",
    ],
    "homeopathy": [
        "Arnica Montana 30",
        "Belladonna 30",
        "Bryonia Alba 30",
        "Nux Vomica 30",
        "Rhus Toxicodendron 30",
        "Pulsatilla 30",
        "Gelsemium 30",
        "Merc Sol 30",
    ],
    "dental": [
        "Amoxicillin 500 mg",
        "Metronidazole 400 mg",
        "Ibuprofen 400 mg",
        "Diclofenac 50 mg",
        "Chlorhexidine Mouthwash",
        "Mefenamic Acid 500 mg",
        "Paracetamol 650 mg",
    ],
    "physiotherapy": [
        "Aceclofenac 100 mg",
        "Paracetamol 650 mg",
        "Calcium + Vitamin D3",
        "Topical Diclofenac Gel",
        "Muscle Relaxant",
        "Hot Pack Advice",
        "Resistance Band Exercises",
    ],
}


@lru_cache(maxsize=1)
def get_prescription_templates() -> list[dict[str, object]]:
    templates_path = settings.base_dir / "data" / "prescription_templates.json"
    if not templates_path.exists():
        return []
    return json.loads(templates_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _base_medicine_catalog() -> list[str]:
    catalog_path = settings.base_dir / "data" / "medicine_catalog.json"
    if not catalog_path.exists():
        return []
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def get_medicine_catalog(specialty: str = "ayurveda") -> list[str]:
    normalized_specialty = (specialty or "ayurveda").strip().lower()
    if normalized_specialty == "ayurveda":
        return list(_base_medicine_catalog())
    return list(SPECIALTY_MEDICINE_FALLBACKS.get(normalized_specialty, _base_medicine_catalog()))


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
