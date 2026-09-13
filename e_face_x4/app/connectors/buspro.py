from __future__ import annotations

from typing import Any

import httpx

from ..config import ProviderConfig
from .base import Connector


def normalize_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    raw_devices = payload.get("devices")
    devices = raw_devices if isinstance(raw_devices, list) else []
    counts = {"lights": 0, "switches": 0, "covers": 0, "locks": 0, "sensors": 0}
    rooms: dict[str, dict[str, Any]] = {}
    normalized: list[dict[str, Any]] = []
    light_states = payload.get("states") if isinstance(payload.get("states"), dict) else {}
    cover_states = payload.get("cover_states") if isinstance(payload.get("cover_states"), dict) else {}
    ha_states = payload.get("ha_states") if isinstance(payload.get("ha_states"), dict) else {}
    sensor_types = {"temp", "temperature", "humidity", "illuminance", "pir", "ultrasonic", "dry_contact", "air", "air_quality", "gas_percent"}
    sensor_sources = {
        "temp": ("temp_states", "°C"),
        "temperature": ("temp_states", "°C"),
        "humidity": ("humidity_states", "%"),
        "illuminance": ("illuminance_states", "lx"),
        "air": ("air_quality_states", ""),
        "air_quality": ("air_quality_states", ""),
        "gas_percent": ("gas_percent_states", "%"),
        "dry_contact": ("dry_contact_states", ""),
        "pir": ("pir_states", ""),
        "ultrasonic": ("ultrasonic_states", ""),
    }

    def state_at(source: dict[str, Any], address: str) -> Any:
        for key in (address, address.lower(), address.upper()):
            if key in source:
                return source[key]
        return None
    for index, raw in enumerate(devices):
        if not isinstance(raw, dict):
            continue
        # e-HDL stores BusPro outputs as type=light, but category=Switch belongs to Extra.
        raw_kind = str(raw.get("type") or raw.get("domain") or "light").strip().lower()
        category = str(raw.get("category") or raw.get("page") or "").strip()
        entity_domain = str(raw.get("entity_id") or "").split(".", 1)[0].lower()
        kind = "cover" if raw_kind == "lock" and entity_domain == "cover" else ("switch" if category.casefold() == "switch" else raw_kind)
        room = str(raw.get("group") or "Senza stanza").strip() or "Senza stanza"
        name = str(raw.get("name") or raw.get("entity_id") or f"Dispositivo {index + 1}").strip()
        if kind == "light":
            counts["lights"] += 1
        elif kind == "switch":
            counts["switches"] += 1
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
        address = ".".join(str(raw.get(key)) for key in ("subnet_id", "device_id", "channel") if raw.get(key) is not None)
        state: Any = None
        unit = ""
        position: Any = None
        brightness: Any = None
        battery: Any = raw.get("battery_percent", raw.get("battery_percentage", raw.get("battery_level", raw.get("battery"))))
        entity_id = str(raw.get("entity_id") or "").lower()
        if entity_id and isinstance(ha_states.get(entity_id), dict):
            ha_state = ha_states[entity_id]
            state = ha_state.get("state")
            attributes = ha_state.get("attributes") if isinstance(ha_state.get("attributes"), dict) else {}
            unit = str(attributes.get("unit_of_measurement") or "")
            position = attributes.get("current_position")
            brightness = attributes.get("brightness")
            battery = attributes.get("battery_level", attributes.get("battery_percentage", attributes.get("battery", battery)))
            metrics = ha_state.get("metrics") if isinstance(ha_state.get("metrics"), dict) else {}
            battery = metrics.get("battery_level", battery)
        if state is None:
            source = cover_states if kind == "cover" else light_states
            if kind in sensor_sources:
                source_name, default_unit = sensor_sources[kind]
                candidate = payload.get(source_name)
                source = candidate if isinstance(candidate, dict) else {}
                unit = default_unit
            raw_state = state_at(source, address) if address else None
            if isinstance(raw_state, dict):
                state = raw_state.get("value") if raw_state.get("value") is not None else raw_state.get("state")
                position = raw_state.get("position")
                brightness = raw_state.get("brightness")
                battery = raw_state.get("battery_level", raw_state.get("battery_percent", raw_state.get("battery", battery)))
            else:
                state = raw_state
        normalized.append({
            "id": device_id, "name": name, "kind": kind, "room": room_entry["name"], "state": state,
            "unit": unit, "position": position, "icon": str(raw.get("icon") or "").strip(),
            "category": category,
            "state_key": entity_id or address,
            "dimmable": bool(raw.get("dimmable")), "brightness": brightness,
            "battery_percent": battery if kind == "lock" else None,
            "rgb_group": str(raw.get("rgb_group") or "").strip(),
            "rgb_channel": str(raw.get("rgb_channel") or "").strip().lower(),
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

    async def command(self, target_id: str, action: str, value: Any = None) -> dict[str, Any]:
        allowed = {"on", "off", "brightness", "open", "close", "stop", "lock", "unlock"}
        action = str(action or "").strip().lower()
        if action not in allowed:
            raise ValueError("azione non consentita")
        brightness_value: int | None = None
        if action == "brightness":
            try:
                brightness_value = max(1, min(255, int(value)))
            except (TypeError, ValueError):
                raise ValueError("luminosità non valida")
        async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=False) as client:
            snapshot_response = await client.get(f"{self.config.base_url}/api/user/snapshot", headers=self._headers())
            snapshot_response.raise_for_status()
            snapshot = snapshot_response.json()
            devices = snapshot.get("devices") if isinstance(snapshot, dict) else None
            if not isinstance(devices, list):
                raise ValueError("snapshot non valido")
            raw = next((item for index, item in enumerate(devices) if isinstance(item, dict) and str(item.get("entity_id") or item.get("id") or index) == str(target_id)), None)
            if raw is None:
                raise ValueError("dispositivo non trovato")
            kind = str(raw.get("type") or raw.get("domain") or "light").strip().lower()
            entity_id = str(raw.get("entity_id") or "").strip().lower()
            if entity_id:
                domain = entity_id.split(".", 1)[0]
                if domain in {"light", "switch"} and action in {"on", "off", "brightness"}:
                    body = {"state": "ON" if action == "brightness" else action.upper()}
                    if action == "brightness" and domain == "light":
                        body["brightness"] = brightness_value
                    path = f"/api/control/ha/{domain}/{entity_id}"
                elif domain == "cover" and action in {"open", "close", "stop"}:
                    path, body = f"/api/control/ha/cover/{entity_id}", {"command": action.upper()}
                elif domain == "cover" and kind == "lock" and action in {"lock", "unlock"}:
                    # Garage doors can be presented as security locks while their
                    # Home Assistant entity still belongs to the cover domain.
                    command = "CLOSE" if action == "lock" else "OPEN"
                    path, body = f"/api/control/ha/cover/{entity_id}", {"command": command}
                elif kind == "lock" and action in {"lock", "unlock", "open"}:
                    path, body = f"/api/control/ha/lock/{entity_id}", {"command": action.upper()}
                else:
                    raise ValueError("comando non compatibile con il dispositivo")
            else:
                try:
                    address = "/".join(str(int(raw[key])) for key in ("subnet_id", "device_id", "channel"))
                except (KeyError, TypeError, ValueError):
                    raise ValueError("indirizzo dispositivo non valido")
                if kind in {"light", "switch"} and action in {"on", "off", "brightness"}:
                    body = {"state": "ON" if action == "brightness" else action.upper()}
                    if action == "brightness":
                        body["brightness"] = brightness_value
                    path = f"/api/control/light/{address}"
                elif kind == "cover" and action in {"open", "close", "stop"}:
                    path, body = f"/api/control/cover/{address}", {"command": action.upper()}
                else:
                    raise ValueError("comando non disponibile per questo dispositivo")
            response = await client.post(f"{self.config.base_url}{path}", headers=self._headers(), json=body)
            response.raise_for_status()
            return {"ok": True}
