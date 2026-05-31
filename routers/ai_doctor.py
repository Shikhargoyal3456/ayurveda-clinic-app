from __future__ import annotations

import json
import logging
import re
from typing import Any

import google.generativeai as genai
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.portal_auth import require_portal_roles
from models.user import User
from shared.template_engine import render_template
from shared.template_engine import templates


router = APIRouter(tags=["ai-doctor"])
logger = logging.getLogger(__name__)

DOCTOR_SYSTEM_PROMPT = """You are Dr. Kash, a warm, empathetic, experienced AI doctor. Rules:

PERSONALITY: Warm, calm, reassuring. Simple language. Acknowledge feelings first.

PANIC HANDLING: If patient says scared/panicking - say: "I hear you. You're safe. Let's breathe together. Breathe in for 4... hold... breathe out for 4..." Only continue after they're calmer.

CONSULTATION FLOW:
1. Greet warmly
2. Ask ONE question at a time
3. Gather: symptoms, duration, severity (1-10), location, triggers
4. After 4-5 exchanges: give 2-3 possible diagnoses
5. Recommend: home care or "see a doctor urgently"

DIAGNOSIS FORMAT - append at end when ready:
|||DIAGNOSIS|||{"items":[{"name":"Condition","confidence":70,"color":"#3b82f6"},{"name":"Second","confidence":20,"color":"#8b5cf6"}]}|||END|||

EMERGENCY: Chest pain + left arm → "Call emergency services NOW" | Can't breathe → "Call 911 immediately"

RESPONSE STYLE: SHORT (2-3 sentences). Natural spoken language. End with a question.

SAFETY: End with: "This is AI guidance only — please see a real doctor for treatment.""""

DIAGNOSIS_PATTERN = re.compile(r"\|\|\|DIAGNOSIS\|\|\|(.*?)\|\|\|END\|\|\|", re.DOTALL)


class DoctorChatMessage(BaseModel):
    role: str = Field(default="user")
    content: str = Field(default="")


class DoctorChatPayload(BaseModel):
    message: str = Field(default="")
    messages: list[DoctorChatMessage | dict[str, Any]] = Field(default_factory=list)


def _normalize_history(messages: list[DoctorChatMessage | dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in messages:
        if isinstance(item, DoctorChatMessage):
            role = item.role
            content = item.content
        else:
            role = str(item.get("role", "user"))
            content = str(item.get("content", item.get("message", "")))
        role = role.strip().lower()
        content = content.strip()
        if not content or role not in {"user", "assistant", "system"}:
            continue
        normalized.append({"role": role, "content": content})
    return normalized


def _build_prompt(history: list[dict[str, str]]) -> str:
    lines = [DOCTOR_SYSTEM_PROMPT, "", "Conversation so far:"]
    if not history:
        lines.append("Patient: Hello")
    else:
        for item in history:
            speaker = "Patient" if item["role"] == "user" else "Dr. Kash" if item["role"] == "assistant" else "System"
            lines.append(f"{speaker}: {item['content']}")
    lines.append("")
    lines.append("Reply as Dr. Kash now.")
    return "\n".join(lines)


def _extract_diagnosis(text: str) -> tuple[str, dict[str, Any]]:
    diagnosis = {"items": []}
    match = DIAGNOSIS_PATTERN.search(text or "")
    if match:
        try:
            parsed = json.loads(match.group(1).strip())
            if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
                diagnosis = parsed
        except json.JSONDecodeError:
            logger.warning("Could not parse AI doctor diagnosis payload.")
    clean_text = DIAGNOSIS_PATTERN.sub("", text or "").strip()
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)
    return clean_text, diagnosis


def _generate_doctor_reply(history: list[dict[str, str]]) -> tuple[str, dict[str, Any]]:
    if not settings.gemini_api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is missing.")

    try:
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(_build_prompt(history))
    except Exception as exc:  # pragma: no cover
        logger.exception("Gemini AI doctor request failed: %s", exc)
        raise HTTPException(status_code=502, detail="AI doctor service is unavailable right now.") from exc

    raw_text = getattr(response, "text", "") or ""
    if not raw_text and getattr(response, "candidates", None):
        parts: list[str] = []
        for candidate in response.candidates:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", []) or []:
                part_text = getattr(part, "text", "")
                if part_text:
                    parts.append(part_text)
        raw_text = "\n".join(parts).strip()

    if not raw_text:
        raise HTTPException(status_code=502, detail="AI doctor returned an empty response.")

    return _extract_diagnosis(raw_text)


@router.post("/api/doctor/chat")
async def ai_doctor_chat(payload: DoctorChatPayload):
    history = _normalize_history(payload.messages)
    message = payload.message.strip()

    if message:
        history.append({"role": "user", "content": message})

    reply, diagnosis = _generate_doctor_reply(history)
    return {"reply": reply, "diagnosis": diagnosis}


@router.get("/ai-doctor")
async def ai_doctor_page(request: Request, user: User = Depends(require_portal_roles("patient"))):
    return render_template(
        templates,
        request,
        "ai_doctor.html",
        {
            "active_page": "consult",
            "user_name": user.full_name or "Patient",
            "user_role": "AI Doctor Consultation",
            "avatar_label": "DR",
            "page_hint": "Live, multimodal AI guidance with calm support",
            "book_appointment_url": "/telemedicine/book",
        },
    )


@router.get("/ai-doctor-live")
async def ai_doctor_live_page(request: Request):
    return render_template(templates, request, "doctor.html")
