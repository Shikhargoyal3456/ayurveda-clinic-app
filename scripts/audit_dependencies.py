"""
Dependency audit script for Kash AI
Run: python scripts/audit_dependencies.py
"""
from __future__ import annotations

import subprocess


def run_audit() -> None:
    print("🔍 Running dependency audit...")
    try:
        result = subprocess.run(["pip-audit", "--format", "json"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ No vulnerabilities found!")
        else:
            print("⚠️ Vulnerabilities found:")
            print(result.stdout)
    except FileNotFoundError:
        print("❌ pip-audit not installed. Run: pip install pip-audit")

    try:
        result = subprocess.run(["safety", "check", "--json"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Safety check passed!")
        else:
            print("⚠️ Safety issues found:")
            print(result.stdout)
    except FileNotFoundError:
        print("❌ safety not installed. Run: pip install safety")


if __name__ == "__main__":
    run_audit()
