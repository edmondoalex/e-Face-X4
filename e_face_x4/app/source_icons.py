from __future__ import annotations

import base64
import binascii
import os
from pathlib import Path

MIME_SUFFIX = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}


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
