from __future__ import annotations

import json
import os
import re

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_doctor, verify_csrf
from app.database import get_db
from app.models import Doctor, Patient
from app.portal_auth import normalize_doctor_type
from services.ai_provider import call_gemini, generate_gemini_content, is_gemini_configured, parse_json_response, stream_with_gemini
from shared.template_engine import render_template, templates


load_dotenv()

router = APIRouter(tags=["ai-doctor"])

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
FALLBACK_GEMINI_MODEL = "gemini-2.5-flash"
MAX_HISTORY_MESSAGES = 100
MAX_MESSAGE_CHARS = 2000
DISCLAIMER_PATTERN = re.compile(r"(?:\n\s*)?⚠️ I am an AI assistant, not a licensed doctor\.[\s\S]*$", re.IGNORECASE)
DIAGNOSIS_PATTERN = re.compile(r"\|\|\|DIAGNOSIS\|\|\|(.*?)\|\|\|END\|\|\|", re.DOTALL)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

INDIA_EMERGENCY_NUMBERS = """
INDIA EMERGENCY CONTACTS:
- All emergencies (medical/police/fire): 112
- Ambulance only: 102 or 108
- Mental health / suicide prevention: iCall 9152987821 (Mon-Sat 10am-8pm)
- Mental health 24x7: Vandrevala Foundation 1860-2662-345
- Poison Control: 1800-116-1117
"""

AGE_SAFETY_RULES = """
CRITICAL AGE AND DOSAGE SAFETY RULES:
- NEVER recommend specific dosages unless BOTH patient_age AND patient_weight are provided
- If either is missing, say: "I need your age and weight to suggest safe dosages. Please consult a pharmacist or doctor."
- If patient_age < 2: Say "Do not give any over-the-counter medication to infants without a pediatrician's approval."
- If patient_age < 12: Say "Consult a pediatrician. Never use adult medication dosages for children."
- If patient_age > 65: Say "Start with the lowest possible dose. Elderly patients have higher risk of drug interactions - consult a doctor."
"""

SAFETY_DISCLAIMER = (
    "\n\n⚠️ I am an AI assistant, not a licensed doctor. This is health information, not medical advice. "
    "Always consult a qualified doctor before making medical decisions. For emergencies in India, call 112."
)


class ChatMessage(BaseModel):
    role: str = "user"
    content: str = ""


class ChatRequest(BaseModel):
    message: str
    messages: list[ChatMessage] = Field(default_factory=list)
    language: str = "en"
    patient_age: int | None = None
    patient_weight: float | None = None
    allergies: str | None = None
    current_medications: str | None = None


class ChatResponse(BaseModel):
    reply: str
    diagnosis: dict


class StructureFieldRequest(BaseModel):
    field_name: str
    transcribed_text: str
    patient_id: int | None = None


def _sanitize_text(value: object) -> str:
    text = HTML_TAG_PATTERN.sub("", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_MESSAGE_CHARS]


def _clean_history(messages: list[ChatMessage]) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    for message in messages[-MAX_HISTORY_MESSAGES:]:
        role = "assistant" if str(message.role).strip().lower() == "assistant" else "user"
        content = _sanitize_text(message.content)
        if content:
            cleaned.append({"role": role, "content": content})
    return cleaned


def _doctor_type_from_request(request: Request) -> str:
    return normalize_doctor_type(
        request.session.get("doctor_type") or request.session.get("portal_doctor_type"),
        request.session.get("doctor_type"),
    )


def _conversation_turns(history: list[dict[str, str]], message: str) -> int:
    prior_user_turns = sum(1 for item in history if item["role"] == "user")
    return prior_user_turns + (1 if message.strip() else 0)


