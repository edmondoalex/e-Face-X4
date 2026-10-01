from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import httpx

from ..config import ProviderConfig
from ..installation_profile import access_profiles, translate_access_action
from .base import Connector


SMART_HOME_SCHEMA_VERSION = "1.0"
SMART_HOME_CLASS_KIND = {
    "light": "light", "dimmer": "light", "switch": "switch",
    "cover": "cover", "shutter": "cover", "awning": "cover",
    "gate": "cover", "garage_door": "cover", "thermostat": "climate",
    "temperature_sensor": "temperature", "humidity_sensor": "humidity",
    "illuminance_sensor": "sensor", "environment_sensor": "air",
    "presence": "binary_sensor", "dry_contact": "binary_sensor",
    "scenario": "button",
}
SMART_HOME_ACTIONS = {
    "brightness": "level", "set_position": "position", "set_target": "temperature",
    "press": "execute", "run": "execute",
}
PROTECTED_SECURITY_FAMILIES = {
    "alarm", "arm", "bypass", "disarm", "panel", "partition", "security", "zone",
}


def _security_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().casefold()).strip("_")


def _is_protected_security_semantic(value: Any) -> bool:
    token = _security_token(value)
    if not token:
        return False
    parts: set[str] = set()
    for part in token.split("_"):
        if not part:
            continue
        if part.endswith("es") and part[:-2] in PROTECTED_SECURITY_FAMILIES:
            part = part[:-2]
        elif part.endswith("s") and part[:-1] in PROTECTED_SECURITY_FAMILIES:
            part = part[:-1]
        parts.add(part)
    return bool(parts & PROTECTED_SECURITY_FAMILIES)


def _smart_home_snapshot(payload: dict[str, Any]) -> dict[str, Any] | None:
    smart_home = payload.get("smart_home")
    if not isinstance(smart_home, dict) or smart_home.get("schema_version") != SMART_HOME_SCHEMA_VERSION:
        return None
    return smart_home if isinstance(smart_home.get("devices"), list) else None


def _state_value(raw: Any) -> tuple[Any, dict[str, Any]]:
    if not isinstance(raw, dict):
        return raw, {}
    if "value" in raw and len(raw) == 1:
        value = raw.get("value")
        return (value, value if isinstance(value, dict) else {})
    return raw.get("state", raw.get("value", raw)), raw


