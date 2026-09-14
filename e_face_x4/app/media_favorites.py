"""Installation-wide, persistent e-Face media favorites."""

from __future__ import annotations

import json
import hashlib
import os
import secrets
import threading
from pathlib import Path
from typing import Any

_LOCK = threading.RLock()


def _path() -> Path:
    return Path(os.environ.get("EFACE_MEDIA_FAVORITES", "/data/control4_media_favorites.json"))


def _artwork_path(identity: str) -> Path:
    return _path().parent / "control4_favorite_artwork" / f"{hashlib.sha256(identity.encode()).hexdigest()}.image"


def save_favorite_artwork(identity: str, content: bytes) -> None:
    if not content or len(content) > 700_000:
        raise ValueError("Copertina preferito non valida")
    path = _artwork_path(identity)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("xb") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_favorite_artwork(identity: str) -> bytes | None:
    try:
        return _artwork_path(identity).read_bytes()
    except OSError:
        return None


def list_favorites() -> list[dict[str, Any]]:
    try:
        raw = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [item for item in raw if isinstance(item, dict) and item.get("kind") in {"station", "recent", "msp"} and isinstance(item.get("id"), str)] if isinstance(raw, list) else []


def enrich_recent_favorites(history: list[dict[str, Any]]) -> bool:
    """Persist service IDs for older favorites while Control4 still lists them."""
    drivers = {str(entry.get("key")): int(entry["driver_id"]) for entry in history
               if isinstance(entry, dict) and str(entry.get("key") or "") and str(entry.get("driver_id") or "").isdigit() and int(entry["driver_id"]) > 0}
    if not drivers:
        return False
    with _LOCK:
        items = list_favorites()
        changed = False
        for item in items:
            if item.get("kind") == "recent" and not item.get("driver_id") and str(item.get("key") or "") in drivers:
                item["driver_id"] = drivers[str(item["key"])]
                changed = True
        if changed:
            _save(items)
        return changed


def _save(items: list[dict[str, Any]]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            json.dump(items, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def add_favorite(item: dict[str, Any]) -> list[dict[str, Any]]:
    kind = item.get("kind")
    identity = item.get("id")
    if kind not in {"station", "recent", "msp"} or not isinstance(identity, str) or not 1 <= len(identity) <= 300:
        raise ValueError("Preferito non valido")
    if not isinstance(item.get("title"), str) or not 1 <= len(item["title"]) <= 200:
        raise ValueError("Titolo preferito non valido")
    with _LOCK:
        items = list_favorites()
        if any(existing["id"] == identity for existing in items):
            return items
        if len(items) >= 100:
            raise ValueError("Limite di 100 preferiti raggiunto")
        items.append(item)
        _save(items)
        return items


def remove_favorite(identity: str) -> list[dict[str, Any]]:
    if not isinstance(identity, str) or not 1 <= len(identity) <= 300:
        raise ValueError("Preferito non valido")
    with _LOCK:
        items = [item for item in list_favorites() if item["id"] != identity]
        _save(items)
        _artwork_path(identity).unlink(missing_ok=True)
        return items


def favorite_by_id(identity: str) -> dict[str, Any]:
    item = next((item for item in list_favorites() if item["id"] == identity), None)
    if not item:
        raise ValueError("Preferito non disponibile")
    return item
