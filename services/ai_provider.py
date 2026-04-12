import json
import logging
import os
import time
from enum import Enum
from typing import Dict, List

from google import genai
from google.genai import types


class AIProvider(Enum):
    GEMINI = "gemini"
    GROQ = "groq"


logger = logging.getLogger("ai_provider")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "30"))


def chat_with_gemini(
    system_prompt: str | List[Dict[str, str]],
    user_prompt: str = "",
    temperature: float = 0.3,
) -> str:
    """
    Call Gemini via google-genai. Returns response text.
    Raises RuntimeError if the call fails.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    if isinstance(system_prompt, list):
        prompt_parts = []
        for message in system_prompt:
            role = (message.get("role") or "").strip()
            content = (message.get("content") or "").strip()
            if not content:
                continue
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
            else:
                prompt_parts.append(f"User: {content}")
        system_prompt = ""
        user_prompt = "\n\n".join(prompt_parts)

    client = genai.Client(api_key=GEMINI_API_KEY)

    start_time = time.time()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            http_options=types.HttpOptions(timeout=AI_TIMEOUT * 1000),
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=2048,
        ),
    )
    elapsed = time.time() - start_time
    logger.info("Gemini responded in %.2fs using model=%s", elapsed, GEMINI_MODEL)

    text = response.text or ""
    if not text.strip():
        raise RuntimeError("Gemini returned an empty response.")
    return text.strip()


def chat_with_groq(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
) -> str:
    """
    Call Groq chat completions. Returns response text.
    Raises RuntimeError if Groq is not configured or the SDK is not installed.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    try:
        import groq
    except ImportError as exc:
        raise RuntimeError("Groq SDK is not installed. Install requirements.txt in the app runtime.") from exc

    client = groq.Groq(api_key=GROQ_API_KEY)
    start_time = time.time()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        timeout=AI_TIMEOUT,
    )
    elapsed = time.time() - start_time
    logger.info("Groq responded in %.2fs using model=%s", elapsed, GROQ_MODEL)

    content = response.choices[0].message.content or ""
    if not content.strip():
        raise RuntimeError("Groq returned an empty response.")
    return content.strip()


def chat_with_fallback(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
) -> tuple[str, AIProvider]:
    """
    Use the configured remote AI provider without falling back to Ollama.
    Gemini is preferred when configured; Groq is used as the secondary provider.
    """
    if GEMINI_API_KEY:
        return chat_with_gemini(system_prompt, user_prompt, temperature), AIProvider.GEMINI
    if GROQ_API_KEY:
        return chat_with_groq(system_prompt, user_prompt, temperature), AIProvider.GROQ
    raise RuntimeError("Neither GEMINI_API_KEY nor GROQ_API_KEY is configured. AI provider is unavailable.")


def parse_json_response(raw: str) -> dict:
    """
    Strip markdown code fences and parse JSON.
    Handles ```json ... ``` and ``` ... ``` wrapping.
    Raises ValueError with clear message if parsing fails.
    """
    cleaned = (raw or "").strip()

    if cleaned.startswith("```"):
        fenced_parts = cleaned.split("```")
        if len(fenced_parts) > 1:
            cleaned = fenced_parts[1].strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI returned invalid JSON. Raw response: {raw[:200]}...") from exc
