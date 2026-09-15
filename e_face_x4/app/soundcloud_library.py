from __future__ import annotations
import json, os, re
from pathlib import Path
from typing import Any

def _path() -> Path:
    return Path(os.environ.get("EFACE_SOUNDCLOUD_LIBRARY", "/data/soundcloud_library.json"))

def load() -> dict[str, list[dict[str, Any]]]:
    try: data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): data = {}
    return {"favorites": data.get("favorites", []) if isinstance(data.get("favorites"), list) else [], "recent": data.get("recent", []) if isinstance(data.get("recent"), list) else []}

def _track(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not re.fullmatch(r"soundcloud:tracks:\d+", str(value.get("urn") or "")):
        raise ValueError("Brano SoundCloud non valido")
    clean = {key: str(value.get(key) or "")[:2048] for key in ("urn", "title", "artist", "artwork", "permalink_url")}
    clean.update({"type": "track", "duration": max(0, min(int(value.get("duration") or 0), 86400)), "playable": True})
    return clean

def _save(data: dict) -> None:
    path = _path(); path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8"); os.chmod(temporary, 0o600); temporary.replace(path)

def remember(value: Any) -> dict:
    item = _track(value); data = load(); data["recent"] = [item] + [x for x in data["recent"] if x.get("urn") != item["urn"]][:39]; _save(data); return data

def toggle(value: Any) -> dict:
    item = _track(value); data = load(); existing = any(x.get("urn") == item["urn"] for x in data["favorites"])
    data["favorites"] = [x for x in data["favorites"] if x.get("urn") != item["urn"]]
    if not existing: data["favorites"].insert(0, item)
    _save(data); return data
