import base64
import io
import os
import wave

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types


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
    name = "VERTEX_AI_PROJECT"
    try:
        project = os.getenv(name) or os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        if not project:
            raise RuntimeError("Missing environment variable")
        client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
            http_options=types.HttpOptions(api_version="v1"),
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say hello",
        )
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
