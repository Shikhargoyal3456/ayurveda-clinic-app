from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

import requests


class AIFallback:
    def __init__(self, cache_path: Path | None = None, ttl_seconds: int = 24 * 3600, max_items: int = 100) -> None:
        base_dir = Path(__file__).resolve().parent.parent
        self.cache_path = cache_path or (base_dir / "data" / "ai_cache.json")
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._knowledge = self._build_knowledge_base()
        self._load_cache()

    def _build_knowledge_base(self) -> dict[str, Any]:
        return {
            "doshas": {
                "vata": {
                    "description": "Vata governs movement, the nervous system, circulation, and dryness.",
                    "symptoms": ["anxiety", "bloating", "constipation", "dry skin", "insomnia", "joint pain"],
                    "recommendations": [
                        "Favor warm cooked meals and regular daily routines.",
                        "Use sesame oil massage and grounding breathing practices.",
                        "Reduce excessive fasting, travel, and late nights.",
                    ],
                },
                "pitta": {
                    "description": "Pitta governs transformation, digestion, heat, and intensity.",
                    "symptoms": ["acidity", "burning sensation", "irritability", "loose stools", "skin rashes"],
                    "recommendations": [
                        "Favor cooling foods, coriander, fennel, and adequate hydration.",
                        "Reduce spicy, oily, sour, and fermented foods.",
                        "Protect sleep and manage overwork or anger triggers.",
                    ],
                },
                "kapha": {
                    "description": "Kapha governs stability, structure, lubrication, and immunity.",
                    "symptoms": ["lethargy", "heaviness", "mucus", "slow digestion", "water retention"],
                    "recommendations": [
                        "Favor light warm meals, movement, and stimulating spices.",
                        "Reduce excess dairy, sugar, fried food, and oversleeping.",
                        "Use brisk walking, pranayama, and decongesting herbs.",
                    ],
                },
            },
            "herbs": {
                "ashwagandha": {
                    "uses": "Adaptogenic support for stress, sleep, energy, and recovery.",
                    "dosage": "Commonly 250-600 mg extract once or twice daily, clinician adjusted.",
                    "precautions": "Use caution in hyperthyroid states, pregnancy, and with sedative medication.",
                },
                "triphala": {
                    "uses": "Supports bowel regularity, digestion, and gentle detox routines.",
                    "dosage": "Commonly 500-1000 mg at bedtime with warm water, clinician adjusted.",
                    "precautions": "Use caution with diarrhea, dehydration, or very weak digestion.",
                },
                "tulsi": {
                    "uses": "Supports immunity, respiratory comfort, and stress resilience.",
                    "dosage": "Tea or extract once to twice daily based on formulation.",
                    "precautions": "Use caution with blood-thinning medication and pregnancy without supervision.",
                },
                "brahmi": {
                    "uses": "Supports focus, mental calm, memory, and stress modulation.",
                    "dosage": "Commonly 250-500 mg extract daily, clinician adjusted.",
                    "precautions": "Use caution with sedatives and monitor digestion in sensitive patients.",
                },
            },
            "concerns": {
                "digestion": "Support agni with freshly cooked meals, mindful eating, ginger-coriander-fennel style support, and avoidance of overeating.",
                "stress": "Use regular sleep timing, breathwork, abhyanga, nervous-system support, and adaptogenic herbs when appropriate.",
                "sleep": "Use consistent bedtime, warm evening routines, calming herbs, reduced screen stimulation, and clinician review of chronic insomnia.",
                "immunity": "Use adequate sleep, digestive correction, warm hydration, moderate exercise, and immune-supportive herbs like tulsi or guduchi when appropriate.",
            },
        }

    def _load_cache(self) -> None:
        if not self.cache_path.exists():
            return
        try:
            raw_data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if isinstance(raw_data, list):
                for item in raw_data:
                    key = str(item.get("key", ""))
                    if key:
                        self._cache[key] = item
            self._purge_expired()
        except Exception:
            self._cache.clear()

    def _save_cache(self) -> None:
        self.cache_path.write_text(json.dumps(list(self._cache.values()), indent=2, ensure_ascii=True), encoding="utf-8")

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [key for key, value in self._cache.items() if float(value.get("expires_at", 0)) <= now]
        for key in expired:
            self._cache.pop(key, None)

    def _cache_key(self, query: str, context: str) -> str:
        payload = f"{query.strip().lower()}::{context.strip().lower()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _lookup(self, cache_key: str) -> dict[str, Any] | None:
        self._purge_expired()
        item = self._cache.get(cache_key)
        if item is None:
            self._misses += 1
            return None
        self._cache.move_to_end(cache_key)
        self._hits += 1
        return dict(item["payload"])

    def _remember(self, cache_key: str, payload: dict[str, Any]) -> None:
        self._purge_expired()
        if cache_key in self._cache:
            self._cache.pop(cache_key)
        while len(self._cache) >= self.max_items:
            self._cache.popitem(last=False)
            self._evictions += 1
        self._cache[cache_key] = {
            "key": cache_key,
            "created_at": time.time(),
            "expires_at": time.time() + self.ttl_seconds,
            "payload": payload,
        }
        self._save_cache()

    def _match_topics(self, query: str, context: str) -> list[str]:
        haystack = f"{query} {context}".lower()
        topics: list[str] = []
        for dosha_name, dosha_data in self._knowledge["doshas"].items():
            if dosha_name in haystack or any(symptom in haystack for symptom in dosha_data["symptoms"]):
                topics.append(dosha_name)
        for concern in self._knowledge["concerns"]:
            if concern in haystack:
                topics.append(concern)
        for herb in self._knowledge["herbs"]:
            if herb in haystack:
                topics.append(herb)
        return topics or ["general"]

    def _build_response_text(self, query: str, context: str) -> str:
        haystack = f"{query} {context}".lower()
        lines: list[str] = []
        if any(term in haystack for term in ("stress", "anxiety", "sleep", "insomnia")):
            lines.append("Focus: Vata-pacifying support with regular routines, grounding meals, and calming herbs.")
        if any(term in haystack for term in ("burning", "acidity", "heat", "inflammation")):
            lines.append("Focus: Pitta-balancing support with cooling foods, hydration, and reduced spicy intake.")
        if any(term in haystack for term in ("mucus", "cold", "heaviness", "weight", "slow digestion")):
            lines.append("Focus: Kapha-reducing support with light meals, movement, and warming spices.")

        if "digestion" in haystack or "acidity" in haystack or "bloating" in haystack:
            lines.append(f"Digestion: {self._knowledge['concerns']['digestion']}")
        if "stress" in haystack or "anxiety" in haystack:
            lines.append(f"Stress: {self._knowledge['concerns']['stress']}")
        if "sleep" in haystack or "insomnia" in haystack:
            lines.append(f"Sleep: {self._knowledge['concerns']['sleep']}")
        if "immunity" in haystack or "cold" in haystack:
            lines.append(f"Immunity: {self._knowledge['concerns']['immunity']}")

        herbs = []
        if any(term in haystack for term in ("stress", "anxiety", "sleep")):
            herbs.extend(["ashwagandha", "brahmi"])
        if any(term in haystack for term in ("digestion", "bloating", "constipation")):
            herbs.append("triphala")
        if any(term in haystack for term in ("immunity", "cold", "cough", "respiratory")):
            herbs.append("tulsi")
        if not herbs:
            herbs = ["ashwagandha", "triphala", "tulsi", "brahmi"]

        for herb_name in dict.fromkeys(herbs):
            herb = self._knowledge["herbs"][herb_name]
            lines.append(
                f"{herb_name.title()}: {herb['uses']} Dosage: {herb['dosage']} Precautions: {herb['precautions']}"
            )

        if not lines:
            lines.append("General Ayurvedic guidance: assess agni, ama, bowel pattern, sleep, stress, and dominant dosha before giving tailored advice.")
        lines.append("This fallback response is educational support and not a substitute for clinician judgment.")
        return "\n".join(lines)

    def get_response(self, query: str, context: str = "") -> dict[str, Any]:
        cache_key = self._cache_key(query, context)
        cached = self._lookup(cache_key)
        if cached is not None:
            return cached

        payload = {
            "response": self._build_response_text(query, context),
            "source": "fallback",
            "topics": self._match_topics(query, context),
            "generated_at": int(time.time()),
        }
        self._remember(cache_key, payload)
        return payload

    def get_status(self) -> dict[str, Any]:
        self._purge_expired()
        return {
            "cache_size": len(self._cache),
            "max_items": self.max_items,
            "ttl_seconds": self.ttl_seconds,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "cache_path": str(self.cache_path),
        }


fallback_handler = AIFallback()


def fallback_health_status(probe_remote: bool = False) -> dict[str, Any]:
    if not probe_remote:
        return {
            "available": False,
            "checked": False,
            "mode": "probe_skipped",
        }
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return {"available": response.status_code < 500, "status_code": response.status_code, "checked": True}
    except requests.RequestException as exc:
        return {"available": False, "error": str(exc), "checked": True}
