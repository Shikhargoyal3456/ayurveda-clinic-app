from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from services.sarvam_voice import get_sarvam_voice


router = APIRouter(prefix="/api/voice", tags=["Sarvam Voice"])


class TextToSpeechRequest(BaseModel):
    text: str
    target_language_code: str = "hi-IN"
    speaker: str = "simran"


@router.post("/speech-to-text")
async def sarvam_speech_to_text(
    file: UploadFile = File(...),
    language_code: str = Form("hi-IN"),
):
    """Convert speech to text using Sarvam AI."""
    try:
        audio_bytes = await file.read()
        transcript = get_sarvam_voice().speech_to_text(
            audio_bytes=audio_bytes,
            language_code=language_code,
            filename=file.filename or "recording.wav",
        )
        return {"success": True, "transcript": transcript, "provider": "sarvam"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/text-to-speech")
async def sarvam_text_to_speech(payload: TextToSpeechRequest):
    """Convert text to speech using Sarvam AI."""
    try:
        audio_bytes = get_sarvam_voice().text_to_speech(
            text=payload.text,
            target_language_code=payload.target_language_code,
            speaker=payload.speaker,
        )
        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
