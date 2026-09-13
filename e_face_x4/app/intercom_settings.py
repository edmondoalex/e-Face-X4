from __future__ import annotations

import ipaddress
import json
import os
import re
import secrets
from pathlib import Path

DEFAULTS = {"asterisk_host": "192.168.3.24", "asterisk_port": 8088, "doorbird_host": "192.168.2.30", "doorbird_port": 80, "ring_extension": "8290"}
TURN_DEFAULTS = {"turn_url": "", "turn_username": "", "turn_password": ""}
PRIVATE_NETWORKS = tuple(ipaddress.ip_network(network) for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


def _path() -> Path:
    return Path(os.environ.get("EFACE_INTERCOM_SETTINGS", "/data/intercom.json"))


def _turn_path() -> Path:
    return Path(os.environ.get("EFACE_INTERCOM_TURN_SETTINGS", "/data/intercom_turn.json"))


def load_turn() -> dict:
    try:
        stored = json.loads(_turn_path().read_text(encoding="utf-8"))
        return {key: str(stored.get(key) or "") for key in TURN_DEFAULTS} if isinstance(stored, dict) else TURN_DEFAULTS.copy()
    except (OSError, json.JSONDecodeError):
        return TURN_DEFAULTS.copy()


def save_turn(payload: dict) -> dict:
    if set(payload) != set(TURN_DEFAULTS):
        raise ValueError("Configurazione TURN incompleta")
    url = str(payload["turn_url"]).strip()
    if url and not re.fullmatch(r"turns?:[A-Za-z0-9.-]+(?::[0-9]{1,5})?(?:\?transport=(?:udp|tcp))?", url):
        raise ValueError("Indirizzo TURN non valido")
    username = str(payload["turn_username"]).strip()
    password = str(payload["turn_password"])
    if url and (not username or not password):
        raise ValueError("Utente e password TURN richiesti")
    value = {"turn_url": url, "turn_username": username if url else "", "turn_password": password if url else ""}
    path = _turn_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"intercom_turn.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            os.chmod(temporary, 0o600)
            json.dump(value, file)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return value


def load() -> dict:
    try:
        stored = json.loads(_path().read_text(encoding="utf-8"))
        return {**DEFAULTS, **stored} if isinstance(stored, dict) else DEFAULTS.copy()
    except (OSError, json.JSONDecodeError):
        return DEFAULTS.copy()


def save(payload: dict) -> dict:
    if set(payload) != set(DEFAULTS):
        raise ValueError("Configurazione incompleta")
    value = {}
    for field in ("asterisk_host", "doorbird_host"):
        host = str(payload[field]).strip()
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError(f"{field}: usa un indirizzo IP locale") from exc
        if address.version != 4 or not any(address in network for network in PRIVATE_NETWORKS):
            raise ValueError(f"{field}: usa un indirizzo IPv4 privato")
        value[field] = host
    for field in ("asterisk_port", "doorbird_port"):
        port = payload[field]
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError(f"{field}: porta non valida")
        value[field] = port
    extension = str(payload["ring_extension"]).strip()
    if not re.fullmatch(r"[0-9]{2,6}", extension):
        raise ValueError("Interno di chiamata non valido")
    value["ring_extension"] = extension
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"intercom.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            os.chmod(temporary, 0o600)
            json.dump(value, file)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return value
