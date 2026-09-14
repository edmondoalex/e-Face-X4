"""Persistent external Intercom stations; no SIP secrets are sent to browsers."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import secrets
from pathlib import Path

from . import intercom_settings


def _path() -> Path:
    return Path(os.environ.get("EFACE_EXTERNAL_STATIONS", "/data/external_stations.json"))


def _default() -> list[dict]:
    current = intercom_settings.load()
    return [{"id": "ingresso", "name": "Ingresso · DoorBird", "host": current["doorbird_host"],
             "http_port": current["doorbird_port"], "sip_extension": "8201", "ready": True,
             "username": "", "password": ""}]


def load() -> list[dict]:
    try:
        value = json.loads(_path().read_text(encoding="utf-8"))
        if isinstance(value, list) and value:
            legacy = intercom_settings.load()
            if value[0].get("id") == "ingresso":
                value[0]["host"] = legacy["doorbird_host"]
                value[0]["http_port"] = legacy["doorbird_port"]
            return value
    except (OSError, json.JSONDecodeError):
        pass
    return _default()


def public() -> list[dict]:
    return [{key: station[key] for key in ("id", "name", "sip_extension", "ready")}
            for station in load()]


def admin_public() -> list[dict]:
    return [{**{key: station[key] for key in ("id", "name", "host", "http_port", "sip_extension", "ready")},
             "username": station.get("username", ""),
             "credential_configured": bool(station.get("username") and station.get("password")) or station["id"] == "ingresso"}
            for station in load()]


def get(station_id: str) -> dict | None:
    return next((station for station in load() if station["id"] == station_id), None)


def validate(payload: list[dict]) -> list[dict]:
    if not isinstance(payload, list) or not 1 <= len(payload) <= 8:
        raise ValueError("Da 1 a 8 postazioni esterne richieste")
    previous = {station["id"]: station for station in load()}
    result = []
    ids: set[str] = set()
    extensions: set[str] = set()
    for index, item in enumerate(payload):
        if not isinstance(item, dict) or set(item) != {"id", "name", "host", "http_port", "sip_extension", "ready", "username", "password"}:
            raise ValueError("Dati postazione incompleti")
        station_id = str(item["id"]).strip()
        name = str(item["name"]).strip()
        host = str(item["host"]).strip()
        extension = str(item["sip_extension"]).strip()
        if not re.fullmatch(r"[a-z0-9-]{1,32}", station_id) or station_id in ids:
            raise ValueError("Identificativo postazione non valido o duplicato")
        if index == 0 and station_id != "ingresso":
            raise ValueError("La postazione Ingresso non può essere rimossa")
        if not 1 <= len(name) <= 70:
            raise ValueError("Nome postazione non valido")
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError("IP postazione non valido") from exc
        if address.version != 4 or not any(address in network for network in intercom_settings.PRIVATE_NETWORKS):
            raise ValueError("Usa un IP IPv4 privato")
        port = item["http_port"]
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("Porta HTTP non valida")
        if not (re.fullmatch(r"82(?:0[2-9]|[1-8][0-9])", extension) or (index == 0 and extension == "8201")) or extension in extensions:
            raise ValueError("Interno SIP 82xx non valido o duplicato")
        if index == 0 and (extension != "8201" or host != intercom_settings.load()["doorbird_host"]):
            raise ValueError("Ingresso usa la rotta SIP 8201 e l'IP DoorBird delle impostazioni esistenti")
        ready = item["ready"]
        if not isinstance(ready, bool):
            raise ValueError("Stato SIP non valido")
        username = str(item["username"]).strip()
        password = str(item["password"])
        old = previous.get(station_id, {})
        if not password and old.get("username") == username:
            password = old.get("password", "")
        if (username or password) and (not username or not password or len(username) > 254 or len(password) > 512):
            raise ValueError("Credenziale postazione incompleta")
        if index > 0 and ready and not (username and password):
            raise ValueError("Prima di attivare una nuova postazione, salva la sua credenziale")
        result.append({"id": station_id, "name": name, "host": host, "http_port": port,
                       "sip_extension": extension, "ready": ready,
                       "username": username, "password": password})
        ids.add(station_id)
        extensions.add(extension)
    return result


def save(payload: list[dict]) -> list[dict]:
    result = validate(payload)
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"external_stations.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            os.chmod(temporary, 0o600)
            json.dump(result, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return result
