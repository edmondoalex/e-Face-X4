from __future__ import annotations

import base64
import binascii
import json
import os
import re
import secrets
import threading
from pathlib import Path

MIME_SUFFIX = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
BUILTIN_DIRECTORY = Path(__file__).parent / "static" / "assets" / "control4-icons"
_VISIBILITY_LOCK = threading.RLock()
BUILTIN_SOURCE_IDS = {
    source_id: f"by-id/{source_id}.png"
    for source_id in (
        22, 24, 210, 586, 592, 593, 599, 605, 615, 791, 803, 809, 1319,
        1455, 1528, 1567, 1569, 1578, 1579, 1642, 1644, 1646, 1648, 1650,
        1652, 1654, 1658, 1660, 1662, 1667, 100002,
    )
}
BUILTIN_ICONS = {
    "sonos": "sonos.png",
    "sonos rack audio sonos": "by-id/1455.png",
    "ufficio sonos": "by-id/1528.png",
    "stations": "by-id/24.png",
    "internet radio": "internet-radio.png",
    "vidaa": "vidaa.png",
    "hisense vidaa smart tv": "vidaa.png",
    "apps": "by-id/1579.png",
    "custom app": "by-id/1579.png",
    "dlna": "by-id/592.png",
    "spotify connect": "by-id/1569.png",
    "manage music": "by-id/22.png",
    "digital media": "by-id/100002.png",
    "my music": "by-id/1658.png",
    "my music dlna": "by-id/1658.png",
    "am fm": "by-id/605.png",
    "am fm tuner": "by-id/605.png",
    "am fm tuner 2": "by-id/605.png",
    "am fm radio": "by-id/605.png",
    "wireless music bridge": "by-id/210.png",
    "onkyo nr545 sala": "by-id/586.png",
    "pandora": "by-id/593.png",
    "deezer": "by-id/599.png",
    "tunein": "by-id/615.png",
    "projector hisense": "by-id/791.png",
    "xbox one": "by-id/803.png",
    "samsung tv": "by-id/809.png",
    "tv sala": "by-id/1578.png",
    "pc wifi": "by-id/1319.png",
    "airplay": "by-id/1567.png",
    "amazon music": "by-id/1644.png",
    "apple music": "by-id/1646.png",
    "qobuz": "by-id/1648.png",
    "tidal": "by-id/1650.png",
    "soundmachine": "by-id/1652.png",
    "audacy": "by-id/1660.png",
    "iheartradio": "by-id/1662.png",
    "wiim pro e7cc r d": "by-id/1667.png",
}


def _directory() -> Path:
    return Path(os.environ.get("EFACE_SOURCE_ICONS", "/data/source-icons"))


def hidden_source_ids() -> set[int]:
    try:
        values = json.loads((_directory() / "hidden.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {value for value in values if isinstance(value, int) and not isinstance(value, bool) and value > 0} if isinstance(values, list) else set()


def set_source_hidden(source_id: int, hidden: bool) -> set[int]:
    if source_id <= 0:
        raise ValueError("Sorgente non valida")
    with _VISIBILITY_LOCK:
        values = hidden_source_ids()
        (values.add if hidden else values.discard)(source_id)
        directory = _directory()
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "hidden.json"
        temporary = directory / f"hidden.{secrets.token_hex(8)}.tmp"
        try:
            with temporary.open("x", encoding="utf-8") as file:
                json.dump(sorted(values), file)
                file.flush()
                os.fsync(file.fileno())
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return values


def load_source_icon(source_id: int) -> tuple[str, bytes] | None:
    for mime, suffix in MIME_SUFFIX.items():
        path = _directory() / f"{source_id}{suffix}"
        try:
            content = path.read_bytes()
        except OSError:
            continue
        if content and len(content) <= 500_000:
            return mime, content
    return None


def load_builtin_source_icon(label: str | None) -> tuple[str, bytes] | None:
    """Return an icon shipped with the add-on, without network dependencies."""
    normalized = re.sub(r"[^a-z0-9]+", " ", str(label or "").casefold()).strip()
    filename = BUILTIN_ICONS.get(normalized)
    if not filename and "sonos" in normalized.split():
        filename = "sonos.png"
    if not filename:
        return None
    try:
        content = (BUILTIN_DIRECTORY / filename).read_bytes()
    except OSError:
        return None
    return ("image/png", content) if content else None


def load_builtin_source_icon_by_id(source_id: int) -> tuple[str, bytes] | None:
    """Return an imported installation icon without treating it as a user override."""
    filename = BUILTIN_SOURCE_IDS.get(source_id)
    if not filename:
        return None
    try:
        content = (BUILTIN_DIRECTORY / filename).read_bytes()
    except OSError:
        return None
    return ("image/png", content) if content else None


def save_source_icon(source_id: int, mime: str, encoded: str) -> None:
    if source_id <= 0 or mime not in MIME_SUFFIX:
        raise ValueError("Formato icona non valido")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Dati icona non validi") from exc
    signatures = {
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "image/webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
        "image/gif": content.startswith((b"GIF87a", b"GIF89a")),
    }
    if not signatures[mime] or not 16 <= len(content) <= 500_000:
        raise ValueError("File icona non valido o superiore a 500 KB")
    delete_source_icon(source_id)
    directory = _directory()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{source_id}{MIME_SUFFIX[mime]}"
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(content)
    os.chmod(temporary, 0o600)
    temporary.replace(target)


def delete_source_icon(source_id: int) -> bool:
    removed = False
    for suffix in MIME_SUFFIX.values():
        try:
            (_directory() / f"{source_id}{suffix}").unlink()
            removed = True
        except FileNotFoundError:
            pass
    return removed
