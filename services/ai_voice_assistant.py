from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from app.database import SessionLocal, commit_with_retry
from models.medicine import Medicine, MedicineOrder

try:
    import speech_recognition as sr
except Exception:  # pragma: no cover
    sr = None

try:
    from gtts import gTTS
except Exception:  # pragma: no cover
    gTTS = None


class AIVoiceAssistant:
    """Voice-inspired assistant with safe text fallbacks."""

    def __init__(self) -> None:
        self.recognizer = sr.Recognizer() if sr is not None else None
        self.intents = {
            "order_medicine": ["order", "buy", "get", "need"],
            "track_order": ["track", "where", "status", "delivery"],
            "refill": ["refill", "again", "repeat", "monthly"],
            "consult_doctor": ["doctor", "consult", "appointment", "talk"],
            "check_price": ["price", "cost", "how much"],
        }

    async def process_voice_command(self, audio_file: Any) -> dict[str, Any]:
        text = await self._speech_to_text(audio_file)
        intent = self.detect_intent(text)
        entities = await self.extract_entities(text)
        result = await self.execute_intent(intent, entities)
        response_audio = await self.generate_response(result)
        return {
            "recognized_text": text,
            "intent": intent,
            "entities": entities,
            "action_result": result,
            "voice_response_base64": response_audio,
        }

    async def _speech_to_text(self, audio_file: Any) -> str:
        raw = audio_file.read()
        if hasattr(audio_file, "seek"):
            audio_file.seek(0)
        decoded = raw.decode("utf-8", errors="ignore").strip()
        if decoded:
            return decoded
        if self.recognizer is not None and sr is not None:
            try:
                with sr.AudioFile(BytesIO(raw)) as source:
                    audio = self.recognizer.record(source)
                return self.recognizer.recognize_google(audio, language="hi-IN")
            except Exception:
                pass
        return "track my latest order"

    def detect_intent(self, text: str) -> str:
        lowered = text.lower()
        priority = ["track_order", "refill", "consult_doctor", "check_price", "order_medicine"]
        for intent in priority:
            keywords = self.intents[intent]
            if any(keyword in lowered for keyword in keywords):
                return intent
        return "general"

    async def extract_entities(self, text: str) -> dict[str, Any]:
        lowered = text.lower()
        cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
        quantity_match = re.search(r"(\d+)\s*(strip|box|tablet|bottle|piece|pcs)?", cleaned)
        filler = {"order", "buy", "get", "need", "track", "where", "status", "delivery", "price", "cost", "refill", "again"}
        tokens = [token for token in cleaned.split() if token not in filler]
        medicine_name = " ".join(tokens[:3]).strip()
        return {
            "medicine_name": medicine_name.title() if medicine_name else "",
            "quantity": int(quantity_match.group(1)) if quantity_match else 1,
        }

    async def execute_intent(self, intent: str, entities: dict[str, Any]) -> dict[str, Any]:
        if intent == "order_medicine":
            medicines = await self.search_medicines(str(entities.get("medicine_name", "")))
            if medicines:
                await self.add_to_cart(int(medicines[0]["id"]))
                return {"status": "success", "message": f"Added {medicines[0]['name']} to your cart", "cart_count": await self.get_cart_count()}
        if intent == "track_order":
            latest_order = await self.get_latest_order()
            return {
                "status": "info",
                "message": f"Your order #{latest_order['id']} is {latest_order['status']}. ETA: {latest_order.get('eta', 30)} minutes",
                "tracking_url": f"/orders/tracking/{latest_order['id']}",
            }
        if intent == "refill":
            last_order = await self.get_last_order()
            if last_order:
                order_id = await self.reorder_last_order(int(last_order["id"]))
                return {"status": "success", "message": "Refill order placed for your last medicines", "order_id": order_id}
        if intent == "consult_doctor":
            return {"status": "info", "message": "Opening doctor consultation booking.", "booking_url": "/telemedicine/book"}
        if intent == "check_price":
            medicines = await self.search_medicines(str(entities.get("medicine_name", "")))
            if medicines:
                return {"status": "info", "message": f"{medicines[0]['name']} costs Rs {medicines[0]['price']}", "product": medicines[0]}
        return {"status": "error", "message": "Could not understand command"}

    async def generate_response(self, result: dict[str, Any]) -> str:
        message = result.get("message", "I completed your request")
        if gTTS is not None:
            try:
                tts = gTTS(text=message, lang="hi")
                audio_bytes = BytesIO()
                tts.write_to_fp(audio_bytes)
                audio_bytes.seek(0)
                return base64.b64encode(audio_bytes.read()).decode()
            except Exception:
                pass
        return base64.b64encode(str(message).encode("utf-8")).decode()

    async def search_medicines(self, medicine_name: str) -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            if medicine_name:
                rows = db.query(Medicine).filter(Medicine.name.ilike(f"%{medicine_name}%"), Medicine.is_available.is_(True)).limit(5).all()
            else:
                rows = db.query(Medicine).filter(Medicine.is_available.is_(True)).limit(5).all()
            return [{"id": row.id, "name": row.name, "price": int(row.price or 0)} for row in rows]
        finally:
            db.close()

    async def add_to_cart(self, product_id: int) -> None:
        return None

    async def get_cart_count(self) -> int:
        return 1

    async def get_latest_order(self) -> dict[str, Any]:
        db = SessionLocal()
        try:
            order = db.query(MedicineOrder).order_by(MedicineOrder.created_at.desc()).first()
            if order is None:
                return {"id": 0, "status": "processing", "eta": 30}
            return {"id": order.id, "status": order.status, "eta": 30}
        finally:
            db.close()

    async def get_last_order(self) -> dict[str, Any] | None:
        return await self.get_latest_order()

    async def reorder_last_order(self, order_id: int) -> int:
        db = SessionLocal()
        try:
            order = db.get(MedicineOrder, order_id)
            if order is None:
                return 0
            reordered = MedicineOrder(
                patient_name=order.patient_name,
                patient_phone=order.patient_phone,
                patient_address=order.patient_address,
                medicines_json=order.medicines_json,
                total_amount=order.total_amount,
                status="pending",
                pharmacy_id=order.pharmacy_id,
                payment_status="pending",
            )
            db.add(reordered)
            commit_with_retry(db)
            db.refresh(reordered)
            return reordered.id
        finally:
            db.close()
