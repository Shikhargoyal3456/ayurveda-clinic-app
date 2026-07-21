"""
Verify all imports work correctly
Run: python scripts/verify_imports.py
"""
from __future__ import annotations

import sys


def test_import(module_name: str) -> bool:
    try:
        __import__(module_name)
        print(f"✅ {module_name}")
        return True
    except Exception as exc:
        print(f"❌ {module_name}: {exc}")
        return False


print("🔍 Testing imports...")

modules = [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "jinja2",
    "pydantic",
    "httpx",
    "openai",
    "dotenv",
    "PIL",
    "numpy",
    "pdfplumber",
    "pytesseract",
    "google.genai",
    "authlib",
    "redis",
]

failed = []
for module in modules:
    if not test_import(module):
        failed.append(module)

if failed:
    print(f"\n❌ Failed imports: {failed}")
    sys.exit(1)

print("\n✅ All imports successful!")
