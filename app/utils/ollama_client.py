from __future__ import annotations

import os
from typing import Optional

import httpx


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2:3b").strip() or "llama3.2:3b"
        self.enabled = os.getenv("OLLAMA_ENABLED", "true").lower() == "true"
        self._available: bool | None = None
        self._model_available: bool | None = None

    def is_available(self) -> bool:
        if not self.enabled:
            return False
        if self._available is not None:
            return self._available
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=2.0)
            self._available = response.status_code == 200
        except Exception:
            self._available = False
        return self._available

    def model_available(self) -> bool:
        if not self.is_available():
            return False
        if self._model_available is not None:
            return self._model_available
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=2.0)
            response.raise_for_status()
            models = response.json().get("models", [])
            self._model_available = any(self.model in str(item.get("name", "")) for item in models)
        except Exception:
            self._model_available = False
        return self._model_available

    def get_model_available(self) -> bool:
        return self.model_available()

    async def chat(self, messages: list[dict[str, str]], temperature: float = 0.7, max_tokens: int = 500) -> Optional[str]:
        if not self.model_available():
            return None
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "options": {"temperature": temperature, "num_predict": max_tokens},
                        "stream": False,
                    },
                )
            response.raise_for_status()
            return response.json().get("message", {}).get("content") or None
        except Exception:
            return None

    async def analyze_text(self, text: str, prompt: str) -> Optional[str]:
        return await self.chat(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ]
        )


ollama_client = OllamaClient()
