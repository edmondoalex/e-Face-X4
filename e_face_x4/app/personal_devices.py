"""One persistent SIP identity per authenticated e-Face browser installation."""

from __future__ import annotations

import json
import os
import re
import secrets
import uuid
from pathlib import Path
from typing import Any

_EXTENSION = re.compile(r"83(?:0[2-9]|[1-4][0-9])\Z")
_PASSWORD = re.compile(r"[A-Za-z0-9_-]{20,128}\Z")
_OWNER = re.compile(r"[a-z][a-z0-9_-]{2,31}\Z")
_DEVICE_TYPES = {"phone", "tablet", "desktop"}
_RINGTONES = {"doorbell", "dingdong", "double", "bell", "soft", "classic"}
_CAMERA_FACING = {"user", "environment"}


def preferences(record: dict) -> dict[str, Any]:
    ringtone = record.get("ringtone", "doorbell")
    volume = record.get("ring_volume", 80)
    vibration = record.get("vibration", True)
    silent = record.get("silent", False)
    dnd = record.get("dnd", False)
    video_capable = record.get("video_capable", False)
    video_enabled = record.get("video_enabled", video_capable)
    camera_facing = record.get("camera_facing", "user")
    if ringtone not in _RINGTONES or not isinstance(volume, int) or isinstance(volume, bool) or not 0 <= volume <= 100:
        raise ValueError("Impostazioni suoneria non valide")
    if not all(isinstance(value, bool) for value in (vibration, silent, dnd, video_capable, video_enabled)) or camera_facing not in _CAMERA_FACING:
        raise ValueError("Impostazioni suoneria non valide")
    return {"ringtone": ringtone, "ring_volume": volume, "vibration": vibration, "silent": silent, "dnd": dnd,
            "video_capable": video_capable, "video_enabled": video_enabled, "camera_facing": camera_facing}


def device_type(value: object, name: str = "") -> str:
    if value in _DEVICE_TYPES:
        return str(value)
    lowered = name.lower()
    if any(word in lowered for word in ("cellulare", "telefono", "phone", "iphone", "android", "redmi", "poco")):
        return "phone"
    if any(word in lowered for word in ("tablet", "ipad", "inwall")):
        return "tablet"
    return "desktop"


def _path() -> Path:
    return Path(os.environ.get("EFACE_PERSONAL_DEVICES", "/data/personal_devices.json"))


def _revoked_path() -> Path:
    return _path().with_name("personal_device_revocations.json")


def validate_id(device_id: object) -> str:
    if not isinstance(device_id, str):
        raise ValueError("Identificativo dispositivo non valido")
    try:
        normalized = str(uuid.UUID(device_id))
    except ValueError as exc:
        raise ValueError("Identificativo dispositivo non valido") from exc
    if normalized != device_id:
        raise ValueError("Identificativo dispositivo non valido")
    return device_id


def validate(records: object) -> dict[str, dict[str, Any]]:
    if not isinstance(records, dict) or len(records) > 48:
        raise ValueError("Inventario dispositivi personali non valido")
    result = {}
    extensions: set[str] = set()
    owners: dict[str, int] = {}
    for device_id, record in records.items():
        validate_id(device_id)
        required = {"owner", "name", "extension", "password"}
        optional = {"device_type", "ringtone", "ring_volume", "vibration", "silent", "dnd", "video_capable", "video_enabled", "camera_facing"}
        if not isinstance(record, dict) or not required.issubset(record) or set(record) - required - optional:
            raise ValueError("Dati dispositivo personale incompleti")
        owner, name, extension, password = (record[key] for key in ("owner", "name", "extension", "password"))
        if not isinstance(owner, str) or not _OWNER.fullmatch(owner):
            raise ValueError("Utente dispositivo non valido")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64 or any(not (char.isalnum() or char in " -_") for char in name):
            raise ValueError("Nome dispositivo non valido")
        if not isinstance(extension, str) or not _EXTENSION.fullmatch(extension) or extension in extensions:
            raise ValueError("Interno dispositivo duplicato o non valido")
        if not isinstance(password, str) or not _PASSWORD.fullmatch(password):
            raise ValueError("Password SIP dispositivo non valida")
        owners[owner] = owners.get(owner, 0) + 1
        if owners[owner] > 6:
            raise ValueError("Massimo sei dispositivi per utente")
        extensions.add(extension)
        result[device_id] = {"owner": owner, "name": name.strip(), "extension": extension, "password": password,
                             "device_type": device_type(record.get("device_type"), name), **preferences(record)}
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
    temporary = path.with_name(f"personal_devices.{secrets.token_hex(8)}.tmp")
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


def new_record(device_id: str, owner: str, name: str, records: dict, reserved: set[str], kind: str = "desktop") -> dict[str, Any]:
    used = {record["extension"] for record in records.values()} | reserved
    extension = next((str(number) for number in range(8302, 8350) if str(number) not in used), None)
    if extension is None:
        raise ValueError("Nessun interno personale disponibile")
    record = {"owner": owner, "name": name, "extension": extension, "password": secrets.token_urlsafe(36),
              "device_type": device_type(kind, name), "ringtone": "doorbell", "ring_volume": 80, "vibration": True, "silent": False, "dnd": False,
              "video_capable": False, "video_enabled": False, "camera_facing": "user"}
    validate({**records, device_id: record})
    return record


def asterisk_username(device_id: str) -> str:
    return "pd_" + uuid.UUID(device_id).hex[:24]


def revoked() -> set[str]:
    try:
        value = json.loads(_revoked_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set()
    if not isinstance(value, list) or len(value) > 1000:
        raise ValueError("Elenco revoche dispositivi non valido")
    return {validate_id(item) for item in value}


def revoke_id(device_id: str) -> None:
    value = revoked() | {validate_id(device_id)}
    if len(value) > 1000:
        raise ValueError("Elenco revoche dispositivi pieno")
    path = _revoked_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"personal_revocations.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            os.chmod(temporary, 0o600)
            json.dump(sorted(value), file)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def public(records: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    return [{"device_id": device_id, "owner": record["owner"], "name": record["name"], "extension": record["extension"],
             "device_type": record["device_type"], **preferences(record)}
            for device_id, record in sorted(records.items(), key=lambda item: item[1]["extension"])]
