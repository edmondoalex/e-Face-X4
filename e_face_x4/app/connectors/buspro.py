from __future__ import annotations

from typing import Any

import httpx

from ..config import ProviderConfig
from .base import Connector


def normalize_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    raw_devices = payload.get("devices")
    devices = raw_devices if isinstance(raw_devices, list) else []
    counts = {"lights": 0, "covers": 0, "locks": 0, "sensors": 0}
    rooms: dict[str, int] = {}
    normalized: list[dict[str, Any]] = []
    sensor_types = {"temp", "temperature", "humidity", "illuminance", "pir", "ultrasonic", "dry_contact", "air_quality", "gas_percent"}
    for index, raw in enumerate(devices):
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("type") or raw.get("domain") or "unknown").strip().lower()
        room = str(raw.get("group") or "Senza stanza").strip() or "Senza stanza"
        name = str(raw.get("name") or raw.get("entity_id") or f"Dispositivo {index + 1}").strip()
        if kind in {"light", "switch"}:
            counts["lights"] += 1
        elif kind == "cover":
            counts["covers"] += 1
        elif kind == "lock":
            counts["locks"] += 1
        elif kind in sensor_types:
            counts["sensors"] += 1
        rooms[room] = rooms.get(room, 0) + 1
        normalized.append({"id": str(raw.get("entity_id") or raw.get("id") or index), "name": name, "kind": kind, "room": room})
    mqtt = payload.get("mqtt") if isinstance(payload.get("mqtt"), dict) else {}
    return {
        "devices": normalized,
        "rooms": [{"id": f"room-{i}", "name": name, "devices": total} for i, (name, total) in enumerate(sorted(rooms.items()))],
        "counts": counts,
        "mqtt_connected": bool(mqtt.get("connected")),
    }


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
                normalized = normalize_snapshot(payload)
            return {
                "id": self.id,
                "label": self.label,
                "status": "online",
                "data": payload,
                "normalized": normalized,
                "items": normalized["devices"],
            }
        except (httpx.HTTPError, ValueError) as exc:
            if isinstance(exc, httpx.HTTPStatusError):
                reason = f"HTTP {exc.response.status_code}"
            elif isinstance(exc, httpx.ConnectTimeout):
                reason = "timeout di connessione"
            elif isinstance(exc, httpx.ConnectError):
                reason = "connessione rifiutata o indirizzo non raggiungibile"
            elif isinstance(exc, httpx.TimeoutException):
                reason = "timeout della risposta"
            else:
                reason = "risposta non valida"
            return {
                "id": self.id,
                "label": self.label,
                "status": "offline",
                "error": type(exc).__name__,
                "reason": reason,
                "items": [],
            }
