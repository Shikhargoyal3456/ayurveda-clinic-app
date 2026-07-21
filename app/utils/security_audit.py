from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable


SECRET_PATTERNS = (
    re.compile(r"(API_KEY|SECRET|PASSWORD|TOKEN)\s*=", re.I),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
)


def scan_text_for_secrets(text: str) -> list[str]:
    findings = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(pattern.pattern)
    return findings


def scan_paths_for_secrets(paths: Iterable[Path]) -> list[str]:
    matches: list[str] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if scan_text_for_secrets(text):
            matches.append(str(path))
    return matches


def env_has_required_secret(name: str) -> bool:
    return bool(os.getenv(name, "").strip())

