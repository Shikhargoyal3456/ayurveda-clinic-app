"""
Test app startup
Run: python scripts/test_startup.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_app() -> bool:
    try:
        from app.main import app

        print("✅ App imported successfully!")
        print("✅ FastAPI app created!")
        _ = app
        return True
    except Exception as exc:
        print(f"❌ App import failed: {exc}")
        return False


if __name__ == "__main__":
    print("🔍 Testing app startup...")
    success = test_app()
    sys.exit(0 if success else 1)
