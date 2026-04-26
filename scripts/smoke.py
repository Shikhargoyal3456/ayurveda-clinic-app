from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar


def _base_url() -> str:
    # KASH-AI-DEPLOY-FINAL: Accept CLI base URL for deploy.sh and env var for CI.
    if "--base-url" in sys.argv:
        index = sys.argv.index("--base-url")
        if index + 1 < len(sys.argv):
            return sys.argv[index + 1].rstrip("/")
    return os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


BASE_URL = _base_url()


def _request(opener: urllib.request.OpenerDirector, path: str, data: dict[str, str] | None = None) -> tuple[int, str]:
    encoded = urllib.parse.urlencode(data).encode() if data is not None else None
    request = urllib.request.Request(f"{BASE_URL}{path}", data=encoded)
    try:
        with opener.open(request, timeout=20) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def _csrf(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html) or re.search(r'content="([^"]+)"', html)
    return match.group(1) if match else ""


def main() -> int:
    # KASH-AI-DEPLOY-FINAL / GRAND-UNIFIED-1: health -> medicines -> AI -> guarded order -> admin redirect smoke flow.
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    checks: list[str] = []

    status, body = _request(opener, "/healthz")
    assert status == 200 and json.loads(body)["status"] in {"ok", "degraded"}
    checks.append("health")

    status, body = _request(opener, "/patient/medicines")
    medicines = json.loads(body)
    assert status == 200 and len(medicines) >= 20
    checks.append("medicines")

    status, order_page = _request(opener, "/order-medicines")
    token = _csrf(order_page)
    assert status == 200 and token
    status, body = _request(opener, "/order-medicines/ai-suggest", {"symptoms": "acidity", "csrf_token": token})
    assert status == 200 and "suggested_medicines" in json.loads(body)
    checks.append("ai")

    status, _ = _request(
        opener,
        "/patient/order/create",
        {
            "patient_name": "Smoke Patient",
            "patient_phone": "9999999999",
            "patient_address": "Smoke Address",
            "medicines_json": "[]",
            "pharmacy_id": "1",
            "csrf_token": token,
        },
    )
    assert status in {400, 404}
    checks.append("order_guard")

    status, _ = _request(opener, "/admin/suppliers")
    assert status in {200, 303, 403}
    checks.append("admin")

    print("Smoke checks passed:", ", ".join(checks))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Smoke checks failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
