from __future__ import annotations

from typing import Any


class AIOfferEngine:
    def generate_personalized_offers(self, user_profile: dict[str, Any]) -> list[dict[str, Any]]:
        offers: list[dict[str, Any]] = []
        orders = int(user_profile.get("orders", 0) or 0)
        abandoned_carts = int(user_profile.get("abandoned_carts", 0) or 0)
        frequent_category = str(user_profile.get("frequent_category", "wellness") or "wellness")
        subscription_eligible = bool(user_profile.get("subscription_eligible", True))

        if orders == 0:
            offers.append(
                {
                    "type": "welcome",
                    "title": "Welcome offer",
                    "discount": 30,
                    "min_order": 299,
                    "expiry": "7 days",
                    "code": "WELCOME30",
                }
            )
        if abandoned_carts > 0:
            offers.append(
                {
                    "type": "cart_recovery",
                    "title": "Complete your cart",
                    "discount": 15,
                    "min_order": 399,
                    "code": "COMEBACK15",
                }
            )
        offers.append(
            {
                "type": "category",
                "title": f"{frequent_category.title()} savings",
                "category": frequent_category,
                "discount": 10,
                "min_order": 500,
                "code": f"{frequent_category[:4].upper()}10",
            }
        )
        if subscription_eligible:
            offers.append(
                {
                    "type": "subscription",
                    "title": "Smart subscription offer",
                    "discount": 25,
                    "min_order": 0,
                    "first_month_free": True,
                    "code": "SUBSAVE25",
                }
            )
        return offers

    def apply_best_offer(self, cart_total: float, user_offers: list[dict[str, Any]]) -> tuple[float, dict[str, Any] | None]:
        eligible = [offer for offer in user_offers if float(cart_total) >= float(offer.get("min_order", 0) or 0)]
        if not eligible:
            return round(float(cart_total), 2), None
        best_offer = max(eligible, key=lambda item: float(item.get("discount", 0) or 0))
        discounted_total = float(cart_total) * (1 - float(best_offer.get("discount", 0) or 0) / 100)
        return round(discounted_total, 2), best_offer
