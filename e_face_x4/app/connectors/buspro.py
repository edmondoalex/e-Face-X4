from __future__ import annotations

from typing import Any

import httpx

from ..config import ProviderConfig
from .base import Connector


class BusproConnector(Connector):
    id = "buspro"
    label = "e-HDL BusPro MQTT"

    def __init__(self, config: ProviderConfig, timeout_s: float) -> None:
        self.config = config
        self.timeout_s = timeout_s

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.token}"} if self.config.token else {}

    async def snapshot(self) -> dict[str, Any]:
        if not self.config.enabled:
            return {"id": self.id, "label": self.label, "status": "disabled", "items": []}
        if not self.config.base_url:
            return {"id": self.id, "label": self.label, "status": "misconfigured", "items": []}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=False) as client:
                response = await client.get(
                    f"{self.config.base_url}/api/user/snapshot", headers=self._headers()
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("invalid snapshot shape")
            return {
                "id": self.id,
                "label": self.label,
                "status": "online",
                "data": payload,
                "items": payload.get("devices", []) if isinstance(payload.get("devices"), list) else [],
            }
        except (httpx.HTTPError, ValueError) as exc:
            return {
                "id": self.id,
                "label": self.label,
                "status": "offline",
                "error": type(exc).__name__,
                "items": [],
            }

