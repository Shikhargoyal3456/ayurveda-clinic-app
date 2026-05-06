from __future__ import annotations

from io import BytesIO
from typing import Any

import numpy as np

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


class AIImageAnalyzer:
    """Image symptom analysis with deterministic heuristics and optional model hooks."""

    def __init__(self) -> None:
        self.skin_model = self.load_model("models/skin_disease_model.h5")
        self.eye_model = self.load_model("models/eye_disease_model.h5")
        self.throat_model = self.load_model("models/throat_infection_model.h5")

    def load_model(self, path: str) -> object | None:
        return None

    async def analyze_symptom_image(self, image_file: Any, symptom_type: str) -> dict[str, Any]:
        image = self.preprocess_image(image_file)
        if symptom_type == "skin":
            prediction = await self.analyze_skin(image)
        elif symptom_type == "eye":
            prediction = await self.analyze_eye(image)
        elif symptom_type == "throat":
            prediction = await self.analyze_throat(image)
        else:
            prediction = await self.general_analysis(image)
        report = await self.generate_report(prediction)
        doctor_specialization = self.suggest_doctor(prediction, symptom_type)
        return {
            "symptom_type": symptom_type,
            "prediction": prediction,
            "confidence": prediction["confidence"],
            "possible_conditions": prediction["conditions"],
            "report": report,
            "recommended_doctor": doctor_specialization,
            "booking_link": f"/telemedicine/book?specialty={doctor_specialization}",
        }

    def preprocess_image(self, image_file: Any) -> np.ndarray:
        raw = image_file.read()
        if hasattr(image_file, "seek"):
            image_file.seek(0)
        if Image is not None:
            try:
                image = Image.open(BytesIO(raw)).convert("RGB").resize((64, 64))
                return np.asarray(image, dtype=np.float32) / 255.0
            except Exception:
                pass
        return np.ones((64, 64, 3), dtype=np.float32) * 0.5

    async def analyze_skin(self, image: np.ndarray) -> dict[str, Any]:
        redness = float(np.mean(image[:, :, 0]))
        dryness = float(np.std(image))
        conditions = ["Allergic Reaction", "Eczema", "Fungal Infection"] if redness > 0.55 else ["Acne", "Rosacea", "Psoriasis"]
        confidence = round(min(0.94, 0.62 + redness * 0.25 + dryness * 0.1), 2)
        return {"conditions": conditions, "confidence": confidence, "severity": self.calculate_severity(confidence), "urgency": "high" if confidence > 0.8 else "medium"}

    async def analyze_eye(self, image: np.ndarray) -> dict[str, Any]:
        brightness = float(np.mean(image))
        conditions = ["Conjunctivitis", "Eye Strain", "Dry Eye"] if brightness > 0.5 else ["Dry Eye", "Allergy", "Irritation"]
        confidence = round(min(0.91, 0.6 + brightness * 0.3), 2)
        return {"conditions": conditions, "confidence": confidence, "severity": self.calculate_severity(confidence), "urgency": "medium"}

    async def analyze_throat(self, image: np.ndarray) -> dict[str, Any]:
        tone = float(np.mean(image[:, :, 0] - image[:, :, 2]))
        conditions = ["Pharyngitis", "Tonsillitis", "Throat Irritation"] if tone > 0.0 else ["Viral Infection", "Throat Irritation", "Dryness"]
        confidence = round(min(0.9, 0.58 + abs(tone) * 0.5), 2)
        return {"conditions": conditions, "confidence": confidence, "severity": self.calculate_severity(confidence), "urgency": "medium"}

    async def general_analysis(self, image: np.ndarray) -> dict[str, Any]:
        confidence = round(min(0.85, 0.55 + float(np.mean(image)) * 0.3), 2)
        return {"conditions": ["General Inflammation", "Minor Irritation", "Needs Clinical Review"], "confidence": confidence, "severity": self.calculate_severity(confidence), "urgency": "medium"}

    async def generate_report(self, prediction: dict[str, Any]) -> str:
        return f"Top conditions: {', '.join(prediction['conditions'])}. Estimated urgency: {prediction['urgency']}."

    def suggest_doctor(self, prediction: dict[str, Any], symptom_type: str) -> str:
        mapping = {"skin": "dermatology", "eye": "ophthalmology", "throat": "ent"}
        return mapping.get(symptom_type, "general-medicine")

    def calculate_severity(self, confidence: float) -> str:
        if confidence > 0.82:
            return "high"
        if confidence > 0.68:
            return "medium"
        return "low"
