from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

DEFAULTS = {"8291": "Ufficio", "8292": "Tavolo"}


def _path() -> Path:
    return Path(os.environ.get("EFACE_INTERNAL_STATIONS", "/data/internal_stations.json"))


def load() -> dict[str, str]:
    try:
        value = json.loads(_path().read_text(encoding="utf-8"))
        if isinstance(value, dict) and set(value) == set(DEFAULTS) and all(isinstance(name, str) and name.strip() for name in value.values()):
            return value
    except (OSError, json.JSONDecodeError):
        pass
    return DEFAULTS.copy()


def save(value: dict) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != set(DEFAULTS):
        raise ValueError("Elenco postazioni interne non valido")
    names = {}
    for extension, name in value.items():
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64 or any(ord(char) < 32 for char in name):
            raise ValueError(f"Nome non valido per l'interno {extension}")
        names[extension] = name.strip()
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"internal_stations.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            os.chmod(temporary, 0o600)
            json.dump(names, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return names
