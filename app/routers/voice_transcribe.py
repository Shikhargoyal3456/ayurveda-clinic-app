import logging

from fastapi import APIRouter, UploadFile, File, HTTPException
from starlette.concurrency import run_in_threadpool

from app.utils.groq_transcriber import groq_transcriber


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile | None = File(default=None),
    audio_file: UploadFile | None = File(default=None),
):
    """Transcribe uploaded audio using Groq Whisper."""
    upload = file or audio_file
    if upload is None:
        raise HTTPException(status_code=400, detail='Audio file is required in multipart field "file".')
    if not groq_transcriber.is_available():
        raise HTTPException(status_code=503, detail="Groq API not available")

    audio_data = await upload.read(25 * 1024 * 1024 + 1)
    if not audio_data:
        raise HTTPException(status_code=400, detail="Audio file is empty")
    if len(audio_data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file exceeds the 25 MB limit.")

    transcript = await run_in_threadpool(groq_transcriber.transcribe, audio_data, upload.filename)
    if transcript:
        return {"success": True, "transcript": transcript, "model": groq_transcriber.model}
    return {
        "success": False,
        "transcript": "",
        "error": "Transcription produced no text or the provider rejected the audio.",
        "model": groq_transcriber.model,
    }


@router.get("/health")
async def voice_health():
    return {"available": groq_transcriber.is_available(), "model": groq_transcriber.model}
