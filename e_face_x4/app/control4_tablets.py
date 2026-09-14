"""Persistent Composer inventory for additional Control4 intercom tablets.

An inventory entry is not a SIP route. Existing 8291/8292 beta routes remain
outside this file until a verified Asterisk migration is available.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from pathlib import Path

_EXTENSION = re.compile(r"829[3-9]\Z")
_SIP_USER = re.compile(r"[A-Za-z0-9_.-]{3,64}\Z")


def _path() -> Path:
    return Path(os.environ.get("EFACE_CONTROL4_TABLETS", "/data/control4_tablets.json"))


def validate(items: object) -> list[dict[str, str]]:
    if not isinstance(items, list) or len(items) > 7:
        raise ValueError("Massimo sette tablet Control4 aggiuntivi")
    result = []
    extensions: set[str] = set()
    users: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"extension", "name", "sip_user"}:
            raise ValueError("Dati tablet incompleti")
        extension, name, sip_user = (item[key] for key in ("extension", "name", "sip_user"))
        if not all(isinstance(value, str) for value in (extension, name, sip_user)):
            raise ValueError("Dati tablet non validi")
        name = name.strip()
        sip_user = sip_user.strip()
        if not _EXTENSION.fullmatch(extension) or extension in extensions:
            raise ValueError("Interno tablet non valido o duplicato (8293-8299)")
        if not 1 <= len(name) <= 64 or any(ord(char) < 32 for char in name):
            raise ValueError("Nome tablet non valido")
        if not _SIP_USER.fullmatch(sip_user) or sip_user.casefold() in users:
            raise ValueError("SIP User Name non valido o duplicato")
        extensions.add(extension)
        users.add(sip_user.casefold())
        result.append({"extension": extension, "name": name, "sip_user": sip_user})
    return sorted(result, key=lambda item: item["extension"])


def load() -> list[dict[str, str]]:
    try:
        return validate(json.loads(_path().read_text(encoding="utf-8")))
    except FileNotFoundError:
        return []


def save(items: object) -> list[dict[str, str]]:
    value = validate(items)
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"control4_tablets.{secrets.token_hex(8)}.tmp")
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
