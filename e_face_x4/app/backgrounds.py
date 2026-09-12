from __future__ import annotations

import base64, binascii, hashlib, json, os
from pathlib import Path

PRESETS = {"teal", "midnight", "graphite", "ocean", "warm"}
CARD_THEMES = {"graphite", "petrol", "midnight", "slate", "warm"}
MIME_SUFFIX = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}

def _directory() -> Path: return Path(os.environ.get("EFACE_BACKGROUNDS", "/data/backgrounds"))
def _key(room: str | None) -> str: return "global" if not room else "room-" + hashlib.sha256(room.encode()).hexdigest()[:20]

def _config() -> dict:
    try: raw = json.loads((_directory() / "selection.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): raw = {}
    return raw if isinstance(raw, dict) else {}

def load_background(room: str | None = None) -> dict[str, str]:
    raw = _config(); selected = raw.get("rooms", {}).get(room) if room and isinstance(raw.get("rooms"), dict) else raw.get("global")
    if not isinstance(selected, dict): selected = {"mode": "inherit"} if room else {"mode": "preset", "preset": "teal"}
    mode, preset = str(selected.get("mode") or "inherit"), str(selected.get("preset") or "teal")
    if mode == "custom" and not load_background_image(room): mode = "inherit" if room else "preset"
    return {"mode": mode if mode in {"preset", "custom", "inherit"} else "inherit", "preset": preset if preset in PRESETS else "teal"}

def load_backgrounds() -> dict:
    raw = _config(); rooms = raw.get("rooms") if isinstance(raw.get("rooms"), dict) else {}
    return {"global": load_background(), "rooms": {room: load_background(room) for room in rooms}}

def load_card_theme() -> str:
    value = str(_config().get("card_theme") or "graphite")
    return value if value in CARD_THEMES else "graphite"

def save_card_theme(theme: str) -> None:
    if theme not in CARD_THEMES: raise ValueError("Colore card non valido")
    raw = _config(); raw["card_theme"] = theme; _write(raw)

def save_preset(preset: str, room: str | None = None) -> None:
    if preset not in PRESETS: raise ValueError("Sfondo predefinito non valido")
    _save_selection({"mode": "preset", "preset": preset}, room)

def save_inherit(room: str) -> None:
    if not room: raise ValueError("Stanza non valida")
    raw = _config(); rooms = raw.get("rooms") if isinstance(raw.get("rooms"), dict) else {}; rooms.pop(room, None); raw["rooms"] = rooms; _write(raw)

def save_background_image(mime: str, encoded: str, room: str | None = None) -> None:
    if mime not in MIME_SUFFIX: raise ValueError("Formato foto non valido")
    try: content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc: raise ValueError("Dati foto non validi") from exc
    valid = (mime == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n")) or (mime == "image/jpeg" and content.startswith(b"\xff\xd8\xff")) or (mime == "image/webp" and content.startswith(b"RIFF") and content[8:12] == b"WEBP")
    if not valid or not 16 <= len(content) <= 4_000_000: raise ValueError("Foto non valida o superiore a 4 MB")
    directory = _directory(); directory.mkdir(parents=True, exist_ok=True); key = _key(room)
    for suffix in MIME_SUFFIX.values():
        try: (directory / f"{key}{suffix}").unlink()
        except FileNotFoundError: pass
    target = directory / f"{key}{MIME_SUFFIX[mime]}"; temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(content); os.chmod(temporary, 0o600); temporary.replace(target); _save_selection({"mode": "custom", "preset": "teal"}, room)

def load_background_image(room: str | None = None) -> tuple[str, bytes] | None:
    key = _key(room)
    for mime, suffix in MIME_SUFFIX.items():
        try: content = (_directory() / f"{key}{suffix}").read_bytes()
        except OSError: continue
        if 16 <= len(content) <= 4_000_000: return mime, content
    return None

def _save_selection(value: dict, room: str | None) -> None:
    raw = _config()
    if room:
        rooms = raw.get("rooms") if isinstance(raw.get("rooms"), dict) else {}; rooms[room] = value; raw["rooms"] = rooms
    else: raw["global"] = value
    _write(raw)

def _write(value: dict) -> None:
    directory = _directory(); directory.mkdir(parents=True, exist_ok=True); target = directory / "selection.json"; temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8"); os.chmod(temporary, 0o600); temporary.replace(target)
