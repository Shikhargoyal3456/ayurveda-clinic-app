from __future__ import annotations

from typing import Any

from app.analytics import track_event


class MarketingAutomation:
    def send_abandoned_cart_reminder(self, user_id: str, cart_items: list[str]) -> dict[str, Any]:
        track_event("marketing_abandoned_cart_sent", user_id=user_id, item_count=len(cart_items))
        return {
            "success": True,
            "channel": ["whatsapp", "email"],
            "message": f"Cart reminder prepared for {len(cart_items)} items.",
        }

    def send_refill_reminder(self, user_id: str, subscription: dict[str, Any]) -> dict[str, Any]:
        track_event("marketing_refill_reminder_sent", user_id=user_id, subscription_id=subscription.get("id"))
        return {
            "success": True,
            "message": f"Refill reminder queued for {subscription.get('medicine_name', 'subscription')}.",
        }

    def send_health_tips(self, user_id: str, condition: str) -> dict[str, Any]:
        track_event("marketing_health_tip_sent", user_id=user_id, condition=condition)
        return {
            "success": True,
            "message": f"Personalized health tip prepared for {condition}.",
        }

    def birthday_campaign(self, user_id: str) -> dict[str, Any]:
        track_event("marketing_birthday_campaign_sent", user_id=user_id)
        return {
            "success": True,
            "bonus_points": 200,
            "offer": "20% off next order",
        }
