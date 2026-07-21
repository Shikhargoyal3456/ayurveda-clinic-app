from __future__ import annotations

import os
from typing import Optional

try:
    from groq import Groq
except Exception:  # pragma: no cover
    Groq = None


class GroqClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip() or "llama-3.3-70b-versatile"
        self.client = Groq(api_key=self.api_key) if Groq is not None and self.api_key else None

    def is_available(self) -> bool:
        return self.client is not None and bool(self.api_key)

    async def chat(self, messages: list[dict[str, str]], temperature: float = 0.7, max_tokens: int = 500) -> Optional[str]:
        if not self.is_available():
            return None
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return getattr(response.choices[0].message, "content", None)
        except Exception:
            return None


groq_client = GroqClient()
