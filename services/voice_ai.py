import logging
import os
from pathlib import Path

from services.ai_provider import GEMINI_API_KEY, chat_with_fallback, chat_with_gemini, parse_json_response


logger = logging.getLogger(__name__)


def transcribe_audio(audio_file_path: str, language: str = "auto") -> str:
    """
    Transcribe audio using Google Cloud Speech-to-Text API.
    language: "hi-IN" | "en-IN" | "auto" (tries hi-IN first, falls back to en-IN)
    """
    import os
    from google.cloud import speech

    api_key = os.getenv("GOOGLE_SPEECH_API_KEY", "")
    if not api_key:
        raise RuntimeError("GOOGLE_SPEECH_API_KEY is not configured.")

    with open(audio_file_path, "rb") as f:
        audio_content = f.read()

    client = speech.SpeechClient(
        client_options={"api_key": api_key}
    )
    audio = speech.RecognitionAudio(content=audio_content)
    suffix = Path(audio_file_path).suffix.lower()

    language_codes = []
    if language == "auto":
        language_codes = ["hi-IN", "en-IN"]
    else:
        language_codes = [language]

    config_kwargs = {
        "language_code": language_codes[0],
        "alternative_language_codes": language_codes[1:],
        "enable_automatic_punctuation": True,
        "model": "latest_long",
    }
    if suffix == ".mp3":
        config_kwargs["encoding"] = speech.RecognitionConfig.AudioEncoding.MP3
    elif suffix == ".ogg":
        config_kwargs["encoding"] = speech.RecognitionConfig.AudioEncoding.OGG_OPUS
    elif suffix == ".webm":
        config_kwargs["encoding"] = speech.RecognitionConfig.AudioEncoding.WEBM_OPUS
    elif suffix not in {".wav", ".flac"}:
        raise RuntimeError("Unsupported audio format. Please use WAV, FLAC, MP3, OGG, or WEBM.")

    config = speech.RecognitionConfig(**config_kwargs)

    response = client.recognize(config=config, audio=audio, timeout=30)
    transcript = " ".join(
        result.alternatives[0].transcript
        for result in response.results
        if result.alternatives
    ).strip()

    if not transcript:
        raise RuntimeError("Speech-to-Text returned an empty transcript.")

    return transcript


def structure_case_sheet(raw_transcript: str, patient_name: str) -> dict:
    system_prompt = "You are an Ayurvedic medical scribe. Return only valid JSON."
    user_prompt = (
        f"Extract all Ayurvedic case sheet fields for patient_name='{patient_name}'. "
        "Return JSON only. Include identification details, chief complaints, history of present illness, "
        "past history, personal history, examination findings, prakriti, vikriti, agni, koshta, nadi, "
        "diagnosis, treatment plan, and follow_up if available.\n\n"
        f"Transcript:\n{raw_transcript}"
    )

    if GEMINI_API_KEY:
        raw = chat_with_gemini(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        logger.info("Case sheet structured using gemini")
    else:
        raw, provider = chat_with_fallback(system_prompt, user_prompt, temperature=0.1)
        logger.info("Case sheet structured using %s", provider.value)
    return parse_json_response(raw)