def _doctor_system_prompt(doctor_type: str, payload: ChatRequest, history: list[dict[str, str]]) -> str:
    patient_context_lines = [
        f"doctor_type: {doctor_type}",
        f"patient_age: {payload.patient_age if payload.patient_age is not None else 'not provided'}",
        f"patient_weight: {payload.patient_weight if payload.patient_weight is not None else 'not provided'}",
        f"allergies: {_sanitize_text(payload.allergies) or 'not provided'}",
        f"current_medications: {_sanitize_text(payload.current_medications) or 'not provided'}",
        f"language: {_sanitize_text(payload.language) or 'en'}",
    ]
    context_block = "\n".join(patient_context_lines)
    common_rules = f"""
You are Dr. Kash, a careful clinic consultation assistant supporting a real doctor inside Kash AI.

ABSOLUTE RULES:
1. Generate all responses dynamically.
2. Ask at most 2 follow-up questions in one reply.
3. Detect emergencies in the first 5 words when present.
4. Match the patient's language: English or Hindi/Hinglish.
5. Never invent patient facts that were not provided.
6. Keep replies practical for an in-clinic consultation flow.
7. If medicine dosage is unsafe to infer, say what is missing instead of guessing.
8. Keep the doctor in control and frame output as consultation support, not final diagnosis.

{INDIA_EMERGENCY_NUMBERS.strip()}

{AGE_SAFETY_RULES.strip()}

PATIENT CONTEXT:
{context_block}
""".strip()
    if doctor_type == "ayurveda":
        specialty_rules = """
SPECIALTY MODE: AYURVEDA
- Use Samhita-based reasoning wherever possible.
- Think in terms of prakriti, vikriti, agni, ama, nidana, samprapti, and chikitsa siddhanta.
- Prefer classical formulations, pathya-apathya, ahara, vihara, and follow-up observations.
- Do not present generic western triage only; translate symptoms into Ayurvedic reasoning when enough context exists.
- If context is incomplete, ask for details that help classify dosha imbalance and digestive/metabolic state.
""".strip()
    else:
        specialty_rules = f"""
SPECIALTY MODE: {doctor_type.upper()}
- Give clinically grounded consultation support appropriate to the doctor's specialty.
- Keep reasoning structured and concise.
""".strip()

    turns = _conversation_turns(history, payload.message)
    diagnosis_instruction = """
STRUCTURED OUTPUT RULE:
When enough context is available, append this exact machine-readable block at the very end:
|||DIAGNOSIS|||{"items":[{"name":"Condition","seek_doctor":true,"color":"#3b82f6"}]}|||END|||
Only include JSON inside the block. Keep 2-3 items max.
""".strip()
    if turns >= 4:
        diagnosis_instruction += "\nYou now have enough context. Return the diagnosis block in this reply."
    else:
        diagnosis_instruction += "\nIf context is still incomplete, skip the block for now."
    return f"{common_rules}\n\n{specialty_rules}\n\n{diagnosis_instruction}"


def _build_prompt(payload: ChatRequest, doctor_type: str) -> str:
    history = _clean_history(payload.messages)
    system_prompt = _doctor_system_prompt(doctor_type, payload, history)
    conversation_lines = []
    for item in history:
        speaker = "Assistant" if item["role"] == "assistant" else "Patient"
        conversation_lines.append(f"{speaker}: {item['content']}")
    conversation_lines.append(f"Patient: {_sanitize_text(payload.message)}")
    conversation_lines.append("Assistant:")
    return f"{system_prompt}\n\nCONVERSATION:\n" + "\n".join(conversation_lines)


def _extract_reply_and_diagnosis(text: str) -> tuple[str, dict]:
    diagnosis = {"items": []}
    clean_reply = (text or "").strip()
    match = DIAGNOSIS_PATTERN.search(clean_reply)
    if match:
        raw_json = match.group(1).strip()
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
                diagnosis = parsed
        except json.JSONDecodeError:
            diagnosis = {"items": []}
        clean_reply = DIAGNOSIS_PATTERN.sub("", clean_reply).strip()
    clean_reply = DISCLAIMER_PATTERN.sub("", clean_reply).strip()
    clean_reply = re.sub(r"\n{3,}", "\n\n", clean_reply)
    return clean_reply, diagnosis


def _fallback_diagnosis_from_reply(reply: str) -> dict:
    cleaned = DISCLAIMER_PATTERN.sub("", str(reply or "")).strip()
    candidates: list[str] = []
    for line in cleaned.splitlines():
        text = re.sub(r"^[\-\*\d\.\)\s]+", "", line).strip(" :")
        if text and len(text) > 3:
            candidates.append(text)
    first_item = candidates[0] if candidates else "Clinical review needed"
    first_item = re.split(r"[.!?]", first_item, maxsplit=1)[0].strip() or "Clinical review needed"
    return {"items": [{"name": first_item[:60], "seek_doctor": True, "color": "#3b82f6"}]}


def _finalize_diagnosis(reply: str, diagnosis: dict, turns: int) -> dict:
    if diagnosis.get("items"):
        return diagnosis
    if turns >= 4:
        return _fallback_diagnosis_from_reply(reply)
    return {"items": []}


def _append_safety_disclaimer(text: str) -> str:
    clean = DISCLAIMER_PATTERN.sub("", str(text or "")).strip()
    return f"{clean}{SAFETY_DISCLAIMER}" if clean else SAFETY_DISCLAIMER.strip()


def _chunk_text(text: str, size: int = 180) -> list[str]:
    clean = str(text or "")
    return [clean[index:index + size] for index in range(0, len(clean), size)] or [""]


