from __future__ import annotations

import os
from typing import Optional

try:
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover
    genai = None
    types = None


class GeminiClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
        self.client = genai.Client(api_key=self.api_key) if genai is not None and self.api_key else None

    def is_available(self) -> bool:
        return self.client is not None and bool(self.api_key)

    async def generate_text(self, prompt: str, temperature: float = 0.2, max_tokens: int = 500) -> Optional[str]:
        if not self.is_available():
            return None
        try:
            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ) if types is not None else None
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            return getattr(response, "text", None) or None
        except Exception:
            return None

    async def analyze_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/png", temperature: float = 0.2, max_tokens: int = 500) -> Optional[str]:
        if not self.is_available() or types is None:
            return None
        try:
            parts = [
                types.Part.from_text(text=prompt),
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            ]
            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            response = self.client.models.generate_content(
                model=self.model,
                contents=parts,
                config=config,
            )
            return getattr(response, "text", None) or None
        except Exception:
            return None


gemini_client = GeminiClient()