def _normalize_smart_home(payload: dict[str, Any], smart_home: dict[str, Any]) -> dict[str, Any]:
    legacy = normalize_snapshot({key: value for key, value in payload.items() if key != "smart_home"})
    legacy_by_state = {str(item.get("state_key")): str(item.get("id")) for item in legacy["devices"] if item.get("state_key")}
    counts = {"lights": 0, "switches": 0, "covers": 0, "locks": 0, "sensors": 0}
    rooms: dict[str, dict[str, Any]] = {}
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in smart_home["devices"]:
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("source") or "").strip().lower()
        source_id = str(raw.get("device_id") or "").strip()
        canonical_id = str(raw.get("id") or f"{source}:{source_id}").strip()
        if not source or not source_id or canonical_id != f"{source}:{source_id}" or canonical_id in seen:
            continue
        device_class = str(raw.get("device_class") or "").strip().lower()
        capabilities = [str(value).strip().lower() for value in raw.get("capabilities") or [] if str(value).strip()]
        commands = [dict(value) for value in raw.get("commands") or [] if isinstance(value, dict)]
        allowed_actions = [{"level": "brightness", "position": "set_position", "temperature": "set_target", "execute": "press"}.get(value, value) for value in capabilities]
        command_semantics = [value.get("action", value.get("command", value.get("name", ""))) for value in commands]
        semantic_text = [device_class, raw.get("native_type"), *capabilities, *command_semantics]
        if any(_is_protected_security_semantic(value) for value in semantic_text):
            continue
        kind = SMART_HOME_CLASS_KIND.get(device_class, "switch" if capabilities else "sensor")
        state, state_fields = _state_value(raw.get("state"))
        room = str(raw.get("room_name") or raw.get("floor_name") or "Senza stanza").strip() or "Senza stanza"
        categories = [str(value) for value in raw.get("categories") or [] if isinstance(value, str)]
        features = dict(raw.get("features") or {}) if isinstance(raw.get("features"), dict) else {}
        position = state_fields.get("position")
        brightness = state_fields.get("brightness", state_fields.get("level"))
        if kind == "light": counts["lights"] += 1
        elif kind == "switch": counts["switches"] += 1
        elif kind == "cover": counts["covers"] += 1
        else: counts["sensors"] += 1
        rooms.setdefault(room.casefold(), {"id": str(raw.get("room_id") or f"room-{len(rooms)}"), "name": room, "devices": 0})["devices"] += 1
        legacy_id = legacy_by_state.get(source_id, "") if source == "hdl" else ""
        normalized.append({
            "id": canonical_id, "canonical_id": canonical_id, "source": source, "device_id": source_id,
            "legacy_id": legacy_id, "aliases": [legacy_id] if legacy_id and legacy_id != canonical_id else [],
            "name": str(raw.get("name") or source_id), "kind": kind, "device_class": device_class,
            "native_type": str(raw.get("native_type") or ""), "native_id": str(raw.get("native_id") or ""),
            "room": room, "floor_id": str(raw.get("floor_id") or ""), "floor_name": str(raw.get("floor_name") or ""),
            "room_id": str(raw.get("room_id") or ""), "group_ids": list(raw.get("group_ids") or []),
            "group_names": list(raw.get("group_names") or []), "state": state,
            "brightness": brightness, "position": position,
            "dimmable": "level" in capabilities, "position_supported": "position" in capabilities,
            "capabilities": capabilities, "commands": commands, "features": features,
            "allowed_actions": allowed_actions if not raw.get("read_only") and raw.get("available") and not raw.get("orphaned") else [],
            "read_only": bool(raw.get("read_only")), "available": bool(raw.get("available")),
            "availability": "available" if raw.get("available") else "unavailable",
            "connection_status": "offline" if not raw.get("available") else "online",
            "stale": bool(raw.get("stale")), "orphaned": bool(raw.get("orphaned")),
            "categories": categories, "default_categories": categories,
            "orders": dict(raw.get("orders") or {}), "visible": bool(raw.get("visible", True)),
            "favorite": bool(raw.get("favorite")), "shortcut": bool(raw.get("shortcut")),
            "visual_category": str(raw.get("visual_category") or (categories[0] if categories else "")),
            "icon": str(raw.get("icon") or raw.get("icon_override") or raw.get("icon_auto") or ""),
            "icon_auto": str(raw.get("icon_auto") or ""), "icon_override": str(raw.get("icon_override") or ""),
            "state_key": source_id, "provider": "buspro", "organization_authority": "e-control-hub",
            "home_assistant_entity_id": str(raw.get("home_assistant_entity_id") or ""),
            "home_assistant_entity_ids": [str(value) for value in raw.get("home_assistant_entity_ids") or [] if str(value)],
        })
        seen.add(canonical_id)
    mqtt = payload.get("mqtt") if isinstance(payload.get("mqtt"), dict) else {}
    return {"devices": normalized, "rooms": sorted(rooms.values(), key=lambda item: item["name"].casefold()),
            "counts": counts, "mqtt_connected": bool(mqtt.get("connected")),
            "smart_home_schema_version": smart_home["schema_version"],
            "capability_model_version": str(smart_home.get("capability_model_version") or "")}


