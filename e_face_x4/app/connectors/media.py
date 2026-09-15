from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, AsyncIterator
from urllib.parse import quote

import httpx

from ..config import ProviderConfig
from .base import Connector


_LOCAL_SNAPSHOT_CACHE: dict[str, Any] | None = None
_LOCAL_SNAPSHOT_CACHED_AT = 0.0
_LOCAL_SNAPSHOT_GRACE_SECONDS = 60.0


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


class EvoiceLocalMediaConnector(EkonexMediaConnector):
    """Media transport exposed by the Ekonex Voice HA integration."""

    label = "Ekonex Voice locale"

    def __init__(self, timeout: float) -> None:
        # Home Assistant's local evoice snapshot can legitimately take over ten
        # seconds while its entity registry is being rebuilt after a restart.
        self.timeout = max(15.0, timeout)
        self.base_url = "http://supervisor/core/api/evoice/media"
        self.token = str(os.environ.get("SUPERVISOR_TOKEN") or "").strip()

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _url(self, suffix: str) -> str:
        return f"{self.base_url}{suffix}"

    async def snapshot(self) -> dict[str, Any]:
        global _LOCAL_SNAPSHOT_CACHE, _LOCAL_SNAPSHOT_CACHED_AT
        if not self.token:
            return {"id": self.id, "label": self.label, "status": "misconfigured", "reason": "SUPERVISOR_TOKEN non disponibile", "items": []}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                response = await client.get(self._url("/snapshot"), headers=self.headers())
                response.raise_for_status()
            payload = response.json()
            players = payload.get("players", []) if isinstance(payload, dict) else []
            result = {
                "id": self.id, "label": self.label, "status": "online",
                "connection_status": "online", "items": [normalize_local_player(item) for item in players if isinstance(item, dict)],
                "groups": payload.get("groups", []) if isinstance(payload.get("groups"), list) else [],
            }
            _LOCAL_SNAPSHOT_CACHE = result
            _LOCAL_SNAPSHOT_CACHED_AT = time.monotonic()
            return result
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            if _LOCAL_SNAPSHOT_CACHE is not None and time.monotonic() - _LOCAL_SNAPSHOT_CACHED_AT <= _LOCAL_SNAPSHOT_GRACE_SECONDS:
                return {**_LOCAL_SNAPSHOT_CACHE, "status": "stale", "reason": _reason(exc)}
            return {"id": self.id, "label": self.label, "status": "offline", "reason": _reason(exc), "items": []}

    async def command(self, registry_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        local_payload = dict(payload)
        if local_payload.get("operation") == "turn_off":
            local_payload["operation"] = "media_stop"
        return await super().command(registry_id, local_payload)


def normalize_player(player: dict[str, Any]) -> dict[str, Any]:
    registry_id = str(player.get("registry_id") or "")
    media = player.get("media") if isinstance(player.get("media"), dict) else {}
    area = player.get("area") if isinstance(player.get("area"), dict) else {}
    capabilities = player.get("capabilities") if isinstance(player.get("capabilities"), dict) else {}
    group = player.get("group") if isinstance(player.get("group"), dict) else None
    experiences = player.get("experiences") if isinstance(player.get("experiences"), list) else ["watch", "listen"]
    identity = " ".join(str(player.get(key) or "") for key in ("name", "entity_id", "device_class", "manufacturer", "model")).casefold()
    is_echo = bool(player.get("is_echo")) or any(token in identity for token in ("amazon", "alexa", "echo"))
    tts_available = bool(player.get("tts_available") or capabilities.get("tts") or capabilities.get("announce"))
    dnd_available = bool(player.get("dnd_available") or capabilities.get("dnd") or capabilities.get("do_not_disturb"))
    return {
        "id": f"media:{registry_id}", "registry_id": registry_id, "entity_id": str(player.get("entity_id") or ""), "provider": "evoice",
        "kind": "media_player", "icon": "mdi:speaker", "name": str(player.get("name") or "Player"),
        "room": str(area.get("name") or player.get("room_name") or "Senza stanza"), "state": player.get("state"),
        "availability": str(player.get("availability") or "unknown"),
        "connection_status": str(player.get("connection_status") or ("online" if player.get("availability") == "available" else "offline")),
        "title": media.get("title"), "artist": media.get("artist"), "album": media.get("album"),
        "duration_seconds": media.get("duration_seconds"), "content_fingerprint": media.get("content_fingerprint"),
        "volume": player.get("volume_percent"), "muted": player.get("muted"),
        "source": player.get("source"), "source_list": player.get("source_list") or [],
        "capabilities": capabilities, "group": group, "resource_revision": player.get("resource_revision"),
        "experiences": [str(item).lower() for item in experiences if str(item).lower() in {"watch", "listen"}],
        "device_type": "echo" if is_echo else str(player.get("device_class") or "media_player"),
        "manufacturer": str(player.get("manufacturer") or ""), "tts_available": tts_available,
        "dnd_available": dnd_available, "dnd": bool(player.get("dnd") or player.get("do_not_disturb")),
    }


def normalize_local_player(player: dict[str, Any]) -> dict[str, Any]:
    """Add a stable cache key for the artwork endpoint exposed by e-Voice local."""
    item = normalize_player(player)
    try:
        supported_features = int(player.get("supported_features") or 0)
    except (TypeError, ValueError):
        supported_features = 0
    item["capabilities"] = {
        **item["capabilities"],
        "turn_off": bool(
            item["capabilities"].get("turn_off")
            or supported_features & 256
            or (item["device_type"] == "echo" and item["capabilities"].get("stop"))
        ),
    }
    media = player.get("media") if isinstance(player.get("media"), dict) else {}
    artwork_identity = {key: media.get(key) for key in ("title", "artist", "album")}
    if any(artwork_identity.values()):
        encoded = json.dumps(artwork_identity, ensure_ascii=False, sort_keys=True).encode()
        item["content_fingerprint"] = hashlib.sha256(encoded).hexdigest()
        item["capabilities"] = {**item["capabilities"], "artwork": True}
    return item


def _reason(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"risposta HTTP {exc.response.status_code}"
    return type(exc).__name__
