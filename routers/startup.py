from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from services.startup_service import (
    claim_referral_bonus,
    get_demo_inventory_snapshot,
    get_competitor_matrix,
    get_growth_metrics,
    get_investor_demo_payload,
    get_panchakarma_centers,
    get_personalized_kits,
    get_referral_snapshot,
    get_social_proof_activity,
    get_waitlist_snapshot,
    get_verified_practitioners,
    get_verified_testimonials,
    get_wellness_feed,
    join_waitlist,
)


router = APIRouter(tags=["startup"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


@router.get("/marketplace/panchakarma-booking")
def panchakarma_booking_page(request: Request):
    centers = get_panchakarma_centers()
    return templates.TemplateResponse(
        request,
        "marketplace/panchakarma_booking.html",
        {
            "centers": centers,
            "center_count": len(centers),
            "comparison_rows": get_competitor_matrix(),
        },
    )


@router.get("/trust/verified-practitioners")
def verified_practitioners_page(request: Request):
    return templates.TemplateResponse(
        request,
        "trust/verified_practitioners.html",
        {
            "practitioners": get_verified_practitioners(),
            "testimonials": get_verified_testimonials(),
            "comparison_rows": get_competitor_matrix(),
        },
    )


@router.get("/community/wellness-feed")
def community_feed_page(request: Request):
    return templates.TemplateResponse(
        request,
        "community/wellness_feed.html",
        {
            "feed": get_wellness_feed(),
            "challenge": {
                "name": "30-day Ayurveda morning routine challenge",
                "participants": 1234,
                "progress": 67,
            },
        },
    )


@router.get("/growth/referral-system")
def referral_system_page(request: Request):
    return templates.TemplateResponse(
        request,
        "growth/referral_system.html",
        get_referral_snapshot(),
    )


@router.get("/growth/waitlist")
def waitlist_page(request: Request):
    return templates.TemplateResponse(
        request,
        "growth/waitlist.html",
        get_waitlist_snapshot(),
    )


@router.get("/investor-demo")
def investor_demo_page(request: Request):
    payload = get_investor_demo_payload()
    return templates.TemplateResponse(
        request,
        "investor_demo.html",
        payload,
    )


@router.get("/launch/press-kit")
def press_kit_page(request: Request):
    return templates.TemplateResponse(
        request,
        "launch/press_kit.html",
        {"comparison_rows": get_competitor_matrix()},
    )


@router.get("/admin/growth-dashboard")
def growth_dashboard_page(request: Request):
    payload = get_growth_metrics()
    payload["inventory"] = get_demo_inventory_snapshot()
    return templates.TemplateResponse(
        request,
        "admin/growth_dashboard.html",
        payload,
    )


@router.get("/api/startup/personalized-kits")
def personalized_kits_api():
    return JSONResponse(get_personalized_kits())


@router.post("/api/referral/claim")
async def claim_referral(request: Request):
    payload = await request.json()
    result = claim_referral_bonus(
        str(payload.get("referral_code", "")).strip(),
        str(payload.get("email", "")).strip(),
    )
    return JSONResponse(result, status_code=200 if result.get("success") else 400)


@router.post("/api/waitlist/join")
async def waitlist_join(request: Request):
    payload = await request.json()
    result = join_waitlist(str(payload.get("email", "")).strip())
    return JSONResponse(result, status_code=200 if result.get("success") else 400)


@router.get("/api/social-proof/activity")
def social_proof_activity():
    return JSONResponse({"activity": get_social_proof_activity()})
