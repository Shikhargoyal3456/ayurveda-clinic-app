"""
Complete feature verification for Kash AI
Run: python scripts/verify_all_features.py
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

import requests

BASE_URL = "http://localhost:8000"


def test_endpoint(name: str, method: str, url: str, data: dict[str, Any] | None = None, expected_status: int = 200):
    print(f"Testing {name}...", end=" ")
    try:
        if method == "GET":
            resp = requests.get(f"{BASE_URL}{url}", timeout=10)
        elif method == "POST" and data is not None:
            resp = requests.post(f"{BASE_URL}{url}", json=data, timeout=10)
        elif method == "POST":
            resp = requests.post(f"{BASE_URL}{url}", timeout=10)
        else:
            return False, None

        if resp.status_code == expected_status:
            print(f"✅ Working (Status: {resp.status_code})")
            return True, resp.json() if resp.text else None
        print(f"❌ Failed (Status: {resp.status_code})")
        return False, None
    except Exception as exc:
        print(f"❌ Error: {exc}")
        return False, None


def main() -> int:
    print("=" * 60)
    print("KASH AI - COMPLETE FEATURE VERIFICATION")
    print("=" * 60)
    print()

    features = [
        ("Health Check", "GET", "/healthz", None),
        ("Tongue Diagnosis", "POST", "/api/tongue-analyze", {"description": "white coated tongue"}),
        ("AI Chat", "POST", "/api/ai-chat", {"message": "What is Triphala?"}),
        ("Billing Codes", "POST", "/api/generate-billing-codes", {"prescription_id": 1}),
        ("Medicine Recommendations", "POST", "/api/recommend-medicines", {"case_sheet_id": 1}),
        ("Voice Extraction", "POST", "/api/voice/extract", {"transcript": "Patient has fever"}),
        ("Churn Prediction", "GET", "/api/predict-churn", None),
        ("Video Consultation", "GET", "/telemedicine/start", None),
        ("Device Check", "GET", "/api/device/check", None),
    ]

    results: list[tuple[str, bool]] = []
    for name, method, url, payload in features:
        status, data = test_endpoint(name, method, url, payload)
        results.append((name, status))
        if status and isinstance(data, dict) and data.get("model"):
            print(f"   Model: {data.get('model')}")
        if name == "AI Chat" and data:
            print(f"   Response preview: {str(data.get('response', ''))[:80]}...")

    print()
    print("=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print()

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for name, ok in results:
        print(f"{'✅' if ok else '❌'} {name}")

    print()
    print(f"Passed: {passed}/{total}")
    if passed == total:
        print("ALL FEATURES WORKING! Your app is ready!")
    else:
        print(f"{total - passed} feature(s) need attention.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
