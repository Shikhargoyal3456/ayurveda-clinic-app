from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from app.services.ai_service import analyze_symptoms
router = APIRouter()


class SymptomRequest(BaseModel):
    symptoms: str


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return RedirectResponse(url="/new", status_code=303)


@router.get("/ai_analyzer", response_class=HTMLResponse)
async def ai_analyzer(request: Request):
    return RedirectResponse(url="/ai-analyzer", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return RedirectResponse(url="/auth/login", status_code=303)


@router.get("/signup", response_class=HTMLResponse)
async def signup(request: Request):
    return RedirectResponse(url="/new/signup", status_code=303)


@router.get("/appointments", response_class=HTMLResponse)
async def appointments(request: Request):
    return RedirectResponse(url="/appointments", status_code=303)


@router.get("/followups", response_class=HTMLResponse)
async def followups(request: Request):
    return RedirectResponse(url="/followups", status_code=303)


@router.get("/schedule", response_class=HTMLResponse)
async def schedule(request: Request):
    return RedirectResponse(url="/schedule", status_code=303)


@router.get("/add_case", response_class=HTMLResponse)
async def add_case(request: Request):
    return RedirectResponse(url="/patients/1/cases/new", status_code=303)


@router.get("/view_cases", response_class=HTMLResponse)
async def view_cases(request: Request):
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/analyze")
async def analyze(data: SymptomRequest):
    try:
        return {"response": analyze_symptoms(data.symptoms)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
