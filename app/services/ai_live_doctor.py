from __future__ import annotations

import asyncio
import base64
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from models.user import User
from services.ai_provider import (
    GEMINI_MODEL,
    build_gemini_part,
    generate_gemini_content,
    is_gemini_configured,
)
from services.medicine_api_service import MedicineAPIService


logger = logging.getLogger(__name__)

OPENING_DISCLAIMER = "I'm an AI doctor assistant. For final diagnosis and treatment, please consult a real doctor."
FINAL_DISCLAIMER = "Remember, a real doctor should confirm any diagnosis or treatment plan."

AI_DOCTOR_SYSTEM_PROMPT = """
You are Dr. Kash, an AI doctor assistant with the bedside manner of an experienced clinician.

Communication style:
- Professional, calm, knowledgeable, and compassionate
- Use medical terminology when useful, then explain it simply
- Ask focused follow-up questions before narrowing the assessment
- Sound organized and clinically thoughtful, but do not imply you are a licensed physician

What to do:
- Start by saying: "I'm an AI doctor assistant. For final diagnosis and treatment, please consult a real doctor."
- End by saying: "Remember, a real doctor should confirm any diagnosis or treatment plan."
- Take a structured history: onset, severity, duration, triggers, relieving factors, prior episodes, medication use, allergies, and family history when relevant
- If useful, guide simple camera-based exam steps such as showing the area, moving a joint, or taking a deep breath
- Give a cautious differential diagnosis with rough probabilities when appropriate
- Explain what the patient can monitor, what home measures are typically used, and when a real doctor should evaluate
- Be especially supportive and validating with anxiety or low mood

Critical safety rules:
- Never claim certainty
- Never present a remote impression as a confirmed diagnosis
- Never provide a personalized prescription or act as if you have legally prescribed treatment
- If medicines are discussed, keep it educational and state that a real clinician must confirm dose, interactions, and suitability
- If symptoms sound emergent, advise urgent in-person care immediately
- If information is incomplete, say you need more information

Preferred response format when enough information exists:
1. What I think is going on
2. Most likely possibilities with rough probabilities
3. What you can do now
4. Red flags that require urgent care
5. Follow-up plan
""".strip()

EMERGENCY_RESPONSE = (
    f"{OPENING_DISCLAIMER} "
    "⚠️ I'm concerned. Please seek immediate medical attention. "
    "⏰ Do not wait. Go to the emergency room now. "
    "📞 Call emergency services in India (112) right away. "
    "If someone is with you, ask them to stay nearby and help right now. "
    f"{FINAL_DISCLAIMER}"
)

CALMING_RESPONSE = (
    f"{OPENING_DISCLAIMER} "
    "I understand your concern. Let me connect you with AI for proper guidance. "
    f"{FINAL_DISCLAIMER}"
)

FALLBACK_RESPONSE = (
    f"{OPENING_DISCLAIMER} "
    "I understand your concern. Let me connect you with AI for proper guidance. "
    f"{FINAL_DISCLAIMER}"
)

EMERGENCY_PATTERNS = {
    "chest pain",
    "heart attack",
    "difficulty breathing",
    "trouble breathing",
    "severe bleeding",
    "loss of consciousness",
    "passed out",
    "fainted",
    "seizure",
    "suicidal thoughts",
    "want to die",
    "kill myself",
}

LOW_MOOD_PATTERNS = {
    "depressed",
    "hopeless",
    "very sad",
    "anxious",
    "panic",
    "scared",
    "lonely",
    "overwhelmed",
    "can't sleep",
    "cant sleep",
}

MEDICINE_LOOKUP_PATTERN = re.compile(
    r"(?:medicine|tablet|capsule|drug|dose|dosage|side effects? of|about)\s+(?P<name>[A-Za-z][A-Za-z0-9+\- ]{1,60})",
    re.IGNORECASE,
)


@dataclass
class LiveDoctorSession:
    session_id: str
    user_id: int
    user_name: str
    transcript: list[str] = field(default_factory=list)
    last_frame_bytes: bytes | None = None
    last_frame_mime: str = "image/jpeg"
    last_visual_summary: str = ""
    last_frame_analysis_at: float = 0.0
    last_user_text: str = ""
    audio_chunks_received: int = 0
    turn_count: int = 0


