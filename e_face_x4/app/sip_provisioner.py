"""Narrow client for the optional, internal Asterisk provisioner."""

from __future__ import annotations

import os
import json
import secrets
from pathlib import Path
from urllib.parse import urlsplit

import httpx

DEFAULT_URL = "http://172.30.32.1:8350"


def _secret_path() -> Path:
    return Path(os.environ.get("EFACE_PROVISION_SECRET_PATH", "/data/asterisk_provisioner.json"))


def _saved_token() -> str:
    try:
        value = json.loads(_secret_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return value.get("token", "") if isinstance(value, dict) and isinstance(value.get("token"), str) else ""


def _save_token(token: str) -> None:
    path = _secret_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            os.chmod(temporary, 0o600)
            json.dump({"token": token}, file)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def settings() -> tuple[str, str] | None:
    url = os.environ.get("EFACE_PROVISION_URL", DEFAULT_URL).rstrip("/")
    token = os.environ.get("EFACE_PROVISION_TOKEN", "") or _saved_token()
    parsed = urlsplit(url)
    if not url or not token or len(token) < 32:
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme != "http" or parsed.hostname not in {"172.30.32.1", "127.0.0.1"} or port != 8350 or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        return None
    return url, token


async def pair(code: str) -> None:
    url = os.environ.get("EFACE_PROVISION_URL", DEFAULT_URL).rstrip("/")
    if url not in {DEFAULT_URL, "http://127.0.0.1:8350"}:
        raise RuntimeError("Indirizzo del provisioner non consentito")
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        response = await client.post(f"{url}/v1/pair", json={"code": code})
    if response.status_code != 200:
        raise RuntimeError(f"Associazione Asterisk non riuscita (HTTP {response.status_code})")
    try:
        token = response.json().get("token")
    except ValueError as exc:
        raise RuntimeError("Risposta di associazione non valida") from exc
    if not isinstance(token, str) or len(token) < 32:
        raise RuntimeError("Chiave di associazione non valida")
    _save_token(token)


async def activate(username: str, extension: str, password: str, name: str) -> None:
    configured = settings()
    if configured is None:
        raise RuntimeError("Provisioner Asterisk non associato")
    url, token = configured
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        response = await client.put(
            f"{url}/v1/phones/{username}",
            json={"extension": extension, "password": password, "name": name},
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code != 200:
        raise RuntimeError(f"Provisioner Asterisk: risposta HTTP {response.status_code}")
    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError("Risposta del provisioner non valida") from exc
    if result.get("extension") != extension or result.get("active") is not True:
        raise RuntimeError("Il provisioner non ha confermato l'interno")
