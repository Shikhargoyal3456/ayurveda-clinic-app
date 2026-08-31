from __future__ import annotations

from typing import Any


def get_default_medicines() -> list[dict[str, Any]]:
    """Return a launch-safe fallback catalog for local mode and tests."""
    return [
        {
            "id": 1,
            "name": "Paracetamol 500mg",
            "price": 35,
            "category": "allopathy",
            "otc": True,
            "description": "Fever and pain relief tablet for short-term symptom support.",
        },
        {
            "id": 2,
            "name": "Dolo 650",
            "price": 42,
            "category": "allopathy",
            "otc": True,
            "description": "High-strength paracetamol support for fever and body ache.",
        },
        {
            "id": 3,
            "name": "Amoxicillin 250mg",
            "price": 85,
            "category": "allopathy",
            "otc": False,
            "description": "Prescription antibiotic option for doctor-directed bacterial infection care.",
        },
        {
            "id": 4,
            "name": "Azithromycin 500mg",
            "price": 140,
            "category": "allopathy",
            "otc": False,
            "description": "Prescription antibiotic used only under clinician guidance.",
        },
        {
            "id": 5,
            "name": "Vitamin D3 60K",
            "price": 150,
            "category": "wellness",
            "otc": True,
            "description": "Vitamin D support for bone health and low-level deficiency follow-up.",
        },
        {
            "id": 6,
            "name": "Ashwagandha",
            "price": 299,
            "category": "wellness",
            "otc": True,
            "description": "Adaptogenic herb for stress balance, sleep support, and daily vitality.",
        },
        {
            "id": 7,
            "name": "Chyawanprash",
            "price": 399,
            "category": "ayurveda",
            "otc": True,
            "description": "Traditional Ayurvedic wellness tonic for immunity and recovery routines.",
        },
        {
            "id": 8,
            "name": "Cetirizine 10mg",
            "price": 32,
            "category": "allopathy",
            "otc": True,
            "description": "Anti-allergy tablet for sneezing, itching, and seasonal symptoms.",
        },
        {
            "id": 9,
            "name": "Metformin 500mg",
            "price": 25,
            "category": "allopathy",
            "otc": False,
            "description": "Prescription diabetes medicine for clinician-managed glucose control.",
        },
        {
            "id": 10,
            "name": "Omeprazole 20mg",
            "price": 45,
            "category": "allopathy",
            "otc": True,
            "description": "Acidity and reflux support capsule for short-term digestive relief.",
        },
        {
            "id": 11,
            "name": "Amlodipine 5mg",
            "price": 32,
            "category": "allopathy",
            "otc": False,
            "description": "Prescription blood pressure medicine for ongoing doctor-supervised care.",
        },
        {
            "id": 12,
            "name": "Atorvastatin 10mg",
            "price": 65,
            "category": "allopathy",
            "otc": False,
            "description": "Prescription lipid-lowering medicine for long-term cardiovascular risk care.",
        },
        {
            "id": 13,
            "name": "Giloy Juice",
            "price": 150,
            "category": "ayurveda",
            "otc": True,
            "description": "Guduchi-based herbal tonic for immunity and seasonal resilience.",
        },
        {
            "id": 14,
            "name": "Triphala",
            "price": 99,
            "category": "ayurveda",
            "otc": True,
            "description": "Classic digestive and bowel-regularity Ayurvedic formulation.",
        },
        {
            "id": 15,
            "name": "Tulsi Drops",
            "price": 79,
            "category": "ayurveda",
            "otc": True,
            "description": "Tulsi-based daily wellness drops for throat and immunity support.",
        },
        {
            "id": 16,
            "name": "Brahmi Capsules",
            "price": 239,
            "category": "wellness",
            "otc": True,
            "description": "Memory and focus support supplement inspired by Ayurvedic practice.",
        },
        {
            "id": 17,
            "name": "Calcium + Vitamin D3",
            "price": 185,
            "category": "wellness",
            "otc": True,
            "description": "Bone and muscle support supplement for daily preventive care.",
        },
        {
            "id": 18,
            "name": "Omega 3 Capsules",
            "price": 380,
            "category": "wellness",
            "otc": True,
            "description": "Heart and joint support supplement with essential fatty acids.",
        },
        {
            "id": 19,
            "name": "Protein Powder",
            "price": 1999,
            "category": "wellness",
            "otc": True,
            "description": "Daily nutrition supplement for recovery, strength, and wellness goals.",
        },
        {
            "id": 20,
            "name": "Zincovit Tablet",
            "price": 120,
            "category": "wellness",
            "otc": True,
            "description": "Multivitamin support for general nutrition and recovery.",
        },
    ]


def seed_default_medicine_catalog() -> dict[str, int]:
    catalog = get_default_medicines()
    return {"seeded": len(catalog), "existing": 0, "mode": "fallback_catalog"}
