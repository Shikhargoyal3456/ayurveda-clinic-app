from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy import insert

from app.database import SessionLocal, engine
from services.automation_tables import ai_processing_logs_table, ensure_automation_tables, support_tickets_table
from services.feature_flags import is_ai_automation_enabled


logger = logging.getLogger(__name__)


class AISupportAutomation:
    """AI-powered customer support without replacing existing system."""

    def __init__(self) -> None:
        self.intent_patterns = {
            "order_status": [r"where is my order", r"order status", r"tracking"],
            "refund": [r"refund", r"return", r"money back"],
            "medicine_info": [r"how to take", r"dosage", r"side effects"],
            "delivery": [r"delivery time", r"when will i get", r"shipping"],
            "cancellation": [r"cancel order", r"stop delivery"],
        }
        ensure_automation_tables()

    async def auto_respond_to_query(self, user_query: str, user_context: dict[str, Any]) -> dict[str, Any]:
        if not is_ai_automation_enabled():
            return {
                "detected_intent": None,
                "auto_response": "AI automation is disabled. A human agent will assist you.",
                "needs_human": True,
                "confidence": 0.0,
            }

        intent = self._detect_intent(user_query)
        response_templates = {
            "order_status": f"Your order #{user_context.get('last_order_id', 'N/A')} is being processed. Track it from your recent orders dashboard.",
            "refund": "Refunds are usually processed within 5-7 business days. I can help log a refund request for review.",
            "medicine_info": "For medicine-specific advice, please follow your doctor's prescription. You can also review our health library for general guidance.",
            "delivery": f"Standard delivery takes 3-5 days. Based on your current flow, the order should arrive by {self._calculate_eta()}",
            "cancellation": "Orders can usually be cancelled within 1 hour of placement if fulfillment has not started yet.",
        }
        result = {
            "detected_intent": intent,
            "auto_response": response_templates.get(intent, "I'll connect you to a human agent shortly."),
            "needs_human": intent is None,
            "confidence": 0.85 if intent else 0.3,
        }
        self._log_decision("support_query", int(user_context.get("user_id", 0) or 0), "auto_respond", result, result["confidence"])
        return result

    async def auto_ticket_routing(self, ticket_data: dict[str, Any]) -> dict[str, Any]:
        content = str(ticket_data.get("message", "")).lower()
        department = "general"
        if any(word in content for word in ["payment", "refund", "money"]):
            department = "billing"
        elif any(word in content for word in ["medicine", "prescription", "doctor"]):
            department = "clinical"
        elif any(word in content for word in ["delivery", "shipping", "courier"]):
            department = "logistics"

        result = {
            "ticket_id": ticket_data.get("id"),
            "assigned_department": department,
            "priority": "high" if "urgent" in content else "normal",
            "auto_assigned": True,
        }
        self._store_ticket(ticket_data, result)
        self._log_decision("support_ticket", int(ticket_data.get("id", 0) or 0), "route", result, 0.81)
        return result

    async def auto_suggest_help_articles(self, query: str) -> list[dict[str, Any]]:
        needle = str(query or "").lower()
        articles = [
            {"title": "How to track your order", "url": "/help/tracking", "relevance": 0.95},
            {"title": "Understanding medicine delivery", "url": "/help/delivery", "relevance": 0.87},
            {"title": "Return and refund policy", "url": "/help/refunds", "relevance": 0.76},
        ]
        if "refund" in needle:
            return sorted(articles, key=lambda item: item["title"] != "Return and refund policy")
        return articles

    def _detect_intent(self, user_query: str) -> str | None:
        query = str(user_query or "").strip().lower()
        for intent, patterns in self.intent_patterns.items():
            if any(re.search(pattern, query) for pattern in patterns):
                return intent
        return None

    def _calculate_eta(self) -> str:
        from datetime import datetime, timedelta

        return (datetime.now() + timedelta(days=3)).strftime("%d %b")

    def _store_ticket(self, ticket_data: dict[str, Any], routed: dict[str, Any]) -> None:
        try:
            ensure_automation_tables()
            payload = {
                "user_id": int(ticket_data.get("user_id", 0) or 0),
                "query": str(ticket_data.get("message", "")),
                "ai_response": json.dumps(routed, ensure_ascii=True),
                "assigned_department": str(routed.get("assigned_department", "general")),
                "status": "open",
            }
            with engine.begin() as connection:
                connection.execute(insert(support_tickets_table).values(**payload))
        except Exception as exc:
            logger.warning("Support ticket persistence skipped: %s", exc)

    def _log_decision(self, entity_type: str, entity_id: int, action: str, decision: dict[str, Any], confidence: float) -> None:
        try:
            ensure_automation_tables()
            payload = {
                "entity_type": entity_type,
                "entity_id": int(entity_id or 0),
                "action": action,
                "ai_decision": json.dumps(decision, ensure_ascii=True),
                "confidence": float(confidence),
            }
            with engine.begin() as connection:
                connection.execute(insert(ai_processing_logs_table).values(**payload))
        except Exception as exc:
            logger.warning("AI support decision log skipped for %s:%s: %s", entity_type, entity_id, exc)
