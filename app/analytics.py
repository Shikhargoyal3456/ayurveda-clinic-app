from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import settings


_analytics_lock = Lock()


def _analytics_path() -> Path:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    return settings.analytics_log_path


def track_event(event: str, **details: Any) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "details": details,
    }
    with _analytics_lock:
        with _analytics_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def aggregate_daily_statistics() -> dict[str, Any]:
    path = _analytics_path()
    if not path.exists():
        return {"days": {}, "totals": {}}

    daily: dict[str, Counter[str]] = {}
    totals: Counter[str] = Counter()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        item = json.loads(raw_line)
        timestamp = str(item.get("timestamp", ""))
        day = timestamp[:10] if len(timestamp) >= 10 else "unknown"
        event = str(item.get("event", "unknown"))
        daily.setdefault(day, Counter())[event] += 1
        totals[event] += 1
    return {
        "days": {day: dict(counter) for day, counter in sorted(daily.items())},
        "totals": dict(totals),
    }
