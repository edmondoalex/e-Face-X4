from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

COOKIE = "eface_user"
SESSION_SECONDS = 12 * 60 * 60
_LOCK = threading.RLock()
_USERNAME = re.compile(r"^[a-z][a-z0-9_-]{2,31}$")


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


def _save_users(users: dict) -> None:
    path = _users_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"users.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            os.chmod(temporary, 0o600)
            json.dump(users, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _password_fields(password: str) -> dict[str, str]:
    if len(password) < 12 or len(password) > 256:
        raise ValueError("La password deve avere da 12 a 256 caratteri")
    salt = secrets.token_bytes(32)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return {"salt": salt.hex(), "hash": digest.hex()}


def account(username: str) -> dict | None:
    user = _users().get(username)
    if not isinstance(user, dict):
        return None
    return {
        "username": username,
        "name": str(user.get("name") or username),
        "role": "admin" if username == "admin" else "user",
        "active": user.get("active") is not False,
        "origin": str(user.get("origin") or "local"),
        "sync_status": str(user.get("sync_status") or "local"),
        "created_at": str(user.get("created_at") or ""),
        "provider": str(user.get("provider") or ""),
    }


def accounts() -> list[dict]:
    return [item for name in sorted(_users()) if (item := account(name)) is not None]


def create_account(username: str, name: str, password: str, origin: str = "local") -> dict:
    username = username.strip().lower()
    name = name.strip()
    if not _USERNAME.fullmatch(username):
        raise ValueError("Nome utente non valido: usa 3-32 lettere minuscole, numeri, _ o -")
    if not 1 <= len(name) <= 64:
        raise ValueError("Il nome deve avere da 1 a 64 caratteri")
    if origin != "local":
        raise ValueError("Gli inviti VPS non sono ancora disponibili")
    fields = _password_fields(password)
    with _LOCK:
        users = _users()
        if username in users:
            raise ValueError("Nome utente già presente")
        users[username] = {
            **fields,
            "name": name,
            "role": "user",
            "active": True,
            "session_version": 0,
            "origin": "local",
            "sync_status": "local",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "external_id": None,
            "provider": None,
            "expires_at": None,
        }
        _save_users(users)
    return account(username) or {}


def update_account(username: str, *, name: str | None = None, password: str | None = None, active: bool | None = None) -> dict:
    with _LOCK:
        users = _users()
        user = users.get(username)
        if not isinstance(user, dict):
            raise ValueError("Utente non trovato")
        if active is False and username == "admin":
            raise ValueError("Non puoi disattivare l'account admin")
        if name is not None:
            name = name.strip()
            if not 1 <= len(name) <= 64:
                raise ValueError("Il nome deve avere da 1 a 64 caratteri")
            user["name"] = name
        if password is not None:
            user.update(_password_fields(password))
        if active is not None:
            user["active"] = active
        if password is not None or active is False:
            user["session_version"] = int(user.get("session_version", 0)) + 1
        _save_users(users)
    return account(username) or {}


def delete_account(username: str) -> None:
    with _LOCK:
        users = _users()
        if username == "admin":
            raise ValueError("Non puoi eliminare l'account admin")
        if username not in users:
            raise ValueError("Utente non trovato")
        users.pop(username)
        _save_users(users)


def create_admin(password: str) -> None:
    if enabled():
        raise ValueError("Account già inizializzato")
    fields = _password_fields(password)
    path = _users_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as file:
        os.chmod(path, 0o600)
        json.dump({"admin": {**fields, "name": "Admin", "role": "admin", "active": True, "session_version": 0}}, file)


def verify(username: str, password: str) -> bool:
    user = _users().get(username)
    if not isinstance(user, dict) or user.get("active") is False:
        return False
    try:
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(user["salt"]), n=16384, r=8, p=1)
        return hmac.compare_digest(digest, bytes.fromhex(user["hash"]))
    except (KeyError, ValueError, TypeError):
        return False


def create_session(username: str) -> str:
    expiry = int(time.time()) + SESSION_SECONDS
    nonce = secrets.token_hex(16)
    user = _users().get(username, {})
    version = int(user.get("session_version", 0))
    payload = f"{username}.{expiry}.{nonce}.{version}"
    signature = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def session_user(value: str | None) -> str | None:
    try:
        parts = (value or "").split(".")
        if len(parts) == 4:
            username, expiry, nonce, signature = parts
            version = 0
            payload = f"{username}.{expiry}.{nonce}"
        elif len(parts) == 5:
            username, expiry, nonce, version_text, signature = parts
            version = int(version_text)
            payload = f"{username}.{expiry}.{nonce}.{version}"
        else:
            return None
        expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if int(expiry) < int(time.time()) or not hmac.compare_digest(signature, expected):
            return None
        user = _users().get(username)
        return username if isinstance(user, dict) and user.get("active") is not False and version == int(user.get("session_version", 0)) else None
    except (ValueError, OSError):
        return None
