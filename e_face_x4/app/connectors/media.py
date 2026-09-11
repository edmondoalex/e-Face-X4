from __future__ import annotations

from typing import Any, AsyncIterator
from urllib.parse import quote

import httpx

from ..config import ProviderConfig
from .base import Connector


class EkonexMediaConnector(Connector):
    id = "evoice"
    label = "Ekonex Media"

    def __init__(self, config: ProviderConfig, timeout: float) -> None:
        self.config = config
        self.timeout = timeout

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.token}"} if self.config.token else {}

    def _url(self, suffix: str) -> str:
        installation = quote(self.config.installation_id, safe="")
        return f"{self.config.base_url}/api/media/v1/installations/{installation}{suffix}"

    async def snapshot(self) -> dict[str, Any]:
        if not self.config.enabled:
            return {"id": self.id, "label": self.label, "status": "disabled", "items": []}
        if not self.config.base_url or not self.config.installation_id:
            return {"id": self.id, "label": self.label, "status": "misconfigured", "reason": "indirizzo o installation_id mancante", "items": []}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                response = await client.get(self._url("/snapshot"), headers=self.headers())
                response.raise_for_status()
            payload = response.json()
            players = payload.get("players", []) if isinstance(payload, dict) else []
            return {
                "id": self.id,
                "label": self.label,
                "status": "online",
                "installation_revision": payload.get("installation_revision", 0),
                "connection_status": payload.get("connection_status", "unknown"),
                "items": [normalize_player(item) for item in players if isinstance(item, dict)],
                "groups": payload.get("groups", []) if isinstance(payload.get("groups"), list) else [],
            }
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            return {"id": self.id, "label": self.label, "status": "offline", "reason": _reason(exc), "items": []}

    async def command(self, registry_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        resource = quote(registry_id, safe="")
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            response = await client.post(self._url(f"/players/{resource}/commands"), headers=self.headers(), json=payload)
            response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("risposta comando non valida")
        return result

    async def group_command(self, group_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        resource = quote(group_id, safe="")
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            response = await client.post(self._url(f"/groups/{resource}/commands"), headers=self.headers(), json=payload)
            response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("risposta comando gruppo non valida")
        return result

    async def artwork(self, registry_id: str, fingerprint: str, etag: str | None = None) -> httpx.Response:
        resource = quote(registry_id, safe="")
        headers = self.headers()
        if etag:
            headers["If-None-Match"] = etag
        client = httpx.AsyncClient(timeout=self.timeout, follow_redirects=False)
        try:
            response = await client.get(self._url(f"/players/{resource}/artwork"), headers=headers, params={"fingerprint": fingerprint})
            return response
        finally:
            await client.aclose()

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        headers = {**self.headers(), "Accept": "text/event-stream"}
        async with httpx.AsyncClient(timeout=None, follow_redirects=False) as client:
            async with client.stream("GET", self._url("/events"), headers=headers) as response:
                response.raise_for_status()
                data: list[str] = []
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data.append(line[5:].lstrip())
                    elif not line and data:
                        import json
                        event = json.loads("\n".join(data))
                        data.clear()
                        if isinstance(event, dict):
                            yield event


def normalize_player(player: dict[str, Any]) -> dict[str, Any]:
    registry_id = str(player.get("registry_id") or "")
    media = player.get("media") if isinstance(player.get("media"), dict) else {}
    area = player.get("area") if isinstance(player.get("area"), dict) else {}
    capabilities = player.get("capabilities") if isinstance(player.get("capabilities"), dict) else {}
    group = player.get("group") if isinstance(player.get("group"), dict) else None
    experiences = player.get("experiences") if isinstance(player.get("experiences"), list) else ["watch", "listen"]
    return {
        "id": f"media:{registry_id}", "registry_id": registry_id, "provider": "evoice",
        "kind": "media_player", "icon": "mdi:speaker", "name": str(player.get("name") or "Player"),
        "room": str(area.get("name") or "Senza stanza"), "state": player.get("state"),
        "availability": str(player.get("availability") or "unknown"),
        "connection_status": str(player.get("connection_status") or "offline"),
        "title": media.get("title"), "artist": media.get("artist"), "album": media.get("album"),
        "duration_seconds": media.get("duration_seconds"), "content_fingerprint": media.get("content_fingerprint"),
        "volume": player.get("volume_percent"), "muted": player.get("muted"),
        "source": player.get("source"), "source_list": player.get("source_list") or [],
        "capabilities": capabilities, "group": group, "resource_revision": player.get("resource_revision"),
        "experiences": [str(item).lower() for item in experiences if str(item).lower() in {"watch", "listen"}],
    }


def _reason(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"risposta HTTP {exc.response.status_code}"
    return type(exc).__name__
