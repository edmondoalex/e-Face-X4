"""Locally stored copies of device credentials not yet provisioned by e-Face.

These records are inventory only: saving them does not change DoorBird or Asterisk.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

KINDS = {"doorbird", "sip_doorbird", "sip_eface", "sip_control4"}


def _path() -> Path:
    return Path(os.environ.get("EFACE_CREDENTIAL_INVENTORY", "/data/credential_inventory.json"))


def load() -> dict[str, dict[str, str]]:
    try:
        stored = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(stored, dict):
        return {}
    return {
        kind: {"username": str(value.get("username") or ""), "password": str(value.get("password") or "")}
        for kind, value in stored.items()
        if kind in KINDS and isinstance(value, dict)
    }


def save(kind: str, username: str, password: str) -> dict[str, str]:
    if kind not in KINDS:
        raise ValueError("Tipo di credenziale non valido")
    username = username.strip()
    if not username or len(username) > 254 or len(password) > 512:
        raise ValueError("Utente e password obbligatori")
    records = load()
    if not password:
        password = records.get(kind, {}).get("password", "")
    if not password:
        raise ValueError("Password obbligatoria")
    value = {"username": username, "password": password}
    records[kind] = value
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"credential_inventory.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            os.chmod(temporary, 0o600)
            json.dump(records, file)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return value


def delete(kind: str) -> bool:
    if kind not in KINDS:
        raise ValueError("Tipo di credenziale non valido")
    records = load()
    if kind not in records:
        return False
    del records[kind]
    path = _path()
    temporary = path.with_name(f"credential_inventory.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            os.chmod(temporary, 0o600)
            json.dump(records, file)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return True
