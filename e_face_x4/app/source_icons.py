from __future__ import annotations

import base64
import binascii
import os
import re
from pathlib import Path

MIME_SUFFIX = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
BUILTIN_DIRECTORY = Path(__file__).parent / "static" / "assets" / "control4-icons"
BUILTIN_ICONS = {
    "sonos": "sonos.png",
    "stations": "stations.png",
    "vidaa": "vidaa.png",
    "hisense vidaa smart tv": "vidaa.png",
    "apps": "apps.png",
    "custom app": "apps.png",
    "dlna": "dlna.png",
    "spotify connect": "spotify-connect.png",
    "manage music": "manage-music.png",
    "digital media": "digital-media.png",
    "my music": "digital-media.png",
    "am fm": "am-fm-tuner.png",
    "am fm tuner": "am-fm-tuner.png",
    "am fm radio": "am-fm-tuner.png",
    "wireless music bridge": "wireless-music-bridge.png",
}


def _directory() -> Path:
    return Path(os.environ.get("EFACE_SOURCE_ICONS", "/data/source-icons"))


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
