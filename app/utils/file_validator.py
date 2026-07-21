from __future__ import annotations

import io
from typing import Tuple

from fastapi import HTTPException, UploadFile

try:
    import magic  # type: ignore
except Exception:  # pragma: no cover
    magic = None

ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
ALLOWED_PDF_TYPES = ["application/pdf"]
MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_IMAGE_SIZE = 10 * 1024 * 1024


def validate_file_upload(
    file: UploadFile,
    max_size: int = MAX_FILE_SIZE,
    allowed_types: list[str] = ALLOWED_IMAGE_TYPES,
) -> Tuple[bool, str]:
    content = file.file.read()
    file.file.seek(0)
    if len(content) > max_size:
        return False, f"File too large. Max size: {max_size // (1024 * 1024)}MB"
    file_type = magic.from_buffer(content[:1024], mime=True) if magic is not None else (file.content_type or "")
    if file_type not in allowed_types:
        return False, f"File type not allowed. Allowed: {', '.join(allowed_types)}"
    if file_type in ALLOWED_IMAGE_TYPES:
        try:
            from PIL import Image

            Image.open(io.BytesIO(content)).verify()
        except Exception:
            return False, "Invalid image file"
    return True, ""


def validate_prompt_injection(text: str) -> bool:
    injection_patterns = [
        "ignore previous instructions",
        "ignore all instructions",
        "forget your instructions",
        "system prompt",
        "you are now",
        "new role",
        "take on the role",
        "pretend to be",
        "act as",
        "override",
        "bypass",
        "inject",
        "exploit",
        "hack",
        "breach",
        "sql injection",
        "drop table",
        "delete from",
        "grant all",
        "alter table",
        "exec xp_",
        "wscript.shell",
        "powershell",
        "cmd.exe",
        "eval(",
        "exec(",
        "system(",
        "shell_exec",
        "passthru",
        "base64_decode",
        "str_rot13",
        "assert(",
        "create_function",
        "allow_url_fopen",
        "allow_url_include",
        "open_basedir",
        "disable_functions",
    ]
    text_lower = str(text or "").lower()
    return not any(pattern in text_lower for pattern in injection_patterns)
