from __future__ import annotations

from typing import Any

import requests


class MedicineAPIService:
    """Best-effort external medicine lookup with graceful fallbacks."""

    def __init__(self) -> None:
        self.timeout_seconds = 6

    def search_external_medicines(self, query: str) -> list[dict[str, Any]]:
        clean_query = str(query or "").strip()
        if not clean_query:
            return []
        try:
            response = requests.get(
                "https://api.fda.gov/drug/label.json",
                params={"search": f'openfda.brand_name:"{clean_query}"', "limit": 5},
                timeout=self.timeout_seconds,
            )
            if not response.ok:
                return []
            payload = response.json()
            return self.parse_fda_response(payload)
        except Exception:
            return []

    def import_medicine_by_upc(self, upc_code: str) -> dict[str, Any] | None:
        clean_upc = str(upc_code or "").strip()
        if not clean_upc:
            return None
        try:
            response = requests.get(
                "https://api.fda.gov/drug/label.json",
                params={"search": f'openfda.package_ndc:"{clean_upc}"', "limit": 1},
                timeout=self.timeout_seconds,
            )
            if not response.ok:
                return None
            rows = self.parse_fda_response(response.json())
            return rows[0] if rows else None
        except Exception:
            return None

    def parse_fda_response(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in payload.get("results", []) if isinstance(payload, dict) else []:
            openfda = item.get("openfda", {}) if isinstance(item, dict) else {}
            brand_name = self._first(openfda.get("brand_name"))
            generic_name = self._first(openfda.get("generic_name"))
            manufacturer = self._first(openfda.get("manufacturer_name"))
            product_type = self._first(openfda.get("product_type"))
            barcode = self._first(openfda.get("package_ndc"))
            rows.append(
                {
                    "name": brand_name or generic_name or "Unknown Medicine",
                    "generic_name": generic_name or "",
                    "brand": manufacturer or brand_name or "",
                    "manufacturer": manufacturer or "",
                    "category": "allopathy" if product_type else "wellness",
                    "description": self._first(item.get("description")) or self._first(item.get("indications_and_usage")) or "",
                    "barcode": barcode or "",
                    "source": "openfda",
                }
            )
        return rows

    @staticmethod
    def _first(value: Any) -> str:
        if isinstance(value, list) and value:
            return str(value[0]).strip()
        if isinstance(value, str):
            return value.strip()
        return ""
