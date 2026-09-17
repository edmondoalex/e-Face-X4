from __future__ import annotations

import base64
import binascii
import os
import re
from pathlib import Path


MIME_SUFFIX = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}


def _directory() -> Path:
    return Path(os.environ.get("EFACE_SKYQ_ICON_DIR", "/data/skyq-icons"))


def _key(app_id: str) -> str:
    value = str(app_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", value):
        raise ValueError("App Sky Q non valida")
    return value


def load(app_id: str) -> tuple[str, bytes] | None:
    key = _key(app_id)
    for mime, suffix in MIME_SUFFIX.items():
        try:
            content = (_directory() / f"{key}{suffix}").read_bytes()
        except OSError:
            continue
        if content and len(content) <= 500_000:
            return mime, content
    return None


def save(app_id: str, mime: str, encoded: str) -> None:
    key = _key(app_id)
    if mime not in MIME_SUFFIX:
        raise ValueError("Formato icona non valido")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Dati icona non validi") from exc
    valid = {
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "image/webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
        "image/gif": content.startswith((b"GIF87a", b"GIF89a")),
    }
    if not valid[mime] or not 16 <= len(content) <= 500_000:
        raise ValueError("File icona non valido o superiore a 500 KB")
    delete(app_id)
    directory = _directory()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{key}{MIME_SUFFIX[mime]}"
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(content)
    os.chmod(temporary, 0o600)
    temporary.replace(target)


def delete(app_id: str) -> bool:
    key = _key(app_id)
    removed = False
    for suffix in MIME_SUFFIX.values():
        try:
            (_directory() / f"{key}{suffix}").unlink()
            removed = True
        except FileNotFoundError:
            pass
    return removed
