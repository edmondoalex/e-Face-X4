"""Installation-local visibility for Control4 recently played entries.

The Director history remains untouched; users can restore hidden entries.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def _path() -> Path:
    return Path(os.environ.get("EFACE_HIDDEN_RECENTS", "/data/control4_hidden_recents.json"))


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def load_hidden_recents() -> set[str]:
    try:
        value = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {item for item in value if isinstance(item, str) and len(item) == 64} if isinstance(value, list) else set()


def _save(items: set[str]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(sorted(items)), encoding="utf-8")
    temporary.replace(path)


def hide_recent(key: str) -> int:
    if not key or len(key) > 256:
        raise ValueError("Elemento recente non valido")
    items = load_hidden_recents()
    if len(items) >= 500 and _digest(key) not in items:
        raise ValueError("Limite elementi nascosti raggiunto")
    items.add(_digest(key))
    _save(items)
    return len(items)


def restore_recents() -> None:
    _save(set())


def filter_recents(items: list[dict]) -> tuple[list[dict], int]:
    hidden = load_hidden_recents()
    return [item for item in items if _digest(str(item.get("key") or "")) not in hidden], len(hidden)
