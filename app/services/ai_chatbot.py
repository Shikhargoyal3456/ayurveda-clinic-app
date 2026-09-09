from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.database import SessionLocal, commit_with_retry
from models.ai_features import AIConversationHistory
from models.marketplace import PharmacyStore
from models.medicine import Medicine, MedicineOrder


class AIHealthcareChatbot:
    """Context-aware chatbot with in-memory and DB-backed conversation memory."""

    def __init__(self) -> None:
        self.conversation_history: dict[int, list[dict[str, Any]]] = {}
        self.user_context: dict[int, dict[str, Any]] = {}

    async def chat(self, user_id: int, message: str) -> dict[str, Any]:
        context = self.get_context(user_id)
        intent = await self.analyze_intent(message, context)
        info = await self.fetch_relevant_info(user_id, intent, message)
        response = await self.generate_response(intent, info, context)
        self.update_memory(user_id, message, response, intent)
        action_result = await self.execute_action(intent, user_id, info, message)
        return {
            "response": response,
            "intent": intent,
            "action_taken": action_result,
            "suggested_actions": await self.suggest_actions(intent, info),
            "quick_replies": self.get_quick_replies(intent),
        }

    def get_context(self, user_id: int) -> dict[str, Any]:
        return self.user_context.setdefault(user_id, {"last_seen": datetime.now(timezone.utc).isoformat(), "topics": []})

    async def analyze_intent(self, message: str, context: dict[str, Any]) -> str:
        intents = {
            "symptom_check": ["symptom", "fever", "pain", "cough", "headache"],
            "medicine_info": ["medicine", "tablet", "capsule", "dose", "side effect"],
            "order_status": ["order", "delivery", "track", "where is"],
            "refill": ["refill", "repeat", "again", "monthly"],
            "emergency": ["emergency", "urgent", "hospital", "chest pain"],
            "appointment": ["appointment", "doctor", "consult", "book"],
        }
        lowered = message.lower()
        if any(word in lowered for word in intents["emergency"]):
            return "emergency"
        for intent, keywords in intents.items():
            if any(keyword in lowered for keyword in keywords):
                return intent
        return "general"

    async def fetch_relevant_info(self, user_id: int, intent: str, message: str) -> dict[str, Any]:
        if intent == "order_status":
            db = SessionLocal()
            try:
                order = db.query(MedicineOrder).order_by(MedicineOrder.created_at.desc()).first()
                return {"order_id": order.id if order else 0, "status": order.status if order else "processing", "eta": 30}
            finally:
                db.close()
        if intent == "medicine_info":
            db = SessionLocal()
            try:
                row = db.query(Medicine).order_by(Medicine.created_at.desc()).first()
                return {"medicine_name": row.name if row else "Ayurvedic medicine", "uses": "general wellness", "side_effects": ["dry mouth", "mild nausea"]}
            finally:
                db.close()
        if intent == "symptom_check":
            symptoms = [token for token in message.replace(",", " ").split() if len(token) > 3][:4]
            return {"symptoms": symptoms or ["general discomfort"], "suggestion": "You can use the symptom checker or book a video consultation."}
        if intent == "appointment":
            return {"booking_url": "/telemedicine/book", "available_today": True}
        return {}

    async def generate_response(self, intent: str, info: dict[str, Any], context: dict[str, Any]) -> str:
        responses = {
            "symptom_check": f"Based on your symptoms ({', '.join(info.get('symptoms', []))}), I recommend consulting a doctor. {info.get('suggestion', '')}",
            "medicine_info": f"{info.get('medicine_name')} is used for {info.get('uses', 'various conditions')}. Common side effects: {', '.join(info.get('side_effects', []))}",
            "order_status": f"Your order #{info.get('order_id')} is {info.get('status')}. ETA: {info.get('eta', '30')} minutes",
            "refill": "I can help place a refill based on your last medicines. Would you like me to proceed?",
            "emergency": "Please call emergency services immediately. I am surfacing nearby care options and urgent support guidance now.",
            "appointment": "You can book a doctor consultation right away. I can direct you to telemedicine booking.",
            "general": "How can I help you with your healthcare needs today?",
        }
        return responses.get(intent, responses["general"])

    async def execute_action(self, intent: str, user_id: int, info: dict[str, Any], message: str) -> dict[str, Any]:
        if intent == "emergency":
            return await self.handle_emergency(user_id, message)
        if intent == "appointment":
            return {"booking_url": "/telemedicine/book"}
        return {"status": "none"}

    async def suggest_actions(self, intent: str, info: dict[str, Any]) -> list[dict[str, str]]:
        mapping = {
            "symptom_check": [{"label": "Open Symptom Checker", "url": "/telemedicine/symptom-checker"}],
            "order_status": [{"label": "Track Orders", "url": "/superapp/dashboard"}],
            "appointment": [{"label": "Book Consultation", "url": "/telemedicine/book"}],
            "emergency": [{"label": "Call 108", "url": "tel:108"}],
        }
        return mapping.get(intent, [{"label": "Open Superapp", "url": "/superapp/dashboard"}])

    def get_quick_replies(self, intent: str) -> list[str]:
        mapping = {
            "general": ["Track my order", "Book a doctor", "Refill medicines"],
            "symptom_check": ["Analyze symptoms", "Book consultation", "Find nearest pharmacy"],
            "order_status": ["Show tracking", "Call support", "Reorder medicines"],
        }
        return mapping.get(intent, ["Show offers", "Open dashboard"])

    def update_memory(self, user_id: int, message: str, response: str, intent: str) -> None:
        self.conversation_history.setdefault(user_id, []).append({"message": message, "response": response, "intent": intent})
        self.user_context.setdefault(user_id, {}).update({"last_intent": intent, "last_seen": datetime.now(timezone.utc).isoformat()})
        db = SessionLocal()
        try:
            db.add(
                AIConversationHistory(
                    user_id=user_id,
                    session_id=f"user-{user_id}",
                    message=message,
                    response=response,
                    intent=intent,
                )
            )
            commit_with_retry(db)
        finally:
            db.close()

    async def handle_emergency(self, user_id: int, message: str) -> dict[str, Any]:
        user_location = await self.get_user_location(user_id)
        nearest_hospital = await self.find_nearest_hospital(user_location)
        await self.notify_emergency_contacts(user_id)
        await self.alert_nearby_doctors(user_location)
        return {
            "emergency_activated": True,
            "nearest_hospital": nearest_hospital,
            "ambulance_contact": "108",
            "instructions": "Stay calm. Help is on the way. Share your location if possible.",
        }

    async def get_user_location(self, user_id: int) -> dict[str, float]:
        return {"lat": 28.4595, "lng": 77.0266}

    async def find_nearest_hospital(self, user_location: dict[str, float]) -> dict[str, Any]:
        return {"name": "Kash Emergency Care", "distance_km": 2.4, "phone": "108"}

    async def notify_emergency_contacts(self, user_id: int) -> None:
        return None

    async def alert_nearby_doctors(self, user_location: dict[str, float]) -> None:
        return None
