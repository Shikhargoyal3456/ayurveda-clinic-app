from __future__ import annotations

import logging

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


logger = logging.getLogger(__name__)


class TelegramOrderNotifier:
    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id and requests is not None)

    def send_order_notification(self, order: dict[str, object]) -> dict[str, object]:
        if not self.is_configured():
            logger.info("Telegram notifier skipped because it is not configured.")
            return {"success": False, "skipped": True, "reason": "not_configured"}

        message = (
            "NEW ORDER ALERT\n"
            f"Order ID: #{order.get('id')}\n"
            f"Customer: {order.get('customer_name')}\n"
            f"Amount: Rs {order.get('total')}\n"
            f"Items: {order.get('items_count')}\n"
            f"Status: {order.get('status')}\n"
        )

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            response = requests.post(
                url,
                json={"chat_id": self.chat_id, "text": message},
                timeout=10,
            )
            response.raise_for_status()
            return {"success": True}
        except Exception as exc:  # pragma: no cover
            logger.warning("Telegram order notification failed: %s", exc)
            return {"success": False, "error": str(exc)}
