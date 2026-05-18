from __future__ import annotations

from typing import Any


def get_default_medicines() -> list[dict[str, Any]]:
    """
    Pure AI mode disables static default medicine catalogs.
    Real pharmacy inventory may still populate the product layer from live DB data.
    """
    return []


def seed_default_medicine_catalog() -> dict[str, int]:
    """
    Pure AI mode disables static medicine master seeding.
    """
    return {"seeded": 0, "existing": 0, "mode": "pure_ai"}
