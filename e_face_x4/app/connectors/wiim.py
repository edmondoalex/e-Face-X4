from __future__ import annotations

import asyncio
import ipaddress
import re
from typing import Any
from urllib.parse import urlsplit

import httpx


def validate_host(value: str) -> str:
    try:
        address = ipaddress.ip_address(str(value).strip())
    except ValueError as exc:
        raise ValueError("Indirizzo WiiM non valido") from exc
    if address.version != 4 or not address.is_private or address.is_loopback or address.is_multicast or address.is_unspecified:
        raise ValueError("Il WiiM deve avere un indirizzo IPv4 LAN")
    return str(address)


def decode_linkplay_text(value: Any) -> str:
    text = str(value or "")
    if text and len(text) % 2 == 0 and re.fullmatch(r"[0-9a-fA-F]+", text):
        try:
            return bytes.fromhex(text).decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            pass
    return text


def public_artwork(value: Any) -> str:
    text = str(value or "").strip()
    parts = urlsplit(text)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password or len(text) > 2048:
        return ""
    return text


class WiiMClient:
    """Small native client for the documented WiiM/Linkplay HTTPS API."""

    def __init__(self, host: str, *, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 5.0):
        self.host = validate_host(host)
        self._transport = transport
        self.timeout = max(1.0, min(float(timeout), 15.0))

    async def command(self, name: str, *, json_response: bool = True) -> Any:
        if not re.fullmatch(r"[A-Za-z0-9_:,./?=&%+ -]{1,512}", name):
            raise ValueError("Comando WiiM non valido")
        async with httpx.AsyncClient(verify=False, timeout=self.timeout, transport=self._transport) as client:
            response = await client.get(f"https://{self.host}/httpapi.asp", params={"command": name})
            response.raise_for_status()
            if not json_response:
                return response.text.strip()
            try:
                return response.json()
            except ValueError as exc:
                raise RuntimeError("Risposta WiiM non valida") from exc

    async def player_action(self, action: str, value: int | None = None) -> str:
        commands = {
            "play": "setPlayerCmd:play",
            "pause": "setPlayerCmd:pause",
            "stop": "setPlayerCmd:stop",
            "next": "setPlayerCmd:next",
            "previous": "setPlayerCmd:prev",
            "mute": "setPlayerCmd:mute:1",
            "unmute": "setPlayerCmd:mute:0",
        }
        if action == "volume":
            if value is None or not 0 <= int(value) <= 100:
                raise ValueError("Volume WiiM non valido")
            command = f"setPlayerCmd:vol:{int(value)}"
        else:
            command = commands.get(action, "")
        if not command:
            raise ValueError("Azione WiiM non valida")
        return str(await self.command(command, json_response=False))

    async def presets(self) -> list[dict[str, Any]]:
        payload = await self.command("getPresetInfo")
        entries = payload.get("preset_list", payload.get("presets", [])) if isinstance(payload, dict) else []
        if not isinstance(entries, list):
            return []
        result = []
        for position, item in enumerate(entries, 1):
            if not isinstance(item, dict):
                continue
            index = int(item.get("number") or item.get("preset_num") or item.get("index") or position)
            result.append({"index": index, "name": decode_linkplay_text(item.get("name") or item.get("title") or f"Preset {index}"), "artwork": public_artwork(item.get("picurl") or item.get("artwork"))})
        return result

    async def play_preset(self, index: int) -> str:
        if not 1 <= int(index) <= 12:
            raise ValueError("Preset WiiM non valido")
        return str(await self.command(f"MCUKeyShortClick:{int(index)}", json_response=False))

    async def snapshot(self) -> dict[str, Any]:
        status, player, metadata = await asyncio.gather(
            self.command("getStatusEx"), self.command("getPlayerStatus"), self.command("getMetaInfo")
        )
        status = status if isinstance(status, dict) else {}
        player = player if isinstance(player, dict) else {}
        metadata = metadata.get("metaData", {}) if isinstance(metadata, dict) else {}
        metadata = metadata if isinstance(metadata, dict) else {}
        duration_ms = int(player.get("totlen") or 0) if str(player.get("totlen") or "0").isdigit() else 0
        position_ms = int(player.get("curpos") or 0) if str(player.get("curpos") or "0").isdigit() else 0
        return {
            "id": str(status.get("uuid") or ""),
            "name": str(status.get("DeviceName") or status.get("GroupName") or "WiiM"),
            "model": str(status.get("project") or "WiiM"),
            "firmware": str(status.get("firmware") or ""),
            "state": {"play": "playing", "pause": "paused", "stop": "idle"}.get(str(player.get("status") or "").lower(), str(player.get("status") or "unknown")),
            "source": str(player.get("vendor") or player.get("mode") or ""),
            "title": decode_linkplay_text(metadata.get("title") or player.get("Title")),
            "artist": decode_linkplay_text(metadata.get("artist") or player.get("Artist")),
            "album": decode_linkplay_text(metadata.get("album") or player.get("Album")),
            "artwork": public_artwork(metadata.get("albumArtURI")),
            "track_id": str(metadata.get("trackId") or ""),
            "duration": duration_ms / 1000,
            "position": position_ms / 1000,
            "volume": int(player.get("vol") or 0) if str(player.get("vol") or "0").isdigit() else 0,
            "muted": str(player.get("mute") or "0") == "1",
            "loop": str(player.get("loop") or ""),
            "sample_rate": str(metadata.get("sampleRate") or ""),
            "bit_depth": str(metadata.get("bitDepth") or ""),
            "bit_rate": str(metadata.get("bitRate") or ""),
        }
