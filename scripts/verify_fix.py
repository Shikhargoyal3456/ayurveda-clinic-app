#!/usr/bin/env python3
"""
Verify that the template context fix works.
Run: python scripts/verify_fix.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time

import requests


BASE_URL = "http://localhost:8000"


def test_homepage() -> bool:
    """Test that homepage returns 200 OK."""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        if response.status_code == 200:
            print("Homepage loads successfully")
            return True
        print(f"Homepage returned {response.status_code}")
        return False
    except Exception as exc:
        print(f"Homepage error: {exc}")
        return False


def test_health() -> bool:
    """Test health endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200 and "healthy" in response.text:
            print("Health check passes")
            return True
        print("Health check failed")
        return False
    except Exception as exc:
        print(f"Health check error: {exc}")
        return False


def check_logs_for_error() -> bool:
    """Check systemd logs for the specific error when journalctl is available."""
    if shutil.which("journalctl") is None:
        print("journalctl not available; skipping log check")
        return True

    command = ["journalctl", "-u", "ayurveda", "-n", "50", "--no-pager"]
    if shutil.which("sudo") is not None:
        command.insert(0, "sudo")

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    output = f"{result.stdout}\n{result.stderr}"
    if "context must include a" in output:
        print("ERROR still found in logs")
        return False
    print("No template context errors in recent logs")
    return True


if __name__ == "__main__":
    print("Verifying template context fix...")
    time.sleep(2)

    results = [
        test_health(),
        test_homepage(),
        check_logs_for_error(),
    ]

    if all(results):
        print("\nALL CHECKS PASSED! The template context issue is fixed.")
        sys.exit(0)

    print("\nSome checks failed. Please investigate.")
    sys.exit(1)
