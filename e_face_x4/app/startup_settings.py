from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any


def _path() -> Path:
    return Path(os.environ.get("EFACE_STARTUP_CONFIG", "/data/startup.json"))


def load() -> dict[str, Any]:
    try:
        raw = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    enabled = raw.get("enabled") is True
    try:
        duration_ms = int(raw.get("duration_ms", 5000))
    except (TypeError, ValueError):
        duration_ms = 5000
    return {"enabled": enabled, "duration_ms": max(500, min(duration_ms, 30_000))}


def save(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Configurazione avvio non valida")
    enabled = value.get("enabled") is True
    try:
        duration_ms = int(value.get("duration_ms", 5000))
    except (TypeError, ValueError) as exc:
        raise ValueError("Durata schermata iniziale non valida") from exc
    if not 500 <= duration_ms <= 30_000:
        raise ValueError("La durata deve essere compresa tra 0,5 e 30 secondi")
    result = {"enabled": enabled, "duration_ms": duration_ms}
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            json.dump(result, file)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temporary, 0o600)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return result
