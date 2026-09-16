from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, AsyncIterator
from urllib.parse import urlsplit, urlunsplit

import httpx
import websockets

from .base import Connector

HA_WEBSOCKET_MAX_BYTES = 16 * 1024 * 1024


def local_websocket_urls(supervisor: str, home_assistant: str = "http://homeassistant:8123") -> tuple[str, ...]:
    """Return local HA WebSocket endpoints in compatibility order."""
    candidates = (
        f"{supervisor.rstrip('/')}/core/websocket",
        f"{home_assistant.rstrip('/')}/api/websocket",
    )
    urls: list[str] = []
    for candidate in candidates:
        parsed = urlsplit(candidate)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        url = urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, ""))
        if url not in urls:
            urls.append(url)
    return tuple(urls)


class LocalMediaConnector(Connector):
    id = "evoice"
    label = "Ekonex Media locale"

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.token = os.environ.get("SUPERVISOR_TOKEN", "")
        supervisor = os.environ.get("SUPERVISOR_API", "http://supervisor").rstrip("/")
        self.api_url = f"{supervisor}/core/api"
        home_assistant = os.environ.get("HOME_ASSISTANT_URL", "http://homeassistant:8123")
        self.ws_urls = local_websocket_urls(supervisor, home_assistant)

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def _connect_websocket(self) -> Any:
        if not self.token:
            raise RuntimeError("SUPERVISOR_TOKEN mancante")
        failures: list[str] = []
        for index, url in enumerate(self.ws_urls, start=1):
            ws = None
            try:
                ws = await websockets.connect(
                    url,
                    open_timeout=self.timeout,
                    max_size=HA_WEBSOCKET_MAX_BYTES,
                    additional_headers={"Authorization": f"Bearer {self.token}"},
                )
                await ws.recv()
                await ws.send(json.dumps({"type": "auth", "access_token": self.token}))
                authenticated = json.loads(await ws.recv())
                if authenticated.get("type") != "auth_ok":
                    raise RuntimeError("autenticazione rifiutata")
                return ws
            except Exception as exc:
                failures.append(f"percorso {index}: {type(exc).__name__}")
                if ws is not None:
                    await ws.close()
        raise RuntimeError("WebSocket Home Assistant locale non raggiungibile (" + ", ".join(failures) + ")")

    async def _registry_snapshot(self) -> dict[str, Any]:
        ws = await self._connect_websocket()
        try:
            commands = {
                1: "get_states", 2: "config/entity_registry/list",
                3: "config/device_registry/list", 4: "config/area_registry/list",
            }
            for command_id, command_type in commands.items():
                await ws.send(json.dumps({"id": command_id, "type": command_type}))
            results: dict[int, Any] = {}
            while len(results) < len(commands):
                message = json.loads(await ws.recv())
                if message.get("type") == "result" and message.get("id") in commands:
                    if not message.get("success"):
                        raise RuntimeError(f"comando HA fallito: {commands[message['id']]}")
                    results[int(message["id"])] = message.get("result") or []
            return {"states": results[1], "entities": results[2], "devices": results[3], "areas": results[4]}
        finally:
            await ws.close()

    async def snapshot(self) -> dict[str, Any]:
        try:
            raw = await self._registry_snapshot()
            players, groups = normalize_local_snapshot(raw)
            rooms = sorted(
                {str(item.get("name")) for item in raw.get("areas", []) if isinstance(item, dict) and item.get("name")},
                key=str.casefold,
            )
            return {"id": self.id, "label": self.label, "status": "online", "connection_status": "online", "items": players, "groups": groups, "rooms": rooms}
        except Exception as exc:
            return {"id": self.id, "label": self.label, "status": "offline", "reason": str(exc)[:160], "items": [], "groups": []}

    async def command(self, registry_id: str, operation: str, value: Any = None) -> dict[str, Any]:
        raw = await self._registry_snapshot()
        entries = {str(item.get("id")): item for item in raw["entities"] if isinstance(item, dict)}
        entry = entries.get(registry_id)
        if entry is None and registry_id.startswith("entity:"):
            entity_id = registry_id.removeprefix("entity:")
            entry = {"id": registry_id, "entity_id": entity_id} if entity_id.startswith("media_player.") else None
        if not entry or not str(entry.get("entity_id", "")).startswith("media_player."):
            raise ValueError("Player locale non trovato")
        entity_id = str(entry["entity_id"])
        services = {
            "media_play": "media_play", "media_pause": "media_pause", "media_stop": "media_stop",
            "media_next": "media_next_track", "media_previous": "media_previous_track",
            "volume_mute": "volume_mute", "volume_unmute": "volume_mute",
            "set_volume": "volume_set", "select_source": "select_source",
            "media_join": "join", "media_unjoin": "unjoin",
        }
        if operation == "tts":
            message = str(value or "").strip()
            if not message or len(message) > 500:
                raise ValueError("Messaggio TTS non valido")
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                response = await client.post(f"{self.api_url}/services/notify/alexa_media", headers=self.headers(), json={"message": message, "target": [entity_id], "data": {"type": "tts"}})
                response.raise_for_status()
            return {"status": "success", "operation": operation, "registry_id": registry_id}
        if operation not in services:
            raise ValueError("Comando multimedia locale non valido")
        body: dict[str, Any] = {"entity_id": entity_id}
        if operation == "set_volume": body["volume_level"] = max(0, min(100, int(value))) / 100
        elif operation in {"volume_mute", "volume_unmute"}: body["is_volume_muted"] = operation == "volume_mute"
        elif operation == "select_source": body["source"] = str(value)
        elif operation == "media_join":
            member_ids = value if isinstance(value, list) else []
            body["group_members"] = [entries[item]["entity_id"] for item in member_ids if item in entries]
            if len(body["group_members"]) != len(member_ids): raise ValueError("Membro locale non trovato")
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            response = await client.post(f"{self.api_url}/services/media_player/{services[operation]}", headers=self.headers(), json=body)
            response.raise_for_status()
        return {"status": "success", "operation": operation, "registry_id": registry_id}

    async def artwork(self, registry_id: str) -> httpx.Response:
        raw = await self._registry_snapshot()
        entry = next((item for item in raw["entities"] if isinstance(item, dict) and str(item.get("id")) == registry_id), None)
        if entry is None and registry_id.startswith("entity:"):
            entry = {"entity_id": registry_id.removeprefix("entity:")}
        if not entry or not str(entry.get("entity_id", "")).startswith("media_player."):
            raise ValueError("Player locale non trovato")
        entity_id = str(entry["entity_id"])
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            return await client.get(f"{self.api_url}/media_player_proxy/{entity_id}", headers=self.headers())

    async def group_volume(self, group_id: str, requested: int) -> dict[str, Any]:
        raw = await self._registry_snapshot()
        players, groups = normalize_local_snapshot(raw)
        group = next((item for item in groups if item["group_id"] == group_id), None)
        if group is None:
            raise ValueError("Gruppo locale non trovato")
        by_registry = {item["registry_id"]: item for item in players}
        members = [by_registry[item] for item in group["member_registry_ids"] if item in by_registry]
        if len(members) != len(group["member_registry_ids"]) or any(item["volume"] is None for item in members):
            raise ValueError("Volume gruppo non disponibile")
        average = sum(int(item["volume"]) for item in members) / len(members)
        delta = max(0, min(100, int(requested))) - average
        results = []
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            for member in members:
                target = max(0, min(100, round(int(member["volume"]) + delta)))
                try:
                    response = await client.post(f"{self.api_url}/services/media_player/volume_set", headers=self.headers(), json={"entity_id": member["entity_id"], "volume_level": target / 100})
                    response.raise_for_status()
                    results.append({"registry_id": member["registry_id"], "previous_percent": member["volume"], "target_percent": target, "status": "success"})
                except httpx.HTTPError:
                    results.append({"registry_id": member["registry_id"], "previous_percent": member["volume"], "target_percent": target, "status": "failed", "error_code": "SERVICE_CALL_FAILED"})
        return {"status": "success" if all(item["status"] == "success" for item in results) else "partial_failure", "operation": "set_group_volume", "group_id": group_id, "members": results}

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        # e-Voice already exposes its filtered SSE stream. Consuming it here
        # avoids a second broad Home Assistant state subscription and lets the
        # shared e-Face broker own the single upstream connection.
        async for event in super().events():
            yield event


