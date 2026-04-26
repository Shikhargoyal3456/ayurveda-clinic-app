from __future__ import annotations

from dataclasses import replace

import pytest

from services.geocoding import get_nearby_pharmacies
from services.medicine_catalog import get_default_medicines


@pytest.mark.asyncio
async def test_medicine_catalog_has_twenty_plus_priced_items(client):
    # GRAND-UNIFIED-1: Patient catalog must have production-useful medicine choices.
    response = await client.get("/patient/medicines")
    assert response.status_code == 200
    medicines = response.json()
    assert len(medicines) >= 20
    assert any(item["name"] == "Ashwagandha" and int(item["price"]) >= 299 for item in medicines)
    assert any(item["name"] == "Triphala" for item in medicines)


def test_default_medicine_catalog_prices_and_categories():
    # GRAND-UNIFIED-1: Seed source keeps prices, categories, and prescription flags.
    catalog = get_default_medicines()
    assert len(catalog) >= 20
    ashwagandha = next(item for item in catalog if item["name"] == "Ashwagandha")
    assert ashwagandha["price"] == 299
    assert ashwagandha["category"] == "wellness"
    assert ashwagandha["otc"] is True


def test_places_fallback_returns_static_pharmacies(monkeypatch):
    # GRAND-UNIFIED-1: Google REQUEST_DENIED/outage still gives checkout-safe pharmacy options.
    from services import geocoding

    geocoding._CACHE.clear()
    monkeypatch.setattr(geocoding, "settings", replace(geocoding.settings, google_maps_api_key=""))
    pharmacies = get_nearby_pharmacies(28.4595, 77.0266)
    assert len(pharmacies) == 5
    assert pharmacies[0]["place_id"].startswith("static_")


@pytest.mark.asyncio
async def test_healthz_includes_monitoring_metrics(client):
    # GRAND-UNIFIED-1: Health endpoint exposes deploy monitoring readiness without secrets.
    response = await client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert "redis_detail" in payload
    assert payload["cloud_run"]["memory"] == "512Mi"
    assert payload["cloud_run"]["concurrency"] == 80
    assert "sentry" in payload
