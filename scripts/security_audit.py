"""
Security audit script for Kash AI
Run: python scripts/security_audit.py
"""
from __future__ import annotations

import os
import re
import subprocess


def scan_for_secrets() -> list[str]:
    patterns = {
        "API Key": r"api[_-]key\s*[=:]\s*['\"]?[a-zA-Z0-9]+",
        "Secret Key": r"SECRET_[A-Z]+\s*[=:]\s*['\"]?[a-zA-Z0-9]+",
        "Password": r"password\s*[=:]\s*['\"]?[a-zA-Z0-9@#$%^&*]+",
        "Token": r"[a-zA-Z0-9]{40,}",
    }
    issues: list[str] = []
    for root, dirs, files in os.walk("."):
        if any(part in root for part in (".git", "__pycache__", "venv", "logs")):
            continue
        for file in files:
            if not any(file.endswith(ext) for ext in (".py", ".js", ".html", ".json", ".yaml", ".yml")):
                continue
            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8") as handle:
                    content = handle.read()
                for pattern_name, pattern in patterns.items():
                    if re.search(pattern, content):
                        if ".env" in filepath and ".example" not in filepath:
                            continue
                        issues.append(f"{pattern_name} found in {filepath}")
            except Exception:
                continue
    return issues


def audit_env_file() -> bool:
    if not os.path.exists(".env"):
        print(".env file missing")
        return False
    if os.name == "posix":
        import stat

        mode = os.stat(".env").st_mode
        if mode & stat.S_IROTH or mode & stat.S_IRGRP:
            print(".env file has insecure permissions")
            return False
    print(".env file exists")
    return True


def check_dependencies() -> None:
    try:
        result = subprocess.run(["pip-audit", "--format", "json"], capture_output=True, text=True)
        if result.returncode == 0:
            print("No vulnerable dependencies found")
        else:
            print("Vulnerable dependencies found")
            print(result.stdout)
    except Exception:
        print("pip-audit not installed. Run: pip install pip-audit")


if __name__ == "__main__":
    print("KASH AI SECURITY AUDIT")
    print("=" * 50)
    print("ENVIRONMENT:")
    audit_env_file()
    print("SECRETS SCAN:")
    issues = scan_for_secrets()
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  No hardcoded secrets found")
    print("DEPENDENCIES:")
    check_dependencies()
    print("=" * 50)
    print("Security audit complete")
