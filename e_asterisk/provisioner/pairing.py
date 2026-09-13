"""One-time installer pairing; long-lived key stays in addon_config."""

from __future__ import annotations

import hmac
import json
import secrets
import threading
import time
from pathlib import Path

from managed_config import _atomic_write

_LOCK = threading.RLock()
CODE_SECONDS = 30 * 60


class Pairing:
    def __init__(self, persistent: Path, temporary: Path) -> None:
        self.persistent = persistent
        self.temporary = temporary

    def token(self) -> str:
        try:
            value = json.loads(self.persistent.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return ""
        if not isinstance(value, dict) or not isinstance(value.get("token"), str) or len(value["token"]) < 32:
            raise RuntimeError("Chiave di associazione danneggiata")
        return value["token"]

    def ensure_code(self) -> str | None:
        """Create or renew an expiring code only while this site is unpaired."""
        with _LOCK:
            if self.token():
                return None
            try:
                value = json.loads(self.temporary.read_text(encoding="utf-8"))
                if isinstance(value, dict) and value.get("expires", 0) > time.time() and isinstance(value.get("code"), str):
                    return value["code"]
            except (OSError, ValueError, TypeError):
                pass
            code = secrets.token_hex(8).upper()
            _atomic_write(self.temporary, json.dumps({"code": code, "expires": time.time() + CODE_SECONDS}))
            print(f"e-Face pairing code (valid 30 minutes): {code}", flush=True)
            return code

    def consume(self, code: str) -> str:
        with _LOCK:
            if self.token():
                raise ValueError("Impianto già associato")
            try:
                value = json.loads(self.temporary.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError) as exc:
                raise ValueError("Codice scaduto o non disponibile") from exc
            expected = value.get("code", "") if isinstance(value, dict) else ""
            if not isinstance(expected, str) or not isinstance(code, str) or not hmac.compare_digest(code, expected) or value.get("expires", 0) <= time.time():
                raise ValueError("Codice non valido o scaduto")
            token = secrets.token_urlsafe(48)
            _atomic_write(self.persistent, json.dumps({"token": token}))
            self.temporary.unlink(missing_ok=True)
            return token
