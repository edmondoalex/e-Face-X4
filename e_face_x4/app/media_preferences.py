from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _path() -> Path:
    return Path(os.environ.get("EFACE_MEDIA_PREFERENCES", "/data/media_players.json"))


def load_preferences() -> dict[str, dict[str, bool | int | str]]:
    try:
        raw = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        key: {
            **{name: bool(value.get(name, False)) for name in ("visible", "audio", "video", "tts")},
            "order": max(0, int(value.get("order", 0))),
            "name": str(value.get("name") or "").strip()[:80],
            "room": str(value.get("room") or "").strip()[:80],
        }
        for key, value in raw.items()
        if isinstance(key, str) and isinstance(value, dict)
    }


def save_preferences(raw: Any, valid_ids: set[str]) -> dict[str, dict[str, bool | int | str]]:
    if not isinstance(raw, dict) or len(raw) > 512:
        raise ValueError("Configurazione player non valida")
    cleaned: dict[str, dict[str, bool | int | str]] = {}
    for registry_id, value in raw.items():
        if registry_id not in valid_ids or not isinstance(value, dict):
            raise ValueError("Player non valido")
        selection = {
            **{name: bool(value.get(name, False)) for name in ("visible", "audio", "video", "tts")},
            "order": max(0, int(value.get("order", 0))),
            "name": str(value.get("name") or "").strip()[:80],
            "room": str(value.get("room") or "").strip()[:80],
        }
        if not (selection["audio"] or selection["video"] or selection["tts"]):
            selection["visible"] = False
        cleaned[registry_id] = selection
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return cleaned


def apply_preferences(snapshot: dict[str, Any]) -> dict[str, Any]:
    preferences = load_preferences()
    if not preferences:
        return snapshot
    snapshot_ids = {str(item.get("registry_id")) for item in snapshot.get("items", []) if isinstance(item, dict)}
    if not snapshot_ids.intersection(preferences):
        return snapshot
    items: list[dict[str, Any]] = []
    for source in snapshot.get("items", []):
        if not isinstance(source, dict):
            continue
        selected = preferences.get(str(source.get("registry_id") or ""))
        if selected is None or not selected["visible"]:
            continue
        item = dict(source)
        item["experiences"] = (["listen"] if selected["audio"] else []) + (["watch"] if selected["video"] else [])
        item["tts_enabled"] = bool(selected.get("tts"))
        if selected.get("name"):
            item["original_name"] = item.get("name")
            item["name"] = selected["name"]
        if selected.get("room"):
            item["original_room"] = item.get("room")
            item["room"] = selected["room"]
        items.append(item)
    items.sort(key=lambda item: int(preferences[str(item.get("registry_id"))]["order"]))
    result = dict(snapshot)
    result["items"] = items
    result["rooms"] = sorted({str(item["room"]) for item in items if item.get("room")}, key=str.casefold)
    visible = {str(item.get("registry_id")) for item in items}
    result["groups"] = [group for group in snapshot.get("groups", []) if set(group.get("member_registry_ids", [])).issubset(visible)]
    return result
