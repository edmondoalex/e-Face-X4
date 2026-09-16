"""Persistent, provider-neutral audio/video project used by e-Face Composer."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
CAPABILITIES = {"audio", "video", "transport", "volume", "mute", "queue", "presets", "eq", "multiroom", "sources", "power"}
ENDPOINTS = {"audio", "video", "video_audio", "audio_volume", "video_volume", "navigator", "multiroom"}


def _path() -> Path:
    return Path(os.environ.get("EFACE_MEDIA_PROJECT", "/data/media_project.json"))


def _id(prefix: str, value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:42] or "item"
    digest = hashlib.sha256(value.encode()).hexdigest()[:8]
    return f"{prefix}:{slug}:{digest}"


def empty() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "revision": 0, "updated_at": 0, "zones": [], "devices": [], "connections": [], "endpoints": {}, "diagnostics": []}


def load() -> dict[str, Any]:
    try:
        value = json.loads(_path().read_text(encoding="utf-8"))
        return validate(value)
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return empty()


def _text(value: Any, maximum: int = 100) -> str:
    return str(value or "").strip()[:maximum]


def validate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Progetto multimediale non valido")
    zones, zone_ids = [], set()
    for raw in value.get("zones", []):
        if not isinstance(raw, dict): raise ValueError("Ambiente multimediale non valido")
        identity, name = _text(raw.get("id"), 90), _text(raw.get("name"), 80)
        if not identity or not name or identity in zone_ids: raise ValueError("Ambiente duplicato o incompleto")
        zone_ids.add(identity); zones.append({"id": identity, "name": name, "floor": _text(raw.get("floor"), 80), "order": int(raw.get("order") or len(zones)), "origin": _text(raw.get("origin"), 30) or "manual"})
    devices, device_ids = [], set()
    for raw in value.get("devices", []):
        if not isinstance(raw, dict): raise ValueError("Dispositivo multimediale non valido")
        identity, name = _text(raw.get("id"), 120), _text(raw.get("name"), 100)
        if not identity or not name or identity in device_ids: raise ValueError("Dispositivo duplicato o incompleto")
        zone_id = _text(raw.get("zone_id"), 90)
        if zone_id and zone_id not in zone_ids: raise ValueError("Ambiente del dispositivo inesistente")
        capabilities = sorted({_text(item, 30) for item in raw.get("capabilities", []) if _text(item, 30) in CAPABILITIES})
        device_ids.add(identity); devices.append({"id": identity, "name": name, "provider": _text(raw.get("provider"), 30), "native_id": _text(raw.get("native_id"), 120), "kind": _text(raw.get("kind"), 40) or "player", "zone_id": zone_id, "online": raw.get("online") is not False, "capabilities": capabilities, "model": _text(raw.get("model"), 100), "address": _text(raw.get("address"), 100), "managed": raw.get("managed") is not False})
    connections = []
    for raw in value.get("connections", []):
        if not isinstance(raw, dict): raise ValueError("Collegamento multimediale non valido")
        source, target = _text(raw.get("source"), 120), _text(raw.get("target"), 120)
        if source not in device_ids or target not in device_ids or source == target: raise ValueError("Collegamento con dispositivo inesistente")
        connections.append({"id": _text(raw.get("id"), 120) or _id("link", f"{source}>{target}"), "source": source, "target": target, "signal": _text(raw.get("signal"), 30) or "audio", "source_port": _text(raw.get("source_port"), 60), "target_port": _text(raw.get("target_port"), 60), "enabled": raw.get("enabled") is not False})
    device_zones = {item["id"]: item["zone_id"] for item in devices}
    device_capabilities = {item["id"]: set(item["capabilities"]) for item in devices}
    endpoint_capability = {"audio": "audio", "audio_volume": "volume", "video": "video", "video_audio": "audio", "video_volume": "volume", "navigator": "transport", "multiroom": "multiroom"}
    endpoints = {}
    for zone_id, raw in (value.get("endpoints") or {}).items():
        if zone_id not in zone_ids or not isinstance(raw, dict): continue
        endpoints[zone_id] = {kind: device for kind, device in raw.items() if kind in ENDPOINTS and device in device_ids and device_zones.get(device) == zone_id and endpoint_capability[kind] in device_capabilities[device]}
    return {"schema_version": SCHEMA_VERSION, "revision": max(0, int(value.get("revision") or 0)), "updated_at": float(value.get("updated_at") or 0), "zones": zones, "devices": devices, "connections": connections, "endpoints": endpoints, "diagnostics": list(value.get("diagnostics") or [])[:100]}


def save(value: Any) -> dict[str, Any]:
    result = validate(value); current = load()
    result["revision"] = current["revision"] + 1; result["updated_at"] = time.time()
    path = _path(); path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file(): shutil.copy2(path, path.with_suffix(".json.bak"))
    temporary = path.with_suffix(".tmp"); temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"); os.chmod(temporary, 0o600); temporary.replace(path)
    return result


def discovered(control4: dict[str, Any] | None, wiim: dict[str, Any] | None, wiim_config: dict[str, Any] | None) -> dict[str, Any]:
    current = load(); zones = {item["id"]: item for item in current["zones"]}; devices = {item["id"]: item for item in current["devices"]}
    diagnostics = []
    room_zone: dict[str, str] = {}
    if control4:
        for position, item in enumerate(control4.get("items", [])):
            room = _text(item.get("room") or item.get("name") or "Ambiente Control4")
            zone_id = _id("zone", f"control4:{room}"); room_zone[room] = zone_id
            zones.setdefault(zone_id, {"id": zone_id, "name": room, "floor": "", "order": len(zones), "origin": "control4"})
            identity = f"control4:{item.get('registry_id') or position}"
            experiences = set(item.get("experiences") or [])
            caps = {"power", "sources"}
            if "listen" in experiences: caps.update({"audio", "transport", "volume", "mute", "multiroom"})
            if "watch" in experiences: caps.update({"video", "transport", "volume", "mute"})
            previous = devices.get(identity, {})
            devices[identity] = {"id": identity, "name": _text(item.get("name") or room), "provider": "control4", "native_id": _text(item.get("registry_id"), 120), "kind": "room_proxy", "zone_id": previous.get("zone_id") or zone_id, "online": control4.get("status") == "online", "capabilities": sorted(caps), "model": "Control4 Room", "address": "", "managed": True}
        if control4.get("status") != "online": diagnostics.append({"severity": "warning", "code": "control4_offline", "message": "Control4 non raggiungibile: mantenuta la struttura già acquisita."})
    if wiim and wiim_config and wiim_config.get("host"):
        native = _text(wiim.get("id") or wiim.get("uuid") or wiim.get("mac") or wiim_config["host"], 120)
        identity = _id("wiim", native); name = _text(wiim.get("name") or "WiiM")
        zone_id = devices.get(identity, {}).get("zone_id") or _id("zone", f"wiim:{name}")
        zones.setdefault(zone_id, {"id": zone_id, "name": name, "floor": "", "order": len(zones), "origin": "wiim"})
        devices[identity] = {"id": identity, "name": name, "provider": "wiim", "native_id": native, "kind": "network_amplifier" if "amp" in _text(wiim.get("model")).casefold() else "network_player", "zone_id": zone_id, "online": True, "capabilities": ["audio", "eq", "multiroom", "mute", "presets", "queue", "sources", "transport", "volume"], "model": _text(wiim.get("model") or "WiiM"), "address": _text(wiim_config.get("host")), "managed": True}
    elif wiim_config and wiim_config.get("host"):
        diagnostics.append({"severity": "warning", "code": "wiim_offline", "message": f"WiiM {wiim_config['host']} non raggiungibile."})
    result = {**current, "zones": list(zones.values()), "devices": list(devices.values()), "diagnostics": diagnostics}
    # Safe defaults: only assign an endpoint when the room has exactly one capable device.
    endpoints = dict(current["endpoints"])
    for zone in result["zones"]:
        members = [item for item in result["devices"] if item["zone_id"] == zone["id"]]
        audio = [item for item in members if "audio" in item["capabilities"]]
        video = [item for item in members if "video" in item["capabilities"]]
        selected = dict(endpoints.get(zone["id"], {}))
        if len(audio) == 1: selected.setdefault("audio", audio[0]["id"]); selected.setdefault("audio_volume", audio[0]["id"]); selected.setdefault("multiroom", audio[0]["id"])
        if len(video) == 1: selected.setdefault("video", video[0]["id"]); selected.setdefault("video_audio", video[0]["id"]); selected.setdefault("video_volume", video[0]["id"])
        if selected: endpoints[zone["id"]] = selected
    result["endpoints"] = endpoints
    return save(result)
