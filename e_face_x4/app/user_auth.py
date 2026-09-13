from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

COOKIE = "eface_user"
SESSION_SECONDS = 12 * 60 * 60


def _directory() -> Path:
    return Path(os.environ.get("EFACE_AUTH_DIR", "/data/auth"))


def _users_path() -> Path:
    return _directory() / "users.json"


def enabled() -> bool:
    return _users_path().is_file()


def _secret() -> bytes:
    path = _directory() / "session.secret"
    try:
        value = path.read_bytes()
        if len(value) >= 32:
            return value
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_bytes(32)
    with path.open("xb") as file:
        file.write(value)
    return value


def _users() -> dict:
    try:
        value = json.loads(_users_path().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def create_admin(password: str) -> None:
    if enabled():
        raise ValueError("Account già inizializzato")
    if len(password) < 12 or len(password) > 256:
        raise ValueError("La password deve avere da 12 a 256 caratteri")
    salt = secrets.token_bytes(32)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    path = _users_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as file:
        os.chmod(path, 0o600)
        json.dump({"admin": {"salt": salt.hex(), "hash": digest.hex()}}, file)


def verify(username: str, password: str) -> bool:
    user = _users().get(username)
    if not isinstance(user, dict):
        return False
    try:
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(user["salt"]), n=16384, r=8, p=1)
        return hmac.compare_digest(digest, bytes.fromhex(user["hash"]))
    except (KeyError, ValueError, TypeError):
        return False


def create_session(username: str) -> str:
    expiry = int(time.time()) + SESSION_SECONDS
    nonce = secrets.token_hex(16)
    payload = f"{username}.{expiry}.{nonce}"
    signature = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def session_user(value: str | None) -> str | None:
    try:
        username, expiry, nonce, signature = (value or "").split(".", 3)
        payload = f"{username}.{expiry}.{nonce}"
        expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if int(expiry) < int(time.time()) or not hmac.compare_digest(signature, expected):
            return None
        return username if username in _users() else None
    except (ValueError, OSError):
        return None
