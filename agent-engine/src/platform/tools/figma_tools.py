"""
Figma integration tools.

Provides a real FigmaClient (Figma REST API) and a MockFigmaClient
that returns canned data.  Use ``get_figma_client()`` as the factory.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.parse
from typing import Any, Dict, List

from ..config import settings


class FigmaClient:
    """Thin Figma REST API client."""

    API_BASE = "https://api.figma.com/v1"

    def __init__(self, token: str) -> None:
        self._headers = {
            "X-Figma-Token": token,
            "Content-Type": "application/json",
        }

    def _request(self, path: str) -> Any:
        url = f"{self.API_BASE}/{path.lstrip('/')}"
        req = urllib.request.Request(url, headers=self._headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def get_file_metadata(self, file_key: str) -> Dict[str, Any]:
        """Return metadata for a Figma file."""
        data = self._request(f"files/{file_key}?depth=1")
        return {
            "file_key": file_key,
            "name": data["name"],
            "last_modified": data["lastModified"],
            "thumbnail_url": data.get("thumbnailUrl", ""),
            "version": data["version"],
        }

    def list_components(self, file_key: str) -> List[Dict[str, Any]]:
        """Return a flat list of published components in a Figma file."""
        data = self._request(f"files/{file_key}/components")
        return [
            {
                "node_id": c["node_id"],
                "name": c["name"],
                "description": c.get("description", ""),
                "containing_frame": c.get("containing_frame", {}).get("name", ""),
            }
            for c in data.get("meta", {}).get("components", [])
        ]

    def get_images(self, file_key: str, node_ids: List[str], scale: float = 2.0) -> Dict[str, str]:
        """Export node images as PNG URLs."""
        ids = urllib.parse.quote(",".join(node_ids))
        data = self._request(f"images/{file_key}?ids={ids}&scale={scale}&format=png")
        return data.get("images", {})


class MockFigmaClient:
    """Returns realistic canned Figma data without API calls."""

    def get_file_metadata(self, file_key: str) -> Dict[str, Any]:
        return {
            "file_key": file_key,
            "name": "SelfCare — Product Catalog UI",
            "last_modified": "2025-09-15T12:00:00Z",
            "thumbnail_url": f"https://figma-thumbnail.example.com/{file_key}.png",
            "version": "42",
        }

    def list_components(self, file_key: str) -> List[Dict[str, Any]]:
        return [
            {
                "node_id": "1:100",
                "name": "ProductCard",
                "description": "Card displaying product image, name, price and CTA",
                "containing_frame": "Product Listing",
            },
            {
                "node_id": "1:101",
                "name": "FilterSidebar",
                "description": "Left-hand filter panel with category / price facets",
                "containing_frame": "Product Listing",
            },
            {
                "node_id": "1:102",
                "name": "ProductDetailHero",
                "description": "Large hero section on the PDP with images carousel",
                "containing_frame": "Product Detail",
            },
            {
                "node_id": "1:103",
                "name": "CartDrawer",
                "description": "Slide-out cart drawer with line items and checkout CTA",
                "containing_frame": "Cart",
            },
        ]

    def get_images(self, file_key: str, node_ids: List[str], scale: float = 2.0) -> Dict[str, str]:
        return {node_id: f"https://figma-export.example.com/{file_key}/{node_id}.png" for node_id in node_ids}


def get_figma_client() -> FigmaClient | MockFigmaClient:
    """Factory — returns mock or real client based on MOCK_MODE."""
    if settings.mock_mode:
        return MockFigmaClient()
    return FigmaClient(token=settings.figma_token)
