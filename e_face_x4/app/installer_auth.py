from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

COOKIE = "eface_installer"


def _secret() -> bytes:
    path = Path(os.environ.get("EFACE_INSTALLER_SECRET", "/data/installer.secret"))
    try:
        value = path.read_bytes()
        if len(value) >= 32:
            return value
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_bytes(32)
    path.write_bytes(value)
    return value


def create_session() -> str:
    expires = str(int(time.time()) + 8 * 60 * 60)
    signature = hmac.new(_secret(), expires.encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{signature}"


def valid_session(value: str | None) -> bool:
    try:
        expires, signature = (value or "").split(".", 1)
        expected = hmac.new(_secret(), expires.encode(), hashlib.sha256).hexdigest()
        return int(expires) >= int(time.time()) and hmac.compare_digest(signature, expected)
    except (ValueError, OSError):
        return False
