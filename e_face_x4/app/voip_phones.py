"""Persistent e-Face inventory and credentials for generic registered SIP phones."""

from __future__ import annotations

import json
import os
import re
import secrets
from pathlib import Path

_PASSWORD = re.compile(r"[A-Za-z0-9_-]{20,128}\Z")
_EXTENSION = re.compile(r"83[5-9][0-9]\Z")


def _path() -> Path:
    return Path(os.environ.get("EFACE_VOIP_PHONES", "/data/voip_phones.json"))


def validate(records: object) -> dict[str, dict[str, str]]:
    if not isinstance(records, dict) or len(records) > 50:
        raise ValueError("Inventario telefoni VoIP non valido")
    result = {}
    for extension, record in records.items():
        if not isinstance(extension, str) or not _EXTENSION.fullmatch(extension):
            raise ValueError("Interno VoIP non valido")
        if not isinstance(record, dict) or set(record) != {"name", "profile", "password"}:
            raise ValueError("Dati telefono VoIP incompleti")
        name, profile, password = record["name"], record["profile"], record["password"]
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64 or any(not (char.isalnum() or char in " -_") for char in name):
            raise ValueError("Nome telefono VoIP non valido")
        if profile not in ("voip_audio", "voip_video"):
            raise ValueError("Profilo telefono VoIP non valido")
        if not isinstance(password, str) or not _PASSWORD.fullmatch(password):
            raise ValueError("Password telefono VoIP non valida")
        result[extension] = {"name": name.strip(), "profile": profile, "password": password}
    return result


def load() -> dict[str, dict[str, str]]:
    try:
        return validate(json.loads(_path().read_text(encoding="utf-8")))
    except FileNotFoundError:
        return {}


def save(records: object) -> dict[str, dict[str, str]]:
    value = validate(records)
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"voip_phones.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            os.chmod(temporary, 0o600)
            json.dump(value, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return value


def new_record(name: str, profile: str, assigned: dict) -> tuple[str, dict[str, str]]:
    extension = next((str(number) for number in range(8350, 8400) if str(number) not in assigned), None)
    if extension is None:
        raise ValueError("Nessun interno VoIP disponibile")
    record = {"name": name, "profile": profile, "password": secrets.token_urlsafe(36)}
    validate({extension: record})
    return extension, record


def public(records: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    return [{"extension": extension, "name": record["name"], "profile": record["profile"]}
            for extension, record in sorted(records.items())]
