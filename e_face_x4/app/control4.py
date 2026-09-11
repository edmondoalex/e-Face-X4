from __future__ import annotations

import ipaddress
import asyncio
import json
import os
from pathlib import Path
from typing import Any

_director_cache: dict[str, Any] = {}


def _path() -> Path:
    return Path(os.environ.get("EFACE_CONTROL4_CONFIG", "/data/control4.json"))


def load_control4_config() -> dict[str, str]:
    try:
        raw = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"host": "192.168.3.10", "username": "", "password": ""}
    return {key: str(raw.get(key) or "") for key in ("host", "username", "password")}


def public_control4_config() -> dict[str, Any]:
    value = load_control4_config()
    return {"host": value["host"], "username": value["username"], "password_configured": bool(value["password"])}


def save_control4_config(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ValueError("Configurazione Control4 non valida")
    host = str(raw.get("host") or "").strip()
    try:
        ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("Indirizzo IP Control4 non valido") from exc
    username = str(raw.get("username") or "").strip()
    password = str(raw.get("password") or "")
    previous = load_control4_config()
    if not password:
        password = previous["password"]
    if not username or not password or len(username) > 254 or len(password) > 512:
        raise ValueError("Email e password Control4 obbligatorie")
    value = {"host": host, "username": username, "password": password}
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    return value


def _find_first(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        if value.get(key):
            return value[key]
        for child in value.values():
            found = _find_first(child, key)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_first(child, key)
            if found:
                return found
    return None


async def test_control4_connection(config: dict[str, str]) -> dict[str, Any]:
    from pyControl4.account import C4Account
    from pyControl4.director import C4Director

    account = C4Account(config["username"], config["password"])
    await account.get_account_bearer_token()
    controllers = await account.get_account_controllers()
    common_name = _find_first(controllers, "controllerCommonName")
    controller_data = controllers.get("controller") if isinstance(controllers, dict) else None
    controller_href = controller_data.get("href") if isinstance(controller_data, dict) else None
    if not common_name:
        raise RuntimeError("Nessun controller associato all'account")
    token_payload = await account.get_director_bearer_token(str(common_name))
    token = token_payload.get("token") if isinstance(token_payload, dict) else None
    if not token:
        raise RuntimeError("Token Director non disponibile")
    director = C4Director(config["host"], str(token))
    ui_configuration, all_items = await asyncio.gather(
        director.get_ui_configuration(), director.get_all_item_info()
    )
    summary = summarize_ui_configuration(ui_configuration, all_items)
    os_version = await account.get_controller_os_version(str(controller_href)) if controller_href else ""
    return {
        "ok": True,
        "controller": str(common_name),
        "os_version": str(os_version),
        **summary,
        "local_host": config["host"],
    }


async def control4_director(config: dict[str, str]) -> tuple[Any, str]:
    """Authenticate and return a local Director client and its ephemeral token."""
    import time
    from pyControl4.account import C4Account
    from pyControl4.director import C4Director

    key = f"{config['host']}\0{config['username']}\0{config['password']}"
    cached = _director_cache.get(key)
    if cached and cached[0] > time.monotonic():
        return C4Director(config["host"], cached[1]), cached[1]
    account = C4Account(config["username"], config["password"])
    await account.get_account_bearer_token()
    info = await account.get_account_controllers()
    common_name = _find_first(info, "controllerCommonName")
    if not common_name:
        raise RuntimeError("Nessun controller Control4 associato")
    payload = await account.get_director_bearer_token(str(common_name))
    token = payload.get("token") if isinstance(payload, dict) else None
    if not token:
        raise RuntimeError("Token Director non disponibile")
    _director_cache.clear()
    _director_cache[key] = (time.monotonic() + 20 * 60 * 60, str(token))
    return C4Director(config["host"], str(token)), str(token)


def summarize_ui_configuration(ui: Any, all_items: Any) -> dict[str, Any]:
    experiences = ui.get("experiences", []) if isinstance(ui, dict) else []
    if isinstance(experiences, dict):
        experiences = experiences.get("experience", [])
    experiences = experiences if isinstance(experiences, list) else []
    room_ids = {str(item.get("room_id")) for item in experiences if isinstance(item, dict) and item.get("room_id") is not None}
    item_names = {
        str(item.get("id")): str(item.get("name"))
        for item in (all_items if isinstance(all_items, list) else [])
        if isinstance(item, dict) and item.get("id") is not None and item.get("name")
    }
    types = sorted({str(item.get("type")) for item in experiences if isinstance(item, dict) and item.get("type")})
    sources = 0
    for item in experiences:
        raw_sources = item.get("sources", {}) if isinstance(item, dict) else {}
        values = raw_sources.get("source", []) if isinstance(raw_sources, dict) else []
        sources += len(values) if isinstance(values, list) else int(bool(values))
    return {
        "rooms": len(room_ids),
        "room_names": [item_names.get(room_id, f"Room {room_id}") for room_id in sorted(room_ids)][:30],
        "experiences": types,
        "sources": sources,
    }
