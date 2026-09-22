from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


CONNECTOR_IDS = ("buspro", "evoice", "etherm", "thermomind", "ksenia", "sunmind")
ACCESS_BEHAVIORS = {
    "auto",
    "native_lock",
    "relay_on_unlock",
    "relay_off_unlock",
    "cover_open_unlock",
    "cover_close_unlock",
}


def _path() -> Path:
    return Path(os.environ.get("EFACE_INSTALLATION_PROFILE", "/data/installation_profile.json"))


def load() -> dict[str, Any]:
    try:
        value = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        value = {}
    return value if isinstance(value, dict) else {}


def _write(value: dict[str, Any]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def connector_overrides() -> dict[str, dict[str, Any]]:
    raw = load().get("connectors")
    if not isinstance(raw, dict):
        return {}
    return {key: value for key, value in raw.items() if key in CONNECTOR_IDS and isinstance(value, dict)}


def save_connector(connector_id: str, payload: Any, current: dict[str, Any]) -> dict[str, Any]:
    if connector_id not in CONNECTOR_IDS or not isinstance(payload, dict):
        raise ValueError("Connettore non valido")
    base_url = str(payload.get("base_url") or "").strip().rstrip("/")
    if base_url and not base_url.lower().startswith(("http://", "https://")):
        raise ValueError("L'indirizzo deve iniziare con http:// o https://")
    auth_mode = str(payload.get("auth_mode") or current.get("auth_mode") or "none").strip().lower()
    if auth_mode not in {"none", "token", "basic"}:
        raise ValueError("Autenticazione non valida")
    value = {
        "enabled": payload.get("enabled") is True,
        "base_url": base_url,
        "auth_mode": auth_mode,
        "username": str(payload.get("username") or "").strip(),
        "installation_id": str(payload.get("installation_id") or "").strip(),
        "token": str(payload.get("token") or current.get("token") or ""),
        "password": str(payload.get("password") or current.get("password") or ""),
    }
    profile = load()
    connectors = profile.get("connectors") if isinstance(profile.get("connectors"), dict) else {}
    connectors[connector_id] = value
    profile["version"] = 1
    profile["connectors"] = connectors
    _write(profile)
    return value


def access_profiles() -> dict[str, dict[str, Any]]:
    raw = load().get("access_devices")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for device_id, value in raw.items():
        if not isinstance(value, dict):
            continue
        behavior = str(value.get("behavior") or "auto")
        if behavior in ACCESS_BEHAVIORS:
            result[str(device_id)] = {
                "enabled": value.get("enabled") is not False,
                "behavior": behavior,
                "name": str(value.get("name") or "").strip()[:80],
                "confirm": value.get("confirm") is True,
                "state_source_id": str(value.get("state_source_id") or "").strip()[:254],
                "unlocked_state": str(value.get("unlocked_state") or "on").strip().casefold()[:40],
            }
    return result


def save_access_profiles(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("Profili accesso non validi")
    values: dict[str, dict[str, Any]] = {}
    for raw in payload["items"]:
        if not isinstance(raw, dict):
            raise ValueError("Profilo accesso non valido")
        device_id = str(raw.get("device_id") or "").strip()
        behavior = str(raw.get("behavior") or "auto").strip()
        if not device_id or len(device_id) > 254 or behavior not in ACCESS_BEHAVIORS:
            raise ValueError("Dispositivo o comportamento non valido")
        if behavior != "auto" or raw.get("enabled") is True or raw.get("name") or raw.get("confirm") is True:
            values[device_id] = {
                "enabled": raw.get("enabled") is True,
                "behavior": behavior,
                "name": str(raw.get("name") or "").strip()[:80],
                "confirm": raw.get("confirm") is True,
                "state_source_id": str(raw.get("state_source_id") or "").strip()[:254],
                "unlocked_state": str(raw.get("unlocked_state") or "on").strip().casefold()[:40] or "on",
            }
    profile = load()
    profile["version"] = 1
    profile["access_devices"] = values
    _write(profile)
    return values


def translate_access_action(profile: dict[str, Any] | None, action: str) -> str:
    behavior = str((profile or {}).get("behavior") or "auto")
    if action not in {"open", "unlock", "lock", "close"} or behavior == "auto":
        return action
    unlocked = action in {"open", "unlock"}
    if behavior == "native_lock":
        return "unlock" if unlocked else "lock"
    if behavior == "relay_on_unlock":
        return "on" if unlocked else "off"
    if behavior == "relay_off_unlock":
        return "off" if unlocked else "on"
    if behavior == "cover_open_unlock":
        return "open" if unlocked else "close"
    if behavior == "cover_close_unlock":
        return "close" if unlocked else "open"
    return action
