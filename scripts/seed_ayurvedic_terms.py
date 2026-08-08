from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SESSION_HTTPS_ONLY", "false")
os.environ.setdefault("HTTPS_REDIRECT_ENABLED", "false")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("APP_ENV", "testing")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import AyurTermCategory, AyurvedicTerm, PatientSamhitaQuery  # noqa: E402,F401


CATEGORIES = [
    {"name": "dosha", "icon": "fa-circle-nodes", "description": "Vata, Pitta, Kapha and related principles."},
    {"name": "disease", "icon": "fa-notes-medical", "description": "Classical disease terms and clinical entities."},
    {"name": "herb", "icon": "fa-leaf", "description": "Dravya, herbs, and materia medica terms."},
    {"name": "treatment", "icon": "fa-hand-holding-medical", "description": "Therapies, procedures, and chikitsa terms."},
    {"name": "anatomy", "icon": "fa-person", "description": "Sharira and anatomical concepts."},
]


AYURVEDIC_TERMS = [
    {
        "term": "Vata",
        "sanskrit_term": "वात",
        "ipa_pronunciation": "/ˈvɑːtə/",
        "category": "dosha",
        "samhita": "Charaka Samhita",
        "chapter": "Sutra Sthana",
        "verse_number": "1.3.5",
        "verse_sanskrit": "वातः पित्तं कफश्चेति त्रयो दोषाः...",
        "verse_translation": "Vata, Pitta, and Kapha are the three doshas.",
        "commentary_name": "Chakrapani",
        "commentary_text": "वातः शरीरे चेष्टाकारकः...",
        "commentary_translation": "Vata is responsible for movement in the body.",
        "meaning": "The biological air principle governing movement.",
        "clinical_significance": "Vata imbalance is associated with neurological, musculoskeletal, and gastrointestinal disorders.",
        "pronunciation_guide": "VAH-tah",
    },
    {
        "term": "Pitta",
        "sanskrit_term": "पित्त",
        "ipa_pronunciation": "/ˈpɪtə/",
        "category": "dosha",
        "samhita": "Charaka Samhita",
        "chapter": "Sutra Sthana",
        "verse_number": "1.3.6",
        "verse_sanskrit": "पित्तं पाचकमग्निरूपं...",
        "verse_translation": "Pitta is connected with digestive fire.",
        "commentary_name": "Chakrapani",
        "commentary_text": "पित्तं दाहकारकं...",
        "commentary_translation": "Pitta causes heat, digestion, and transformation.",
        "meaning": "The biological fire principle governing metabolism.",
        "clinical_significance": "Pitta imbalance is associated with inflammatory, digestive, and skin disorders.",
        "pronunciation_guide": "PIT-tah",
    },
    {
        "term": "Kapha",
        "sanskrit_term": "कफ",
        "ipa_pronunciation": "/ˈkʌfə/",
        "category": "dosha",
        "samhita": "Charaka Samhita",
        "chapter": "Sutra Sthana",
        "verse_number": "1.3.7",
        "verse_sanskrit": "कफः स्नेहनः...",
        "verse_translation": "Kapha provides lubrication and stability.",
        "commentary_name": "Chakrapani",
        "commentary_text": "कफः बलकरः...",
        "commentary_translation": "Kapha provides strength and immunity.",
        "meaning": "The biological water principle governing structure.",
        "clinical_significance": "Kapha imbalance is associated with respiratory, lymphatic, and metabolic disorders.",
        "pronunciation_guide": "KUH-fah",
    },
    {
        "term": "Jwara",
        "sanskrit_term": "ज्वर",
        "ipa_pronunciation": "/ˈdʒwɑːrə/",
        "category": "disease",
        "samhita": "Charaka Samhita",
        "chapter": "Chikitsa Sthana",
        "verse_number": "3.1.1",
        "verse_sanskrit": "ज्वरः सर्वरोगाणां मुखं...",
        "verse_translation": "Fever is described as a gateway among diseases.",
        "commentary_name": "Chakrapani",
        "commentary_text": "ज्वरः दोषदूष्यसंमूर्च्छनाजन्यः...",
        "commentary_translation": "Fever arises from interaction of vitiated dosha and affected tissues.",
        "meaning": "Fever or febrile illness.",
        "clinical_significance": "Jwara is a major classical disease category requiring dosha and stage assessment.",
        "pronunciation_guide": "JWAH-rah",
    },
    {
        "term": "Madhumeha",
        "sanskrit_term": "मधुमेह",
        "ipa_pronunciation": "/mɑːˈdʰuːmeɪhɑː/",
        "category": "disease",
        "samhita": "Charaka Samhita",
        "chapter": "Chikitsa Sthana",
        "verse_number": "6.1.1",
        "verse_sanskrit": "मधुमेहः सर्वमेहानां मूलं...",
        "verse_translation": "Madhumeha is discussed among urinary disorders.",
        "commentary_name": "Chakrapani",
        "commentary_text": "मधुमेही क्षीणः...",
        "commentary_translation": "The Madhumeha patient may show depletion and chronicity.",
        "meaning": "Diabetes mellitus, traditionally associated with honey-like urine.",
        "clinical_significance": "Madhumeha is treated as a serious prameha subtype with metabolic implications.",
        "pronunciation_guide": "MAH-dhu-may-ha",
    },
    {
        "term": "Ashwagandha",
        "sanskrit_term": "अश्वगन्धा",
        "ipa_pronunciation": "/əʃwəˈɡʌndhə/",
        "category": "herb",
        "samhita": "Charaka Samhita",
        "chapter": "Sutra Sthana",
        "verse_number": "1.4.15",
        "verse_sanskrit": "अश्वगन्धा वृष्या...",
        "verse_translation": "Ashwagandha is described as strengthening and rejuvenative.",
        "commentary_name": "Chakrapani",
        "commentary_text": "अश्वगन्धा बल्या...",
        "commentary_translation": "Ashwagandha supports strength and nourishment.",
        "meaning": "Winter cherry, Indian ginseng.",
        "clinical_significance": "Used for stress resilience, strength, sleep, vitality, and tissue nourishment.",
        "pronunciation_guide": "ASH-wa-gun-dha",
    },
    {
        "term": "Marma",
        "sanskrit_term": "मर्म",
        "ipa_pronunciation": "/ˈmɑːrmə/",
        "category": "anatomy",
        "samhita": "Sushruta Samhita",
        "chapter": "Sharir Sthana",
        "verse_number": "6.1.1",
        "verse_sanskrit": "मर्माणि प्राणस्थानानि...",
        "verse_translation": "Marma are vital points associated with life force.",
        "commentary_name": "Dalhana",
        "commentary_text": "मर्मभ्यो हि प्राणाः...",
        "commentary_translation": "Vitality is protected through the marma points.",
        "meaning": "Vital anatomical points.",
        "clinical_significance": "Marma injury can cause severe pain, disability, or danger to life.",
        "pronunciation_guide": "MAR-mah",
    },
    {
        "term": "Panchakarma",
        "sanskrit_term": "पञ्चकर्म",
        "ipa_pronunciation": "/pʌntʃəˈkɑːrmə/",
        "category": "treatment",
        "samhita": "Charaka Samhita",
        "chapter": "Siddhi Sthana",
        "verse_number": "1.1.1",
        "verse_sanskrit": "पञ्चकर्माणि शुद्ध्यर्थं...",
        "verse_translation": "Panchakarma is used for purification.",
        "commentary_name": "Chakrapani",
        "commentary_text": "पञ्चकर्माणि दोषहराणि...",
        "commentary_translation": "Panchakarma removes vitiated doshas.",
        "meaning": "Five therapeutic procedures for purification.",
        "clinical_significance": "A major treatment framework for chronic and deep-seated dosha imbalance.",
        "pronunciation_guide": "PUN-cha-kar-ma",
    },
]


def main() -> int:
    Base.metadata.create_all(bind=engine, tables=[AyurvedicTerm.__table__, AyurTermCategory.__table__, PatientSamhitaQuery.__table__])
    db = SessionLocal()
    try:
        for category in CATEGORIES:
            existing = db.query(AyurTermCategory).filter(AyurTermCategory.name == category["name"]).first()
            if existing:
                for key, value in category.items():
                    setattr(existing, key, value)
            else:
                db.add(AyurTermCategory(**category))

        for item in AYURVEDIC_TERMS:
            existing = db.query(AyurvedicTerm).filter(AyurvedicTerm.term == item["term"]).first()
            if existing:
                for key, value in item.items():
                    setattr(existing, key, value)
            else:
                db.add(AyurvedicTerm(**item))

        db.commit()
        print(f"Seeded {len(CATEGORIES)} categories and {len(AYURVEDIC_TERMS)} Ayurvedic terms.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