def normalize_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    smart_home = _smart_home_snapshot(payload)
    if smart_home is not None:
        return _normalize_smart_home(payload, smart_home)
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
    configured_access = access_profiles()
    for index, raw in enumerate(devices):
        if not isinstance(raw, dict):
            continue
        # e-Control HUB stores BusPro outputs as type=light, but category=Switch belongs to Extra.
        raw_kind = str(raw.get("type") or raw.get("domain") or "light").strip().lower()
        category = str(raw.get("category") or raw.get("page") or "").strip()
        entity_domain = str(raw.get("entity_id") or "").split(".", 1)[0].lower()
        # Keep the configured presentation/group, while retaining the real HA
        # domain below for state and command routing.
        kind = "cover" if raw_kind == "lock" and entity_domain == "cover" else ("switch" if category.casefold() == "switch" else raw_kind)
        transport_kind = kind
        room = str(raw.get("group") or "Senza stanza").strip() or "Senza stanza"
        name = str(raw.get("name") or raw.get("entity_id") or f"Dispositivo {index + 1}").strip()
        device_id = str(raw.get("entity_id") or raw.get("id") or index)
        access_profile = configured_access.get(device_id)
        if access_profile and access_profile.get("enabled"):
            kind = "lock"
            if access_profile.get("name"):
                name = str(access_profile["name"])
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
        address = ".".join(str(raw.get(key)) for key in ("subnet_id", "device_id", "channel") if raw.get(key) is not None)
        state: Any = None
        unit = ""
        position: Any = None
        brightness: Any = None
        battery: Any = raw.get("battery_percent", raw.get("battery_percentage", raw.get("battery_level", raw.get("battery"))))
        entity_id = str(raw.get("entity_id") or "").lower()
        position_supported = kind == "cover" and (bool(raw.get("use_position")) or bool(entity_id) and "_no_" not in entity_id and not raw.get("no_percentage"))
        if entity_id and isinstance(ha_states.get(entity_id), dict):
            ha_state = ha_states[entity_id]
            state = ha_state.get("state")
            attributes = ha_state.get("attributes") if isinstance(ha_state.get("attributes"), dict) else {}
            if kind == "cover" and isinstance(attributes.get("supported_features"), int):
                position_supported = position_supported and bool(attributes["supported_features"] & 4)
            unit = str(attributes.get("unit_of_measurement") or "")
            position = attributes.get("current_position")
            brightness = attributes.get("brightness")
            battery = attributes.get("battery_level", attributes.get("battery_percentage", attributes.get("battery", battery)))
            metrics = ha_state.get("metrics") if isinstance(ha_state.get("metrics"), dict) else {}
            battery = metrics.get("battery_level", battery)
        if state is None:
            source = cover_states if transport_kind == "cover" else light_states
            if transport_kind in sensor_sources:
                source_name, default_unit = sensor_sources[transport_kind]
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
            "unit": unit, "position": position, "position_supported": position_supported, "icon": str(raw.get("icon") or "").strip(),
            "category": category, "entity_domain": entity_domain,
            "state_key": entity_id or address,
            "dimmable": bool(raw.get("dimmable")), "brightness": brightness,
            "battery_percent": battery if kind == "lock" else None,
            "access_behavior": str((access_profile or {}).get("behavior") or "auto"),
            "confirm_action": bool((access_profile or {}).get("confirm")),
            "access_state_source": str((access_profile or {}).get("state_source_id") or ""),
            "state_reliable": True,
            "rgb_group": str(raw.get("rgb_group") or "").strip(),
            "rgb_channel": str(raw.get("rgb_channel") or "").strip().lower(),
        })
    normalized_by_id = {str(item.get("id")): item for item in normalized}
    for item in normalized:
        profile = configured_access.get(str(item.get("id")))
        if not profile or not profile.get("enabled"):
            continue
        source_id = str(profile.get("state_source_id") or "")
        source = normalized_by_id.get(source_id) if source_id else item
        behavior = str(profile.get("behavior") or "auto")
        if source is not None and (source_id or behavior.startswith("relay_")):
            raw_feedback = source.get("state")
            feedback = str(raw_feedback).casefold()
            canonical = "on" if feedback in {"on", "unlocked", "open", "true", "1"} else "off" if feedback in {"off", "locked", "closed", "false", "0"} else feedback
            expected = str(profile.get("unlocked_state") or "on").casefold() if source_id else ("off" if behavior == "relay_off_unlock" else "on")
            item["state"] = "UNLOCKED" if canonical == expected else "LOCKED"
            item["state_reliable"] = True
            item["access_feedback_state"] = raw_feedback
    groups = payload.get("cover_groups") if isinstance(payload.get("cover_groups"), list) else []
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("id") or "").strip()
        members = group.get("members") if isinstance(group.get("members"), list) else []
        if not group_id or not members:
            continue
        member_states = [state_at(cover_states, str(member)) for member in members]
        active = any(isinstance(value, dict) and str(value.get("state") or "").upper() in {"OPEN", "OPENING"}
                     for value in member_states)
        closed = all(isinstance(value, dict) and str(value.get("state") or "").upper() in {"CLOSED", "CLOSE"}
                     for value in member_states)
        positions = [value.get("position") for value in member_states if isinstance(value, dict)
                     and isinstance(value.get("position"), (int, float)) and not isinstance(value.get("position"), bool)]
        group_state = "OPEN" if active else "CLOSED" if closed else "UNKNOWN"
        normalized.append({
            "id": f"cover-group:{group_id}", "group_id": group_id,
            "name": str(group.get("name") or group_id), "kind": "cover", "room": "Gruppi cover",
            "category": "cover_group", "state": group_state,
            "position": round(sum(positions) / len(positions)) if len(positions) == len(members) else None,
            "icon": str(group.get("icon") or "mdi:window-shutter-settings"), "members": members,
            "state_key": f"cover_group:{group_id}",
        })
        normalized.append({
            "id": f"cover-group-no-pct:{group_id}", "group_id": group_id,
            "name": f"{str(group.get('name') or group_id)} · no %", "kind": "cover",
            "room": "Gruppi cover no %", "category": "cover_group_no_pct",
            "state": group_state, "position": None,
            "icon": str(group.get("icon") or "mdi:window-shutter-settings"), "members": members,
            "state_key": f"cover_group:{group_id}",
        })
        counts["covers"] += 2
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
    label = "e-Control HUB"

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
        allowed = {"on", "off", "brightness", "open", "close", "stop", "set_position", "lock", "unlock", "press", "run", "set_target"}
        action = str(action or "").strip().lower()
        action = translate_access_action(access_profiles().get(str(target_id)), action)
        if action not in allowed:
            raise ValueError("azione non consentita")
        brightness_value: int | None = None
        if action == "brightness":
            try:
                brightness_value = max(1, min(255, int(value)))
            except (TypeError, ValueError):
                raise ValueError("luminosità non valida")
        # Commands may take longer than snapshots because e-Control HUB waits for Home
        # Assistant to execute and confirm the requested service call.
        async with httpx.AsyncClient(timeout=max(12.0, self.timeout_s), follow_redirects=False) as client:
            snapshot_response = await client.get(f"{self.config.base_url}/api/user/snapshot", headers=self._headers())
            snapshot_response.raise_for_status()
            snapshot = snapshot_response.json()
            smart_home = _smart_home_snapshot(snapshot) if isinstance(snapshot, dict) else None
            if smart_home is not None:
                target = next((item for item in smart_home["devices"] if isinstance(item, dict) and str(item.get("id")) == str(target_id)), None)
                if target is not None:
                    source = str(target.get("source") or "").strip().lower()
                    source_id = str(target.get("device_id") or "").strip()
                    hub_action = SMART_HOME_ACTIONS.get(action, action)
                    if action == "brightness":
                        hub_value = round((brightness_value or 0) * 100 / 255)
                    else:
                        hub_value = value
                    response = await client.post(
                        f"{self.config.base_url}/api/user/smart-home/{quote(source, safe='')}/{quote(source_id, safe='')}/command",
                        headers=self._headers(), json={"action": hub_action, "value": hub_value},
                    )
                    response.raise_for_status()
                    result = response.json()
                    if not isinstance(result, dict):
                        raise ValueError("risposta comando Smart Home non valida")
                    return result
            devices = snapshot.get("devices") if isinstance(snapshot, dict) else None
            if not isinstance(devices, list):
                raise ValueError("snapshot non valido")
            if str(target_id).startswith(("cover-group:", "cover-group-no-pct:")):
                group_id = str(target_id).split(":", 1)[1]
                groups = snapshot.get("cover_groups") if isinstance(snapshot.get("cover_groups"), list) else []
                if not any(isinstance(group, dict) and str(group.get("id")) == group_id for group in groups):
                    raise ValueError("gruppo cover non trovato")
                if action not in {"open", "close", "stop"}:
                    raise ValueError("comando gruppo cover non valido")
                response = await client.post(
                    f"{self.config.base_url}/api/control/cover_group/{group_id}",
                    headers=self._headers(), json={"command": action.upper()},
                )
                response.raise_for_status()
                return {"ok": True}
            raw = next((item for index, item in enumerate(devices) if isinstance(item, dict) and str(item.get("entity_id") or item.get("id") or index) == str(target_id)), None)
            if raw is None:
                raise ValueError("dispositivo non trovato")
            kind = str(raw.get("type") or raw.get("domain") or "light").strip().lower()
            entity_id = str(raw.get("entity_id") or "").strip().lower()
            if entity_id:
                domain = entity_id.split(".", 1)[0]
                if domain == "switch" and kind == "lock" and action in {"lock", "unlock", "open"}:
                    # Keep the access card presentation, but address the original
                    # e-Control switch only: open/unlock=ON, close/lock=OFF.
                    path, body = f"/api/control/ha/switch/{entity_id}", {"state": "OFF" if action == "lock" else "ON"}
                elif domain in {"light", "switch"} and action in {"on", "off", "brightness"}:
                    body = {"state": "ON" if action == "brightness" else action.upper()}
                    if action == "brightness" and domain == "light":
                        body["brightness"] = brightness_value
                    path = f"/api/control/ha/{domain}/{entity_id}"
                elif domain == "cover" and action in {"open", "close", "stop", "set_position"}:
                    path, body = f"/api/control/ha/cover/{entity_id}", {"command": action.upper()}
                    if action == "set_position":
                        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
                            raise ValueError("posizione cover non valida")
                        body["position"] = round(value)
                elif domain == "cover" and kind == "lock" and action in {"lock", "unlock"}:
                    # Garage doors can be presented as security locks while their
                    # e-Control entity still belongs to the cover domain.
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
                elif kind == "cover" and action in {"open", "close", "stop", "set_position"}:
                    if action == "set_position":
                        if not raw.get("use_position"):
                            raise ValueError("posizionamento non disponibile per questa cover")
                        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
                            raise ValueError("posizione cover non valida")
                    path, body = f"/api/control/cover/{address}", {"command": action.upper()}
                    if action == "set_position":
                        body["position"] = round(value)
                else:
                    raise ValueError("comando non disponibile per questo dispositivo")
            response = await client.post(f"{self.config.base_url}{path}", headers=self._headers(), json=body)
            response.raise_for_status()
            return {"ok": True}
