from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

try:
    from groq import Groq
except Exception:  # pragma: no cover
    Groq = None


load_dotenv()


class GroqTranscriber:
    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.client = Groq(api_key=self.api_key) if Groq is not None and self.api_key else None
        self.model = "whisper-large-v3-turbo"

    def is_available(self) -> bool:
        return self.client is not None and bool(self.api_key)

    def transcribe(self, audio_data: bytes, filename: str | None = None) -> Optional[str]:
        if not self.is_available() or not audio_data:
            return None

        suffix = Path(filename or "recording.webm").suffix or ".webm"
        tmp_path = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            with open(tmp_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=(filename or f"recording{suffix}", audio_file.read()),
                    language="hi",
                    response_format="text",
                    temperature=0.0,
                )

            return str(response).strip() or None
        except Exception as exc:  # pragma: no cover
            print(f"Transcription error: {exc}")
            return None
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass


groq_transcriber = GroqTranscriber()
