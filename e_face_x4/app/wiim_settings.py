from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .connectors.wiim import validate_host


def _path() -> Path:
    return Path(os.environ.get("EFACE_WIIM_CONFIG", "/data/wiim.json"))


def load() -> dict[str, Any]:
    try:
        raw = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    return {
        "enabled": raw.get("enabled") is not False,
        "host": str(raw.get("host") or ""),
        "control4_source_id": int(raw.get("control4_source_id") or 0),
        "control4_protocol_id": int(raw.get("control4_protocol_id") or 0),
    }


def validate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Configurazione WiiM non valida")
    host = validate_host(str(value.get("host") or ""))
    source_id = int(value.get("control4_source_id") or 0)
    protocol_id = int(value.get("control4_protocol_id") or 0)
    if not 0 <= source_id <= 2_000_000_000 or not 0 <= protocol_id <= 2_000_000_000:
        raise ValueError("Identificativo Control4 non valido")
    return {"enabled": value.get("enabled") is not False, "host": host, "control4_source_id": source_id, "control4_protocol_id": protocol_id}


def save(value: Any) -> dict[str, Any]:
    result = validate(value)
    path = _path(); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    return result
