from __future__ import annotations

from pathlib import Path
from typing import Any

import requests
from sqlalchemy.orm import Session

from models.medicine import MasterMedicine

try:  # pragma: no cover - optional dependency in local envs
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


class AIMedicineImageRecognition:
    """Best-effort medicine image recognition with graceful fallback."""

    def __init__(self) -> None:
        self.model = None
        self._decode_predictions = None
        try:  # pragma: no cover - depends on local model availability
            import numpy as np
            import tensorflow as tf

            self._np = np
            self.model = tf.keras.applications.MobileNetV2(weights="imagenet")
            self._preprocess_input = tf.keras.applications.mobilenet_v2.preprocess_input
            self._decode_predictions = tf.keras.applications.mobilenet_v2.decode_predictions
        except Exception:
            self._np = None
            self._preprocess_input = None

    def identify_medicine_from_image(self, image_url: str, db: Session) -> dict[str, Any]:
        labels = self._predict_labels(image_url)
        suggestions = self.match_with_database(labels, db)
        confidence = float(labels[0]["confidence"]) if labels else 0.0
        return {
            "detected_labels": labels,
            "suggested_medicines": suggestions,
            "confidence_score": confidence,
        }

    def _predict_labels(self, image_url: str) -> list[dict[str, Any]]:
        heuristic_labels = self._heuristic_labels(image_url)
        if self.model is None or self._np is None or self._decode_predictions is None or self._preprocess_input is None or Image is None:
            return heuristic_labels
        try:  # pragma: no cover - expensive path
            response = requests.get(image_url, timeout=8)
            response.raise_for_status()
            img = Image.open(__import__("io").BytesIO(response.content)).convert("RGB")
            img = img.resize((224, 224))
            img_array = self._np.array(img, dtype="float32")
            img_array = self._np.expand_dims(img_array, axis=0)
            img_array = self._preprocess_input(img_array)
            predictions = self.model.predict(img_array, verbose=0)
            decoded = self._decode_predictions(predictions, top=3)[0]
            return [{"name": label[1].replace("_", " "), "confidence": float(label[2])} for label in decoded] or heuristic_labels
        except Exception:
            return heuristic_labels

    def _heuristic_labels(self, image_url: str) -> list[dict[str, Any]]:
        filename = Path(image_url).name.lower()
        tokens = [token.replace("-", " ").replace("_", " ") for token in filename.split(".")[0].split()]
        labels = [{"name": token, "confidence": 0.42} for token in tokens if token]
        if not labels:
            labels = [{"name": "medicine package", "confidence": 0.35}]
        return labels[:3]

    def match_with_database(self, labels: list[dict[str, Any]], db: Session) -> list[dict[str, Any]]:
        if not labels:
            return []
        suggestions: list[dict[str, Any]] = []
        for label in labels:
            like = f"%{label['name']}%"
            rows = (
                db.query(MasterMedicine)
                .filter(
                    MasterMedicine.is_active.is_(True),
                    (MasterMedicine.name.ilike(like)) | (MasterMedicine.brand.ilike(like)) | (MasterMedicine.generic_name.ilike(like)),
                )
                .limit(3)
                .all()
            )
            for item in rows:
                if item.id not in {existing["id"] for existing in suggestions}:
                    suggestions.append(
                        {
                            "id": item.id,
                            "name": item.name,
                            "brand": item.brand or "",
                            "price": float(item.price or item.mrp or 0),
                            "category": item.category,
                            "match_reason": label["name"],
                        }
                    )
        return suggestions[:5]
