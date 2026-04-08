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
    OLLAMA = "ollama"


logger = logging.getLogger("ai_provider")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
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
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=2048,
            timeout=AI_TIMEOUT,
        ),
    )
    elapsed = time.time() - start_time
    logger.info("Gemini responded in %.2fs using model=%s", elapsed, GEMINI_MODEL)

    text = response.text or ""
    if not text.strip():
        raise RuntimeError("Gemini returned an empty response.")
    return text.strip()


def chat_with_fallback(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
) -> tuple[str, AIProvider]:
    """
    Try Groq first. If it fails or no API key, fall back to Ollama.
    Returns (response_text, provider_used).
    Logs provider used, response time, and whether fallback occurred.
    """
    if GROQ_API_KEY:
        try:
            import groq

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
            logger.info("Groq responded in %.2fs", elapsed)
            content = response.choices[0].message.content or ""
            return content.strip(), AIProvider.GROQ
        except Exception as exc:
            logger.warning("Groq failed (%s), falling back to Ollama", exc)
    else:
        logger.info("Groq API key not configured, using Ollama directly")

    try:
        import ollama

        os.environ["OLLAMA_HOST"] = OLLAMA_HOST
        start_time = time.time()
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": temperature},
        )
        elapsed = time.time() - start_time
        logger.info("Ollama responded in %.2fs (fallback used)", elapsed)
        return response["message"]["content"].strip(), AIProvider.OLLAMA
    except Exception as exc:
        logger.error("Ollama also failed: %s", exc)
        raise RuntimeError(
            "Both Groq and Ollama failed. "
            "Check your GROQ_API_KEY and ensure Ollama is running."
        ) from exc


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