def _generate_gemini_content(prompt: str) -> str:
    try:
        return generate_gemini_content(
            prompt,
            model_name=GEMINI_MODEL,
            model_candidates=[DEFAULT_GEMINI_MODEL, FALLBACK_GEMINI_MODEL],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini request failed: {exc}") from exc


def _assert_ai_configured() -> None:
    if not is_gemini_configured():
        raise HTTPException(
            status_code=500,
            detail="Vertex AI Gemini is not configured. Set VERTEX_AI_PROJECT and authenticate with ADC.",
        )


@router.post("/api/doctor/chat", response_model=ChatResponse)
async def doctor_chat(payload: ChatRequest, request: Request, _: None = Depends(verify_csrf)):
    _assert_ai_configured()
    doctor_type = _doctor_type_from_request(request)
    prompt = _build_prompt(payload, doctor_type)
    turns = _conversation_turns(_clean_history(payload.messages), payload.message)
    raw_text = _generate_gemini_content(prompt)
    reply, diagnosis = _extract_reply_and_diagnosis(raw_text)
    return {"reply": _append_safety_disclaimer(reply), "diagnosis": _finalize_diagnosis(reply, diagnosis, turns)}


@router.post("/api/doctor/chat/stream")
async def doctor_chat_stream(payload: ChatRequest, request: Request, _: None = Depends(verify_csrf)):
    _assert_ai_configured()
    doctor_type = _doctor_type_from_request(request)
    prompt = _build_prompt(payload, doctor_type)
    turns = _conversation_turns(_clean_history(payload.messages), payload.message)

    async def generate():
        raw_chunks: list[str] = []
        try:
            for chunk_text in stream_with_gemini(
                "",
                prompt,
                temperature=0.3,
                max_output_tokens=2048,
            ):
                if not chunk_text:
                    continue
                raw_chunks.append(chunk_text)
                yield f"data: {json.dumps({'chunk': chunk_text})}\n\n"

            combined = "".join(raw_chunks)
            reply, diagnosis = _extract_reply_and_diagnosis(combined)
            reply = _append_safety_disclaimer(reply)
            diagnosis = _finalize_diagnosis(reply, diagnosis, turns)
            if not combined.endswith(reply):
                disclaimer_only = reply.replace(_extract_reply_and_diagnosis(combined)[0], "", 1).strip()
                if disclaimer_only:
                    yield f"data: {json.dumps({'chunk': disclaimer_only})}\n\n"
            if diagnosis.get("items"):
                diagnosis_json = json.dumps(diagnosis, separators=(",", ":"))
                yield f"data: {json.dumps({'chunk': f'|||DIAGNOSIS|||{diagnosis_json}|||END|||'})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc) or 'Streaming failed.'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/api/doctor/summary")
async def doctor_summary(payload: ChatRequest, request: Request, _: None = Depends(verify_csrf)):
    _assert_ai_configured()
    doctor_type = _doctor_type_from_request(request)
    history = _clean_history(payload.messages)
    if payload.message.strip():
        history.append({"role": "user", "content": _sanitize_text(payload.message)})
    system_prompt = _doctor_system_prompt(doctor_type, payload, history)
    transcript = "\n".join(
        f"{'Doctor' if item['role'] == 'assistant' else 'Patient'}: {item['content']}"
        for item in history[-20:]
    )
    prompt = (
        f"{system_prompt}\n\n"
        "Create a short consultation summary with these headings exactly:\n"
        "Chief complaints\nClinical impression\nAyurveda assessment\nAdvice and precautions\nFollow-up questions\n\n"
        f"TRANSCRIPT:\n{transcript}\n\nSummary:"
    )
    raw_text = _generate_gemini_content(prompt)
    reply, _ = _extract_reply_and_diagnosis(raw_text)
    return JSONResponse({"summary": _append_safety_disclaimer(reply)})


@router.get("/ai-doctor-live")
async def ai_doctor_live_page(request: Request):
    return render_template(templates, request, "doctor.html")


@router.get("/ai-doctor")
async def ai_doctor_page(request: Request, db: Session = Depends(get_db)):
    from app.portal_auth import get_portal_user

    user = get_portal_user(request, db)
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})
    return render_template(
        templates,
        request,
        "new_ai_doctor.html",
        {"request": request, "user": user, "csrf_token": getattr(request.state, "csrf_token", "")},
    )


