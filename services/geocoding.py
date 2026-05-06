from __future__ import annotations

import math
import time
from typing import Any

import requests

from app.analytics import track_error_event
from app.config import settings
from services.cache_service import cache_get_json, cache_set_json


# GRAND-UNIFIED-1: Cached Google Places lookup with static fallback keeps checkout usable during API denial/outage.
_CACHE_TTL_SECONDS = 900
_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}

GURUGRAM_CENTER = {"lat": 28.4595, "lng": 77.0266}
DELHI_CENTER = {"lat": 28.6139, "lng": 77.2090}

STATIC_PHARMACIES: list[dict[str, Any]] = [
    {
        "name": "City Care Pharmacy",
        "vicinity": "Sector 14, Gurugram",
        "rating": 4.6,
        "lat": 28.4692,
        "lng": 77.0456,
        "place_id": "static_city_care_gurugram",
        "open_now": True,
    },
    {
        "name": "HealthPlus Pharmacy",
        "vicinity": "DLF Phase 1, Gurugram",
        "rating": 4.5,
        "lat": 28.4729,
        "lng": 77.1020,
        "place_id": "static_healthplus_gurugram",
        "open_now": True,
    },
    {
        "name": "Ayurveda Wellness Medicos",
        "vicinity": "South Extension, New Delhi",
        "rating": 4.4,
        "lat": 28.5689,
        "lng": 77.2206,
        "place_id": "static_ayurveda_wellness_delhi",
        "open_now": True,
    },
    {
        "name": "Green Leaf Pharmacy",
        "vicinity": "Connaught Place, New Delhi",
        "rating": 4.3,
        "lat": 28.6315,
        "lng": 77.2167,
        "place_id": "static_green_leaf_delhi",
        "open_now": False,
    },
    {
        "name": "Rapid Meds",
        "vicinity": "Sushant Lok, Gurugram",
        "rating": 4.2,
        "lat": 28.4638,
        "lng": 77.0847,
        "place_id": "static_rapid_meds_gurugram",
        "open_now": True,
    },
]


def _cache_key(lat: float, lng: float) -> str:
    return f"{round(float(lat), 2)}:{round(float(lng), 2)}"


def _distance_km(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    radius = 6371
    d_lat = math.radians(lat_b - lat_a)
    d_lng = math.radians(lng_b - lng_a)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat_a)) * math.cos(math.radians(lat_b)) * math.sin(d_lng / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _sorted_static_fallback(lat: float, lng: float) -> list[dict[str, Any]]:
    return sorted(
        [dict(item) for item in STATIC_PHARMACIES],
        key=lambda item: _distance_km(float(lat), float(lng), float(item["lat"]), float(item["lng"])),
    )[:5]


def _parse_places_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    pharmacies: list[dict[str, Any]] = []
    for result in payload.get("places", [])[:10]:
        location = result.get("location", {})
        rating = result.get("rating")
        if rating is not None and float(rating) < 3.5:
            continue
        pharmacies.append(
            {
                "name": result.get("displayName", {}).get("text", ""),
                "vicinity": result.get("formattedAddress", ""),
                "rating": rating,
                "lat": location.get("latitude"),
                "lng": location.get("longitude"),
                "place_id": result.get("id"),
                "open_now": result.get("regularOpeningHours", {}).get("openNow"),
            }
        )
    return sorted(pharmacies, key=lambda item: item.get("rating") or 0, reverse=True)


def get_nearby_pharmacies(lat: float, lng: float) -> list[dict[str, Any]]:
    key = _cache_key(lat, lng)
    redis_key = f"nearby_pharmacies:{key}"
    if not settings.is_testing:
        cached_remote = cache_get_json(redis_key)
        if isinstance(cached_remote, list):
            return [dict(item) for item in cached_remote]
    cached = _CACHE.get(key)
    now = time.time()
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return [dict(item) for item in cached[1]]

    api_key = settings.google_maps_api_key
    if not api_key:
        fallback = _sorted_static_fallback(lat, lng)
        _CACHE[key] = (now, fallback)
        cache_set_json(redis_key, fallback, _CACHE_TTL_SECONDS)
        return fallback

    try:
        response = requests.post(
            "https://places.googleapis.com/v1/places:searchNearby",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.regularOpeningHours",
            },
            json={
                "includedTypes": ["pharmacy"],
                "maxResultCount": 10,
                "locationRestriction": {
                    "circle": {
                        "center": {"latitude": float(lat), "longitude": float(lng)},
                        "radius": 3000.0,
                    }
                },
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Google Places API returned an invalid payload")
        pharmacies = _parse_places_payload(payload)
        if not pharmacies:
            pharmacies = _sorted_static_fallback(lat, lng)
        _CACHE[key] = (now, pharmacies)
        cache_set_json(redis_key, pharmacies, _CACHE_TTL_SECONDS)
        return [dict(item) for item in pharmacies]
    except Exception as exc:
        track_error_event("pharmacy_lookup_failure", "/patient/nearby-pharmacies", f"places_new_fallback: {exc}")
        fallback = _sorted_static_fallback(lat, lng)
        _CACHE[key] = (now, fallback)
        cache_set_json(redis_key, fallback, _CACHE_TTL_SECONDS)
        return fallback
