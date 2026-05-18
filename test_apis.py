import base64
import io
import os
import wave

import requests
from dotenv import load_dotenv

try:
    import google.generativeai as genai
except Exception as exc:  # pragma: no cover - import failure is reported at runtime
    genai = None
    GEMINI_IMPORT_ERROR = exc
else:
    GEMINI_IMPORT_ERROR = None


def print_success(name: str) -> None:
    print(f"✅ {name} - Working")


def print_failure(name: str, error: str) -> None:
    print(f"❌ {name} - Failed: {error}")


def create_silent_wav_base64(duration_ms: int = 250, sample_rate: int = 16000) -> str:
    frame_count = int(sample_rate * (duration_ms / 1000))
    silent_frames = b"\x00\x00" * frame_count

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silent_frames)

    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_gemini() -> None:
    name = "GEMINI_API_KEY"
    try:
        api_key = os.getenv(name)
        if not api_key:
            raise RuntimeError("Missing environment variable")
        if genai is None:
            raise RuntimeError(f"google-generativeai import failed: {GEMINI_IMPORT_ERROR}")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content("Say hello")
        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise RuntimeError("Empty response from Gemini")

        print_success(name)
    except Exception as exc:
        print_failure(name, str(exc))


def test_google_speech() -> None:
    name = "GOOGLE_SPEECH_API_KEY"
    try:
        api_key = os.getenv(name)
        if not api_key:
            raise RuntimeError("Missing environment variable")

        url = "https://speech.googleapis.com/v1/speech:recognize"
        payload = {
            "config": {
                "encoding": "LINEAR16",
                "sampleRateHertz": 16000,
                "languageCode": "en-US",
            },
            "audio": {
                "content": create_silent_wav_base64(),
            },
        }
        response = requests.post(url, params={"key": api_key}, json=payload, timeout=20)
        if response.status_code != 200:
            message = response.json().get("error", {}).get("message", response.text)
            raise RuntimeError(f"HTTP {response.status_code}: {message}")

        print_success(name)
    except Exception as exc:
        print_failure(name, str(exc))


def test_google_maps() -> None:
    name = "GOOGLE_MAPS_API_KEY"
    try:
        api_key = os.getenv(name)
        if not api_key:
            raise RuntimeError("Missing environment variable")

        url = "https://maps.googleapis.com/maps/api/geocode/json"
        response = requests.get(
            url,
            params={"address": "New Delhi", "key": api_key},
            timeout=20,
        )
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}")

        data = response.json()
        status = data.get("status")
        if status != "OK" or not data.get("results"):
            raise RuntimeError(f"Unexpected response status: {status}")

        print_success(name)
    except Exception as exc:
        print_failure(name, str(exc))


def main() -> None:
    load_dotenv()
    test_gemini()
    test_google_speech()
    test_google_maps()


if __name__ == "__main__":
    main()
