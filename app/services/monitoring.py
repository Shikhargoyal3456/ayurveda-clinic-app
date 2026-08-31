from __future__ import annotations

import logging
import os

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


logger = logging.getLogger(__name__)


class MetricsCollector:
    def __init__(self):
        self.webhook_url = os.getenv("METRICS_WEBHOOK", "").strip()

    def send_metrics(self, metrics: dict[str, object]) -> dict[str, object]:
        if not self.webhook_url or requests is None:
            return {"success": False, "skipped": True}
        try:
            response = requests.post(self.webhook_url, json=metrics, timeout=10)
            response.raise_for_status()
            return {"success": True, "status_code": response.status_code}
        except Exception as exc:  # pragma: no cover
            logger.warning("Metrics webhook failed: %s", exc)
            return {"success": False, "error": str(exc)}
