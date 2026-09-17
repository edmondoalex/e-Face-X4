from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_SERVICES = ["Netflix", "Prime Video", "Disney+", "YouTube", "Spotify", "Apple TV+"]


def _path() -> Path:
    return Path(os.environ.get("EFACE_SKYQ_CONFIG", "/data/skyq.json"))


def load() -> dict[str, Any]:
    defaults = {
        "enabled": False, "host": "", "name": "Sky Q", "control4_room_id": 0,
        "control4_source_id": 0, "command_provider": "native", "services": DEFAULT_SERVICES, "app_order": [],
    }
    try:
        value = json.loads(_path().read_text(encoding="utf-8"))
        return {**defaults, **value} if isinstance(value, dict) else defaults
    except (OSError, ValueError):
        return defaults


def save(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Configurazione Sky Q non valida")
    host = str(raw.get("host") or "").strip()
    enabled = bool(raw.get("enabled"))
    if enabled:
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError("Inserisci un indirizzo IP Sky Q valido") from exc
        if address.version != 4 or not address.is_private:
            raise ValueError("Sky Q deve avere un indirizzo IPv4 privato della LAN")
    services = raw.get("services", [])
    if not isinstance(services, list):
        raise ValueError("Servizi Sky Q non validi")
    selected_services = []
    seen_services = set()
    for item in services[:64]:
        title = str(item or "").strip()[:100]
        key = title.casefold()
        if title and key not in seen_services:
            selected_services.append(title)
            seen_services.add(key)
    app_order = []
    seen_order = set()
    for item in raw.get("app_order", [])[:64] if isinstance(raw.get("app_order", []), list) else []:
        title = str(item or "").strip()[:100]
        key = title.casefold()
        if title and key not in seen_order:
            app_order.append(title)
            seen_order.add(key)
    value = {
        "enabled": enabled,
        "host": host,
        "name": str(raw.get("name") or "Sky Q").strip()[:80] or "Sky Q",
        "control4_room_id": max(0, int(raw.get("control4_room_id") or 0)),
        "control4_source_id": max(0, int(raw.get("control4_source_id") or 0)),
        "command_provider": "native",
        "services": selected_services,
        "app_order": app_order,
    }
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    return value
