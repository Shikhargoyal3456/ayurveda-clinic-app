from __future__ import annotations

from typing import Any

from services.marketplace_service import marketplace_nearby_shops


def search_scopes_for_role(role: str) -> list[str]:
    scopes = {
        "patient": ["medicines", "orders", "prescriptions"],
        "pharmacy": ["orders", "inventory", "customers"],
        "doctor": ["patients", "appointments", "prescriptions"],
        "lab": ["tests", "bookings", "reports"],
        "partner": ["assignments", "routes", "payouts"],
    }
    return scopes.get(role, ["search"])


def global_search(role: str, query: str) -> dict[str, Any]:
    normalized = query.strip().lower()
    nearby = marketplace_nearby_shops()
    pharmacies = [
        {"type": "pharmacy", "name": item["name"], "match": "store"}
        for item in nearby.get("pharmacies", [])
        if normalized in item["name"].lower()
    ]
    labs = [
        {"type": "lab", "name": item["name"], "match": "lab"}
        for item in nearby.get("labs", [])
        if normalized in item["name"].lower()
    ]
    generic = []
    if normalized:
        for scope in search_scopes_for_role(role):
            generic.append({"type": scope, "name": f"{query.title()} in {scope}", "match": scope})
    return {"query": query, "scopes": search_scopes_for_role(role), "results": pharmacies + labs + generic[:5]}
