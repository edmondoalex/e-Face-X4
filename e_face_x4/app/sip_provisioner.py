"""Narrow client for the optional, internal Asterisk provisioner."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

import httpx


def settings() -> tuple[str, str] | None:
    url = os.environ.get("EFACE_PROVISION_URL", "").rstrip("/")
    token = os.environ.get("EFACE_PROVISION_TOKEN", "")
    parsed = urlsplit(url)
    if not url or not token or len(token) < 32:
        return None
    if parsed.scheme != "http" or parsed.hostname not in {"172.30.32.1", "127.0.0.1"} or parsed.port != 8350 or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        return None
    return url, token


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