def normalize_local_snapshot(raw: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entries = {str(item.get("entity_id")): item for item in raw.get("entities", []) if isinstance(item, dict)}
    devices = {str(item.get("id")): item for item in raw.get("devices", []) if isinstance(item, dict)}
    areas = {str(item.get("area_id")): str(item.get("name") or "") for item in raw.get("areas", []) if isinstance(item, dict)}
    by_entity: dict[str, dict[str, Any]] = {}
    for state in raw.get("states", []):
        entity_id = str(state.get("entity_id") or "") if isinstance(state, dict) else ""
        entry = entries.get(entity_id)
        if not entity_id.startswith("media_player.") or (entry and entry.get("disabled_by")):
            continue
        entry = entry or {"id": f"entity:{entity_id}", "entity_id": entity_id, "device_id": None}
        attrs = state.get("attributes") if isinstance(state.get("attributes"), dict) else {}
        area_id = entry.get("area_id") or (devices.get(str(entry.get("device_id"))) or {}).get("area_id")
        player_name = str(attrs.get("friendly_name") or entry.get("name") or entity_id)
        features = int(attrs.get("supported_features") or 0)
        media_class = str(entry.get("device_class") or attrs.get("device_class") or "").lower()
        experiences = ["watch"] if media_class == "tv" else ["listen"]
        changed = str(state.get("last_updated") or state.get("last_changed") or "")
        try: revision = int(datetime.fromisoformat(changed.replace("Z", "+00:00")).timestamp() * 1_000_000)
        except ValueError: revision = 0
        volume = attrs.get("volume_level")
        device = devices.get(str(entry.get("device_id"))) or {}
        identity = " ".join(str(value or "") for value in (player_name, entity_id, device.get("manufacturer"), device.get("model"))).casefold()
        is_echo = any(token in identity for token in ("amazon", "alexa", "echo"))
        item = {
            "id": f"media:{entry['id']}", "registry_id": str(entry["id"]), "entity_id": entity_id,
            "provider": "evoice", "kind": "media_player", "icon": str(attrs.get("icon") or "mdi:speaker"),
            "name": player_name, "room": areas.get(str(area_id)) or player_name,
            "state": state.get("state"), "availability": "unavailable" if state.get("state") == "unavailable" else "available",
            "connection_status": "online", "title": attrs.get("media_title"), "artist": attrs.get("media_artist"),
            "album": attrs.get("media_album_name"), "duration_seconds": attrs.get("media_duration"),
            "content_fingerprint": changed or entity_id, "volume": round(float(volume) * 100) if isinstance(volume, (int, float)) and not isinstance(volume, bool) else None,
            "muted": attrs.get("is_volume_muted"), "source": attrs.get("source"), "source_list": attrs.get("source_list") or [],
            "group_entity_ids": attrs.get("group_members") or [], "capabilities": {"play": bool(features & 16384), "pause": bool(features & 1), "stop": bool(features & 4096), "next": bool(features & 32), "previous": bool(features & 16), "set_volume": bool(features & 4), "mute": bool(features & 8), "select_source": bool(features & 2048), "grouping": bool(features & 524288), "artwork": bool(attrs.get("entity_picture"))},
            "resource_revision": revision, "experiences": experiences,
            "device_type": "echo" if is_echo else (media_class or "media_player"),
            "manufacturer": str(device.get("manufacturer") or ""), "tts_available": is_echo,
        }
        by_entity[entity_id] = item
    players = list(by_entity.values())
    groups: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for player in players:
        member_ids = tuple(sorted({by_entity[e]["registry_id"] for e in player.pop("group_entity_ids", []) if e in by_entity}))
        if len(member_ids) < 2 or member_ids in seen: continue
        seen.add(member_ids)
        group = {"group_id": "local:" + ":".join(member_ids), "member_registry_ids": list(member_ids), "completeness": "complete", "resource_revision": max(by_entity[e]["resource_revision"] for e in by_entity if by_entity[e]["registry_id"] in member_ids)}
        groups.append(group)
        for item in players:
            if item["registry_id"] in member_ids: item["group"] = group
    return players, groups
