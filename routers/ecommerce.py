from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.rate_limit import limiter
from services.marketing_automation import MarketingAutomation
from services.superapp_service import (
    add_to_cart,
    ai_extract_prescription,
    auto_refill_prescription,
    book_lab_tests,
    bootstrap_superapp,
    calculate_dynamic_price,
    cancel_order,
    checkout,
    get_ai_recommendations,
    get_best_offer,
    get_cart,
    get_dashboard_payload,
    get_health_articles,
    get_lab_packages,
    get_lab_tests,
    get_loyalty,
    get_offers,
    get_order_tracking,
    get_product_categories,
    get_products,
    get_rewards,
    get_store_categories,
    get_support_response,
    get_trending_topics,
    interpret_lab_report,
    redeem_reward,
    reschedule_order,
)


router = APIRouter(tags=["superapp"])
templates = Jinja2Templates(directory=str(settings.templates_dir))
marketing = MarketingAutomation()


@router.get("/superapp/dashboard")
def superapp_dashboard_page(request: Request):
    bootstrap_superapp(force=False)
    return templates.TemplateResponse(request, "dashboard/superapp_dashboard.html", get_dashboard_payload())


@router.get("/subscription/smart-subscriptions")
def smart_subscriptions_page(request: Request):
    payload = get_dashboard_payload()
    payload["offers"] = get_offers()
    return templates.TemplateResponse(request, "subscription/smart_subscriptions.html", payload)


@router.get("/diagnostics/lab-booking")
def lab_booking_page(request: Request):
    return templates.TemplateResponse(
        request,
        "diagnostics/lab_booking.html",
        {
            "packages": get_lab_packages(),
            "labs": bootstrap_superapp(force=False).get("lab_partners", []),
            "tests": get_lab_tests(),
        },
    )


@router.get("/health/articles")
def health_articles_page(request: Request):
    return templates.TemplateResponse(
        request,
        "health/articles.html",
        {
            "articles": get_health_articles(),
            "trending_topics": get_trending_topics(),
        },
    )


@router.get("/store/wellness-store")
def wellness_store_page(request: Request):
    return templates.TemplateResponse(
        request,
        "store/wellness_store.html",
        {
            "store_categories": get_store_categories(),
            "ai_recommendations": get_ai_recommendations(),
            "products": get_products(),
        },
    )


@router.get("/support/ai-assistant")
def ai_support_page(request: Request):
    return templates.TemplateResponse(request, "support/ai_assistant.html", {})


@router.get("/orders/tracking/{order_id}")
def order_tracking_page(request: Request, order_id: int):
    tracking = get_order_tracking(order_id)
    if not tracking.get("success"):
        tracking = {
            "success": False,
            "order": {
                "id": order_id,
                "timeline": [
                    {"status": "Order placed", "timestamp": "Pending", "completed": False},
                    {"status": "Packed & Ready", "timestamp": "Pending", "completed": False},
                    {"status": "Out for Delivery", "timestamp": "Pending", "completed": False},
                    {"status": "Delivered", "timestamp": "Pending", "completed": False},
                ],
                "delivery_partner": "Awaiting assignment",
                "tracking_id": "Unavailable",
            },
            "location": {"eta": "Pending"},
        }
    tracking.update({"request": request, "simple_nav": "orders", "page_hint": "See where your medicine is"})
    return templates.TemplateResponse(request, "orders/tracking.html", tracking)


@router.get("/loyalty/rewards-program")
def rewards_program_page(request: Request):
    return templates.TemplateResponse(
        request,
        "loyalty/rewards_program.html",
        {
            "user": get_loyalty(),
            "rewards": get_rewards(),
        },
    )


@router.get("/api/pharmacy/search")
def pharmacy_search(q: str = "", category: str = "", prescription_required: bool | None = None):
    return JSONResponse({"products": get_products(q, category, prescription_required)})


@router.post("/api/prescription/upload")
async def prescription_upload(request: Request):
    form = await request.form()
    filename = str(getattr(form.get("file"), "filename", "") or "")
    return JSONResponse({"success": True, "filename": filename, "extracted_medicines": ai_extract_prescription(filename)})


@router.get("/api/pharmacy/categories")
def pharmacy_categories():
    return JSONResponse({"categories": get_product_categories()})


@router.post("/api/cart/add")
@limiter.limit("30/minute")
async def cart_add(request: Request):
    payload = await request.json()
    return JSONResponse(add_to_cart(int(payload.get("product_id", 0) or 0), int(payload.get("quantity", 1) or 1), str(payload.get("user_id", "guest") or "guest")))


@router.get("/api/cart")
def cart_view(user_id: str = "guest"):
    return JSONResponse(get_cart(user_id))


@router.post("/api/checkout")
@limiter.limit("10/minute")
async def checkout_api(request: Request):
    payload = await request.json() if request.headers.get("content-type", "").lower().startswith("application/json") else {}
    return JSONResponse(checkout(str(payload.get("user_id", "guest") or "guest")))


