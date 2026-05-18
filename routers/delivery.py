from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.auth import get_current_doctor
from app.config import settings
from app.database import get_db
from app.models import Doctor
from app.portal_auth import get_portal_user
from models.user import User
from services.cache_service import cache_get_json_async, cache_set_json_async
from services.delivery_service import ZomatoStyleDeliveryService


router = APIRouter(tags=["delivery"])
delivery_service = ZomatoStyleDeliveryService()


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[int, WebSocket] = {}

    async def connect(self, order_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[order_id] = websocket

    def disconnect(self, order_id: int) -> None:
        self.active_connections.pop(order_id, None)

    async def send_location_update(self, order_id: int, data: dict[str, Any]) -> None:
        websocket = self.active_connections.get(order_id)
        if websocket is not None:
            await websocket.send_json(data)


manager = ConnectionManager()


def _doctor_is_admin(doctor: Doctor) -> bool:
    configured = [item.strip().lower() for item in settings.admin_usernames if item.strip()]
    allowed_admins = configured or ["admin@ayurveda.com"]
    dev_admin_by_id = not settings.is_production and int(getattr(doctor, "id", 0) or 0) == 1
    return (doctor.username or "").strip().lower() in allowed_admins or dev_admin_by_id


def require_delivery_access(request: Request, db: Session = Depends(get_db)) -> User | Doctor:
    portal_user = get_portal_user(request, db)
    if portal_user is not None:
        current_role = portal_user.role.value if hasattr(portal_user.role, "value") else str(portal_user.role)
        if current_role in {"delivery_partner", "pharmacy_owner", "admin"}:
            return portal_user

    try:
        doctor = get_current_doctor(request, db)
    except HTTPException as exc:
        if exc.status_code not in {303, 307}:
            raise
    else:
        if _doctor_is_admin(doctor):
            return doctor

    raise HTTPException(status_code=303, headers={"Location": "/auth/login/partner"})


@router.websocket("/ws/order-tracking/{order_id}")
async def websocket_tracking(websocket: WebSocket, order_id: int):
    await manager.connect(order_id, websocket)
    try:
        while True:
            location = await delivery_service.track_live_location(order_id)
            if location:
                await manager.send_location_update(order_id, location)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        manager.disconnect(order_id)


@router.post("/api/delivery/find-pharmacy")
async def find_nearest_pharmacy(payload: dict[str, Any] = Body(...)):
    result = await delivery_service.find_nearest_pharmacy(payload.get("user_location", {}), payload.get("medicines", []))
    return result


@router.post("/api/delivery/assign/{order_id}")
async def assign_delivery_partner(
    order_id: int,
    payload: dict[str, Any] = Body(...),
    user: User | Doctor = Depends(require_delivery_access),
):
    _ = user
    result = await delivery_service.assign_delivery_partner(order_id, payload.get("pharmacy_location", {}), payload.get("customer_location", {}))
    return result


@router.get("/api/delivery/track/{order_id}")
async def track_order(order_id: int):
    cache_key = f"delivery-track:{order_id}"
    cached = await cache_get_json_async(cache_key)
    if cached is not None:
        return cached
    payload = await delivery_service.track_live_location(order_id)
    await cache_set_json_async(cache_key, payload, ttl_seconds=15)
    return payload


@router.post("/api/delivery/optimize-batch")
async def optimize_batch_delivery(
    orders: list[dict[str, Any]] = Body(...),
    user: User | Doctor = Depends(require_delivery_access),
):
    _ = user
    return await delivery_service.optimize_batch_delivery(orders)


@router.get("/api/delivery/predict-time/{order_id}")
async def predict_delivery_time(order_id: int):
    history = await delivery_service.order_history(order_id)
    return await delivery_service.predict_delivery_time(history)
