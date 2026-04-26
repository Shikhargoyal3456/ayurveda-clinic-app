from dataclasses import replace

import pytest


pytestmark = pytest.mark.asyncio


async def test_permissions_policy_allows_same_origin_geolocation(client):
    response = await client.get("/order-medicines")

    assert response.status_code == 200
    assert "geolocation=(self)" in response.headers["Permissions-Policy"]


async def test_nearby_pharmacies_requires_coordinates(client):
    response = await client.get("/patient/nearby-pharmacies")

    assert response.status_code == 400
    assert response.json()["detail"] == "lat and lng are required"


async def test_nearby_pharmacies_returns_filtered_sorted_google_results(client, monkeypatch):
    from services import geocoding

    geocoding._CACHE.clear()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "places": [
                    {
                        "name": "Lower Rated Pharmacy",
                        "displayName": {"text": "Lower Rated Pharmacy"},
                        "formattedAddress": "Old Road",
                        "rating": 3.0,
                        "location": {"latitude": 28.61, "longitude": 77.2},
                        "id": "low-rated",
                        "regularOpeningHours": {"openNow": True},
                    },
                    {
                        "displayName": {"text": "Good Pharmacy"},
                        "formattedAddress": "Main Market",
                        "rating": 4.2,
                        "location": {"latitude": 28.62, "longitude": 77.21},
                        "id": "good",
                        "regularOpeningHours": {"openNow": True},
                    },
                    {
                        "displayName": {"text": "Best Pharmacy"},
                        "formattedAddress": "Clinic Lane",
                        "rating": 4.8,
                        "location": {"latitude": 28.63, "longitude": 77.22},
                        "id": "best",
                        "regularOpeningHours": {"openNow": False},
                    },
                ]
            }

    def fake_post(url, headers, json, timeout):
        assert url == "https://places.googleapis.com/v1/places:searchNearby"
        assert headers["X-Goog-Api-Key"] == "test-google-key"
        assert json["includedTypes"] == ["pharmacy"]
        assert timeout == 10
        return FakeResponse()

    monkeypatch.setattr(geocoding, "settings", replace(geocoding.settings, google_maps_api_key="test-google-key"))
    monkeypatch.setattr("requests.post", fake_post)

    response = await client.get("/patient/nearby-pharmacies?lat=28.6&lng=77.2")

    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "Best Pharmacy",
            "vicinity": "Clinic Lane",
            "rating": 4.8,
            "lat": 28.63,
            "lng": 77.22,
            "place_id": "best",
            "open_now": False,
        },
        {
            "name": "Good Pharmacy",
            "vicinity": "Main Market",
            "rating": 4.2,
            "lat": 28.62,
            "lng": 77.21,
            "place_id": "good",
            "open_now": True,
        },
    ]


async def test_nearby_pharmacies_handles_google_error_status_without_crashing(client, monkeypatch):
    from services import geocoding

    geocoding._CACHE.clear()

    def fake_post(*args, **kwargs):
        raise RuntimeError("REQUEST_DENIED")

    monkeypatch.setattr(geocoding, "settings", replace(geocoding.settings, google_maps_api_key="test-google-key"))
    monkeypatch.setattr("requests.post", fake_post)

    response = await client.get("/patient/nearby-pharmacies?lat=28.6&lng=77.2")

    assert response.status_code == 200
    assert len(response.json()) == 5


async def test_nearby_pharmacies_handles_invalid_google_payload_without_crashing(client, monkeypatch):
    from services import geocoding

    geocoding._CACHE.clear()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return ["unexpected", "payload"]

    monkeypatch.setattr(geocoding, "settings", replace(geocoding.settings, google_maps_api_key="test-google-key"))
    monkeypatch.setattr("requests.post", lambda *args, **kwargs: FakeResponse())

    response = await client.get("/patient/nearby-pharmacies?lat=28.6&lng=77.2")

    assert response.status_code == 200
    assert len(response.json()) == 5
