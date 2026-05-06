from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Body, WebSocket, WebSocketDisconnect

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
async def assign_delivery_partner(order_id: int, payload: dict[str, Any] = Body(...)):
    result = await delivery_service.assign_delivery_partner(order_id, payload.get("pharmacy_location", {}), payload.get("customer_location", {}))
    return result


@router.get("/api/delivery/track/{order_id}")
async def track_order(order_id: int):
    return await delivery_service.track_live_location(order_id)


@router.post("/api/delivery/optimize-batch")
async def optimize_batch_delivery(orders: list[dict[str, Any]] = Body(...)):
    return await delivery_service.optimize_batch_delivery(orders)


@router.get("/api/delivery/predict-time/{order_id}")
async def predict_delivery_time(order_id: int):
    history = await delivery_service.order_history(order_id)
    return await delivery_service.predict_delivery_time(history)
