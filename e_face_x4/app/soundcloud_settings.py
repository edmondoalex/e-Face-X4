from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _path() -> Path:
    return Path(os.environ.get("EFACE_SOUNDCLOUD_CONFIG", "/data/soundcloud.json"))


def load() -> dict[str, str]:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    return {"client_id": str(data.get("client_id") or ""), "client_secret": str(data.get("client_secret") or "")}


def public() -> dict[str, Any]:
    data = load()
    return {"client_id": data["client_id"], "secret_configured": bool(data["client_secret"]), "ready": bool(data["client_id"] and data["client_secret"])}


def save(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Configurazione SoundCloud non valida")
    current = load()
    client_id = str(value.get("client_id") or "").strip()
    secret = str(value.get("client_secret") or "").strip() or current["client_secret"]
    if not 8 <= len(client_id) <= 256 or not 8 <= len(secret) <= 512:
        raise ValueError("Client ID o Client Secret SoundCloud non validi")
    path = _path(); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"client_id": client_id, "client_secret": secret}), encoding="utf-8")
    os.chmod(temporary, 0o600); temporary.replace(path)
    return public()