@router.websocket("/ws/ai-doctor")
async def ai_doctor_websocket(websocket: WebSocket):
    await websocket.accept()
    history: list[ChatMessage] = []
    await websocket.send_json(
        {
            "type": "session_ready",
            "session_id": "live-ai-doctor",
            "status": "connected",
            "detail": "Live consultation room is ready.",
        }
    )

    try:
        while True:
            payload = await websocket.receive_json()
            event_type = str(payload.get("type") or "").strip()

            if event_type == "end_consultation":
                await websocket.send_json(
                    {
                        "type": "consultation_summary",
                        "summary": {
                            "patient_summary": [item.content for item in history if item.role == "user"][-5:],
                            "visual_summary": "Live camera and voice session ended.",
                        },
                    }
                )
                break

            if event_type == "video_frame":
                await websocket.send_json(
                    {
                        "type": "vision_update",
                        "text": "Received the latest camera frame. Continue if you want a deeper visual review.",
                    }
                )
                continue

            if event_type == "audio_chunk":
                await websocket.send_json(
                    {
                        "type": "status",
                        "status": "connected",
                        "detail": "Received audio stream chunk.",
                    }
                )
                continue

            if event_type != "user_text":
                await websocket.send_json({"type": "error", "message": "Unsupported message type."})
                continue

            text = _sanitize_text(payload.get("text", ""))
            if not text:
                await websocket.send_json({"type": "error", "message": "Empty message received."})
                continue

            history.append(ChatMessage(role="user", content=text))
            chat_payload = ChatRequest(message=text, messages=history[:-1])
            prompt = _build_prompt(chat_payload, "general")
            try:
                raw_text = _generate_gemini_content(prompt)
                reply, _diagnosis = _extract_reply_and_diagnosis(raw_text)
                reply = _append_safety_disclaimer(reply)
            except Exception as exc:
                reply = f"I’m having trouble generating a response right now: {exc}"

            history.append(ChatMessage(role="assistant", content=reply))
            await websocket.send_json({"type": "transcript", "text": text})
            await websocket.send_json({"type": "ai_message", "text": reply})
    except WebSocketDisconnect:
        return


@router.post("/api/ai/structure-for-field")
async def structure_for_field(
    payload: StructureFieldRequest,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    _assert_ai_configured()
    field_name = str(payload.field_name or "").strip().lower()
    transcribed_text = _sanitize_text(payload.transcribed_text)
    if not transcribed_text:
        raise HTTPException(status_code=400, detail="Transcribed text is required.")

    if field_name not in {"symptoms", "diagnosis", "notes"}:
        raise HTTPException(status_code=400, detail="Unsupported field name.")

    patient_context = ""
    if payload.patient_id is not None:
        patient = (
            db.query(Patient)
            .filter(Patient.id == payload.patient_id, Patient.doctor_id == doctor.id)
            .first()
        )
        if patient is None:
            raise HTTPException(status_code=404, detail="Patient not found.")
        patient_context = f"Patient name: {patient.name}. Age: {patient.age}. Gender: {patient.gender}."

    try:
        if field_name == "symptoms":
            prompt = (
                "You are an Ayurvedic AI assistant. Given this transcribed symptoms description, extract and structure it.\n\n"
                f"Patient context: {patient_context or 'Not provided.'}\n"
                f'Transcribed symptoms description: "{transcribed_text}"\n\n'
                "Extract and structure:\n"
                "Main symptoms (list)\n"
                "Possible dosha imbalance (Vata/Pitta/Kapha)\n"
                "Possible prakriti related insight\n"
                "Possible vikriti\n\n"
                'Return JSON: {"symptoms": [], "dosha": "", "prakriti_insight": "", "vikriti": ""}'
            )
            raw = await call_gemini(
                prompt,
                system_prompt="You structure clinical voice notes into concise Ayurvedic symptom summaries. Return valid JSON only.",
                temperature=0.2,
                response_mime_type="application/json",
                max_output_tokens=400,
            )
            parsed = parse_json_response(raw)
            symptoms = parsed.get("symptoms")
            if not isinstance(symptoms, list):
                symptoms = [str(symptoms or "").strip()] if str(symptoms or "").strip() else []
            structured_text = "\n".join(f"- {str(item).strip()}" for item in symptoms if str(item).strip())
            return JSONResponse(
                {
                    "success": True,
                    "field_name": field_name,
                    "structured_text": structured_text or transcribed_text,
                    "suggestions": {
                        "dosha": str(parsed.get("dosha") or "").strip(),
                        "prakriti_insight": str(parsed.get("prakriti_insight") or "").strip(),
                        "vikriti": str(parsed.get("vikriti") or "").strip(),
                    },
                }
            )

        if field_name == "diagnosis":
            prompt = (
                f'Structure this Ayurvedic diagnosis from: "{transcribed_text}"\n'
                "Make it clinical but concise. Return plain text only."
            )
        else:
            prompt = (
                f'Structure these clinical notes from: "{transcribed_text}"\n'
                "Return concise, doctor-facing notes in plain text with short sentences."
            )

        structured_text = await call_gemini(
            prompt,
            system_prompt="You are a clinic documentation assistant. Rewrite dictated notes into concise, structured medical text. Return plain text only.",
            temperature=0.2,
            max_output_tokens=250,
        )
        clean_text = str(structured_text or "").strip() or transcribed_text
        return JSONResponse({"success": True, "field_name": field_name, "structured_text": clean_text, "suggestions": {}})
    except Exception as exc:
        raise HTTPException(status_code=503, detail="AI structuring is temporarily unavailable. Please type manually.") from exc
