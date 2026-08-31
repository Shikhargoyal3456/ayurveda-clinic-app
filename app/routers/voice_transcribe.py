from fastapi import APIRouter, UploadFile, File, HTTPException

from app.utils.groq_transcriber import groq_transcriber


router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/transcribe")
async def transcribe_audio(audio_file: UploadFile = File(...)):
    """Transcribe audio using Groq Whisper"""
    if not groq_transcriber.is_available():
        raise HTTPException(status_code=503, detail="Groq API not available")

    audio_data = await audio_file.read()
    if not audio_data:
        raise HTTPException(status_code=400, detail="Audio file is empty")

    transcript = groq_transcriber.transcribe(audio_data, audio_file.filename)

    if transcript:
        return {"success": True, "transcript": transcript, "model": "whisper-large-v3-turbo"}
    return {"success": False, "error": "Transcription failed"}


@router.get("/health")
async def voice_health():
    return {"available": groq_transcriber.is_available(), "model": groq_transcriber.model}