class AILiveDoctorService:
    def __init__(self) -> None:
        self._sessions: dict[str, LiveDoctorSession] = {}
        self._medicine_api = MedicineAPIService()

    def start_session(self, user: User) -> tuple[LiveDoctorSession, list[dict[str, Any]]]:
        session = LiveDoctorSession(
            session_id=str(uuid.uuid4()),
            user_id=int(user.id),
            user_name=user.full_name or "Patient",
        )
        self._sessions[session.session_id] = session
        greeting = (
            f"Hello {session.user_name}. {OPENING_DISCLAIMER} "
            "I can take a structured history, review what you show on camera, and explain the most likely possibilities and next steps. "
            f"{FINAL_DISCLAIMER}"
        )
        return session, [
            {"type": "session_ready", "session_id": session.session_id},
            {"type": "ai_message", "text": greeting},
            {"type": "status", "status": "connected", "detail": "AI doctor is ready."},
        ]

    def close_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def handle_event(self, session_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        session = self._sessions.get(session_id)
        if session is None:
            return [{"type": "error", "message": "Consultation session not found."}]

        event_type = str(payload.get("type") or "").strip().lower()
        if event_type == "ping":
            return [{"type": "pong", "ts": int(time.time())}]
        if event_type == "audio_chunk":
            session.audio_chunks_received += 1
            return [{"type": "status", "status": "listening", "detail": "Audio received in real time only."}]
        if event_type == "video_frame":
            return await self._handle_video_frame(session, payload)
        if event_type == "user_text":
            return await self._handle_user_text(session, str(payload.get("text") or ""))
        if event_type == "end_consultation":
            summary = self._build_consultation_summary(session)
            self.close_session(session_id)
            return [
                {"type": "consultation_summary", "summary": summary},
                {"type": "status", "status": "ended", "detail": "Consultation ended. No audio or video was stored."},
            ]
        return [{"type": "error", "message": f"Unsupported event type: {event_type}"}]

    async def _handle_video_frame(self, session: LiveDoctorSession, payload: dict[str, Any]) -> list[dict[str, Any]]:
        image_data = str(payload.get("image") or "")
        mime_type = str(payload.get("mime_type") or "image/jpeg")
        if not image_data:
            return [{"type": "status", "status": "camera", "detail": "No frame data received."}]

        try:
            session.last_frame_bytes = base64.b64decode(image_data)
            session.last_frame_mime = mime_type
        except Exception:
            return [{"type": "status", "status": "camera", "detail": "Could not decode camera frame."}]

        now = time.time()
        if now - session.last_frame_analysis_at < 6:
            return [{"type": "status", "status": "camera", "detail": "Frame captured for live review only."}]

        session.last_frame_analysis_at = now
        visual_summary = await self._analyze_visual_context(session)
        if not visual_summary:
            return [{"type": "status", "status": "camera", "detail": "Frame captured for live review only."}]

        session.last_visual_summary = visual_summary
        return [{"type": "vision_update", "text": visual_summary}]

    async def _handle_user_text(self, session: LiveDoctorSession, text: str) -> list[dict[str, Any]]:
        clean_text = " ".join(text.split()).strip()
        if not clean_text:
            return [{"type": "status", "status": "idle", "detail": "Waiting for patient input."}]

        session.last_user_text = clean_text
        session.turn_count += 1
        session.transcript.append(f"Patient: {clean_text}")
        events: list[dict[str, Any]] = [{"type": "transcript", "speaker": "patient", "text": clean_text}]

        emergency_hit = self._detect_emergency(clean_text)
        if emergency_hit:
            events.append({"type": "emergency", "trigger": emergency_hit, "text": EMERGENCY_RESPONSE})
            events.append({"type": "ai_message", "text": EMERGENCY_RESPONSE})
            session.transcript.append(f"Doctor: {EMERGENCY_RESPONSE}")
            return events

        medicine_context = await self._maybe_lookup_medicine(clean_text)
        if medicine_context:
            events.append({"type": "medicine_lookup", "payload": medicine_context})

        ai_text = await self._generate_doctor_reply(
            session=session,
            user_text=clean_text,
            visual_summary=session.last_visual_summary,
            medicine_context=medicine_context,
            emotional_support=self._needs_emotional_support(clean_text),
        )
        session.transcript.append(f"Doctor: {ai_text}")
        events.append({"type": "ai_message", "text": ai_text})
        return events

    async def _generate_doctor_reply(
        self,
        *,
        session: LiveDoctorSession,
        user_text: str,
        visual_summary: str,
        medicine_context: dict[str, Any] | None,
        emotional_support: bool,
    ) -> str:
        if self._detect_emergency(user_text):
            return EMERGENCY_RESPONSE
        if emotional_support and any(term in user_text.lower() for term in ("anxious", "panic", "worried")):
            return CALMING_RESPONSE
        if session.turn_count <= 2:
            return await self._structured_interview_reply(user_text, visual_summary)

        prompt_sections = [
            f"Patient message: {user_text}",
            f"Visual findings from camera: {visual_summary or 'No clear visual symptom analysis yet.'}",
            f"Emotional support needed: {'yes' if emotional_support else 'no'}",
            f"Consultation turn number: {session.turn_count}",
            "If history is still incomplete, ask focused follow-up questions first.",
            "Do not provide a personalized prescription. If discussing medicines, keep it educational and state that a real clinician must confirm dose and safety.",
        ]
        if medicine_context:
            prompt_sections.append(f"Medicine lookup context: {medicine_context}")
        prompt_sections.append("Respond as a clinically structured AI doctor assistant.")
        user_prompt = "\n\n".join(prompt_sections)

        if not is_gemini_configured():
            return self._fallback_text(user_text, emotional_support=emotional_support, visual_summary=visual_summary, medicine_context=medicine_context)

        try:
            return await asyncio.to_thread(self._gemini_text_completion, user_prompt)
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            logger.exception("AI doctor text response failed: %s", exc)
            return self._fallback_text(user_text, emotional_support=emotional_support, visual_summary=visual_summary, medicine_context=medicine_context)

    def _gemini_text_completion(self, user_prompt: str) -> str:
        response_text = generate_gemini_content(
            user_prompt,
            system_instruction=AI_DOCTOR_SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=700,
            model_name=GEMINI_MODEL,
        )
        return self._ensure_disclaimer(response_text or FALLBACK_RESPONSE)

    async def _analyze_visual_context(self, session: LiveDoctorSession) -> str:
        if session.last_frame_bytes is None:
            return ""
        if not is_gemini_configured():
            return ""
        try:
            return await asyncio.to_thread(self._gemini_visual_completion, session.last_frame_bytes, session.last_frame_mime)
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            logger.warning("AI doctor vision analysis failed: %s", exc)
            return ""

    def _gemini_visual_completion(self, image_bytes: bytes, mime_type: str) -> str:
        response_text = generate_gemini_content(
            [
                "Give a short visual observation for a telehealth intake. Mention only visible signs, uncertainty, and any red flags. Avoid overclaiming.",
                build_gemini_part(image_bytes, mime_type),
            ],
            temperature=0.2,
            max_output_tokens=180,
            model_name=GEMINI_MODEL,
        )
        return response_text.strip()[:400]

    async def _maybe_lookup_medicine(self, text: str) -> dict[str, Any] | None:
        match = MEDICINE_LOOKUP_PATTERN.search(text)
        if not match:
            return None

        medicine_name = match.group("name").strip(" .,!?:;")
        if len(medicine_name) < 2:
            return None

        def lookup() -> dict[str, Any]:
            external = self._medicine_api.search_external_medicines(medicine_name)
            return {
                "query": medicine_name,
                "matches": external[:3],
                "top_match": external[0] if external else None,
            }

        try:
            return await asyncio.to_thread(lookup)
        except Exception as exc:
            logger.warning("Medicine lookup failed for %s: %s", medicine_name, exc)
            return {"query": medicine_name, "matches": [], "top_match": None}

    def _detect_emergency(self, text: str) -> str | None:
        haystack = text.lower()
        for pattern in EMERGENCY_PATTERNS:
            if pattern in haystack:
                return pattern
        return None

    def _needs_emotional_support(self, text: str) -> bool:
        haystack = text.lower()
        return any(pattern in haystack for pattern in LOW_MOOD_PATTERNS)

    async def _structured_interview_reply(self, patient_message: str, context: str) -> str:
        """Use AI for interview responses, not scripted text."""
        if not is_gemini_configured():
            return "I understand your concern. Let me connect you with AI for proper guidance. (AI assistant - not a doctor)"

        visual_context = f"Previous visual context: {context}" if context else "Previous visual context: none"
        prompt = (
            "You are Dr. Kash, a compassionate medical assistant.\n\n"
            f"{visual_context}\n"
            f"Patient says: {patient_message}\n\n"
            "Provide a natural, structured medical interview response. "
            "Ask ONE relevant follow-up question about symptoms, duration, or severity. "
            "Be calm and professional. Keep the response under 50 words. "
            "Always include: \"Remember, I'm an AI assistant.\""
        )
        try:
            response = await asyncio.to_thread(self._gemini_text_completion, prompt)
            return response
        except Exception:
            return "I understand your concern. Let me connect you with AI for proper guidance. (AI assistant - not a doctor)"

    def _fallback_text(
        self,
        user_text: str,
        *,
        emotional_support: bool,
        visual_summary: str,
        medicine_context: dict[str, Any] | None,
    ) -> str:
        return (
            f"{OPENING_DISCLAIMER} "
            "I understand your concern. Let me connect you with AI for proper guidance. "
            f"{FINAL_DISCLAIMER}"
        )

    def _build_consultation_summary(self, session: LiveDoctorSession) -> dict[str, Any]:
        patient_lines = [line.removeprefix("Patient: ").strip() for line in session.transcript if line.startswith("Patient:")]
        doctor_lines = [line.removeprefix("Doctor: ").strip() for line in session.transcript if line.startswith("Doctor:")]
        return {
            "session_id": session.session_id,
            "patient_name": session.user_name,
            "messages": len(session.transcript),
            "patient_summary": patient_lines[-3:],
            "doctor_summary": doctor_lines[-2:],
            "visual_summary": session.last_visual_summary,
            "book_real_doctor_url": "/telemedicine/book",
            "book_appointment_url": "/appointments",
        }

    def _ensure_disclaimer(self, text: str) -> str:
        clean_text = " ".join((text or "").split()).strip()
        if not clean_text:
            clean_text = FALLBACK_RESPONSE
        if OPENING_DISCLAIMER.lower() not in clean_text.lower():
            clean_text = f"{OPENING_DISCLAIMER} {clean_text}"
        if FINAL_DISCLAIMER.lower() not in clean_text.lower():
            clean_text = f"{clean_text} {FINAL_DISCLAIMER}"
        return clean_text
