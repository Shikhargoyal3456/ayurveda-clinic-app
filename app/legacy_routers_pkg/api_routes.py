from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.config import TEMPLATES_DIR
from app.services.ai_service import analyze_symptoms


templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter()


class SymptomRequest(BaseModel):
    symptoms: str


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {})


@router.get("/ai_analyzer", response_class=HTMLResponse)
async def ai_analyzer(request: Request):
    return templates.TemplateResponse(request, "ai_analyzer.html", {})


@router.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@router.get("/signup", response_class=HTMLResponse)
async def signup(request: Request):
    return templates.TemplateResponse(request, "signup.html", {})


@router.get("/appointments", response_class=HTMLResponse)
async def appointments(request: Request):
    return templates.TemplateResponse(request, "appointments.html", {})


@router.get("/followups", response_class=HTMLResponse)
async def followups(request: Request):
    return templates.TemplateResponse(request, "followups.html", {})


@router.get("/schedule", response_class=HTMLResponse)
async def schedule(request: Request):
    return templates.TemplateResponse(request, "schedule.html", {})


@router.get("/add_case", response_class=HTMLResponse)
async def add_case(request: Request):
    return templates.TemplateResponse(request, "add_case.html", {})


@router.get("/view_cases", response_class=HTMLResponse)
async def view_cases(request: Request):
    return templates.TemplateResponse(request, "view_cases.html", {})


@router.post("/analyze")
async def analyze(data: SymptomRequest):
    try:
        return {"response": analyze_symptoms(data.symptoms)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