@router.get("/api/offers/available")
def available_offers(user_id: str = "guest"):
    return JSONResponse({"offers": get_offers(user_id)})


@router.get("/api/offers/best")
def best_offer(user_id: str = "guest"):
    return JSONResponse(get_best_offer(user_id) or {})


@router.get("/api/labs/tests")
def lab_tests_api(q: str = ""):
    return JSONResponse({"tests": get_lab_tests(q), "packages": get_lab_packages()})


@router.post("/api/labs/book")
@limiter.limit("10/minute")
async def lab_book(request: Request):
    payload = await request.json()
    return JSONResponse(
        book_lab_tests(
            [int(item) for item in payload.get("test_ids", []) if str(item).isdigit()],
            str(payload.get("collection_address", "")).strip(),
            str(payload.get("collection_time", "")).strip(),
            str(payload.get("user_id", "guest") or "guest"),
        )
    )


@router.get("/api/labs/report/{test_id}")
def lab_report(test_id: int):
    return JSONResponse({"test_id": test_id, "status": "completed", "report_summary": "Report ready for AI interpretation.", "download_url": f"/api/labs/report/{test_id}"})


@router.post("/api/labs/interpret")
async def labs_interpret(request: Request):
    payload = await request.json()
    return JSONResponse(interpret_lab_report(str(payload.get("report_text", ""))))


@router.get("/api/orders/{order_id}/track")
def order_track(order_id: int):
    return JSONResponse(get_order_tracking(order_id))


@router.get("/api/orders/{order_id}/location")
def order_location(order_id: int):
    tracking = get_order_tracking(order_id)
    return JSONResponse(tracking.get("location", {"lat": 28.6139, "lng": 77.2090, "eta": "25 min"}))


@router.post("/api/orders/{order_id}/cancel")
def order_cancel(order_id: int):
    return JSONResponse(cancel_order(order_id))


@router.post("/api/orders/{order_id}/reschedule")
async def order_reschedule(order_id: int, request: Request):
    payload = await request.json()
    return JSONResponse(reschedule_order(order_id, str(payload.get("estimated_delivery", "")).strip()))


@router.get("/api/loyalty/points")
def loyalty_points(user_id: str = "guest"):
    return JSONResponse(get_loyalty(user_id))


@router.post("/api/loyalty/redeem")
async def loyalty_redeem(request: Request):
    payload = await request.json()
    return JSONResponse(redeem_reward(str(payload.get("reward_id", "")).strip(), str(payload.get("user_id", "guest") or "guest")))


@router.get("/api/loyalty/rewards")
def loyalty_rewards():
    return JSONResponse({"rewards": get_rewards()})


@router.post("/api/marketing/send-reminder")
async def marketing_send_reminder(request: Request):
    payload = await request.json()
    action = str(payload.get("type", "abandoned_cart")).strip().lower()
    user_id = str(payload.get("user_id", "guest") or "guest")
    if action == "refill":
        return JSONResponse(marketing.send_refill_reminder(user_id, payload.get("subscription", {})))
    if action == "health_tip":
        return JSONResponse(marketing.send_health_tips(user_id, str(payload.get("condition", "wellness"))))
    if action == "birthday":
        return JSONResponse(marketing.birthday_campaign(user_id))
    return JSONResponse(marketing.send_abandoned_cart_reminder(user_id, [str(item) for item in payload.get("cart_items", [])]))


@router.get("/api/marketing/personalized-offers")
def marketing_offers(user_id: str = "guest"):
    return JSONResponse({"offers": get_offers(user_id)})


@router.post("/api/support/chat")
@limiter.limit("20/minute")
async def support_chat(request: Request):
    payload = await request.json()
    return JSONResponse(get_support_response(str(payload.get("message", ""))))


@router.get("/api/superapp/dashboard")
def dashboard_api(user_id: str = "guest"):
    return JSONResponse(get_dashboard_payload(user_id))


@router.get("/api/store/recommendations")
def store_recommendations(user_id: str = "guest"):
    return JSONResponse({"products": get_ai_recommendations(user_id)})


@router.get("/api/store/categories")
def store_categories():
    return JSONResponse({"categories": get_store_categories()})


@router.get("/api/articles/search")
def article_search(q: str = ""):
    return JSONResponse({"articles": get_health_articles(q), "trending_topics": get_trending_topics()})


@router.post("/api/prescriptions/auto-refill")
async def prescription_auto_refill(request: Request):
    payload = await request.json()
    return JSONResponse(
        auto_refill_prescription(
            str(payload.get("user_id", "guest") or "guest"),
            str(payload.get("prescription_name", "Prescription") or "Prescription"),
            payload.get("medicines", []),
            int(payload.get("days_left", 0) or 0),
        )
    )


@router.get("/api/pricing/dynamic/{product_id}")
def dynamic_pricing(product_id: int, user_id: str = "guest"):
    return JSONResponse(calculate_dynamic_price(product_id, user_id))
