from __future__ import annotations

from typing import Any

import httpx

from ..config import ProviderConfig
from .base import Connector


def normalize_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    raw_devices = payload.get("devices")
    devices = raw_devices if isinstance(raw_devices, list) else []
    counts = {"lights": 0, "covers": 0, "locks": 0, "sensors": 0}
    rooms: dict[str, dict[str, Any]] = {}
    normalized: list[dict[str, Any]] = []
    light_states = payload.get("states") if isinstance(payload.get("states"), dict) else {}
    cover_states = payload.get("cover_states") if isinstance(payload.get("cover_states"), dict) else {}
    ha_states = payload.get("ha_states") if isinstance(payload.get("ha_states"), dict) else {}
    sensor_types = {"temp", "temperature", "humidity", "illuminance", "pir", "ultrasonic", "dry_contact", "air_quality", "gas_percent"}
    sensor_sources = {
        "temp": ("temp_states", "°C"),
        "temperature": ("temp_states", "°C"),
        "humidity": ("humidity_states", "%"),
        "illuminance": ("illuminance_states", "lx"),
        "air_quality": ("air_quality_states", ""),
        "gas_percent": ("gas_percent_states", "%"),
        "dry_contact": ("dry_contact_states", ""),
        "pir": ("pir_states", ""),
        "ultrasonic": ("ultrasonic_states", ""),
    }
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
        room_key = room.casefold()
        room_entry = rooms.setdefault(room_key, {"name": room, "devices": 0})
        room_entry["devices"] += 1
        device_id = str(raw.get("entity_id") or raw.get("id") or index)
        state: Any = None
        unit = ""
        entity_id = str(raw.get("entity_id") or "").lower()
        if entity_id and isinstance(ha_states.get(entity_id), dict):
            ha_state = ha_states[entity_id]
            state = ha_state.get("state")
            attributes = ha_state.get("attributes") if isinstance(ha_state.get("attributes"), dict) else {}
            unit = str(attributes.get("unit_of_measurement") or "")
        if state is None:
            address = ".".join(str(raw.get(key)) for key in ("subnet_id", "device_id", "channel") if raw.get(key) is not None)
            source = cover_states if kind == "cover" else light_states
            if kind in sensor_sources:
                source_name, default_unit = sensor_sources[kind]
                candidate = payload.get(source_name)
                source = candidate if isinstance(candidate, dict) else {}
                unit = default_unit
            raw_state = source.get(address) if address else None
            if isinstance(raw_state, dict):
                state = raw_state.get("value") if raw_state.get("value") is not None else raw_state.get("state")
            else:
                state = raw_state
        normalized.append({
            "id": device_id, "name": name, "kind": kind, "room": room_entry["name"], "state": state,
            "unit": unit, "icon": str(raw.get("icon") or "").strip(),
        })
    mqtt = payload.get("mqtt") if isinstance(payload.get("mqtt"), dict) else {}
    return {
        "devices": normalized,
        "rooms": [
            {"id": f"room-{i}", "name": entry["name"], "devices": entry["devices"]}
            for i, (_, entry) in enumerate(sorted(rooms.items()))
        ],
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
