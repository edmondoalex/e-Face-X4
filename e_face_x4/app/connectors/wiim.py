from __future__ import annotations

import asyncio
import html
import ipaddress
import json
import re
import xml.etree.ElementTree as ET
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
        if not re.fullmatch(r"[A-Za-z0-9_:,./?=&%+ -]{1,4608}", name):
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
        elif action == "seek":
            if value is None or not 0 <= int(value) <= 86_400:
                raise ValueError("Posizione WiiM non valida")
            command = f"setPlayerCmd:seek:{int(value)}"
        elif action == "loop":
            if value is None or int(value) not in {-1, 0, 1, 2, 3, 4, 5}:
                raise ValueError("Modalità ripetizione WiiM non valida")
            command = f"setPlayerCmd:loopmode:{int(value)}"
        else:
            command = commands.get(action, "")
        if not command:
            raise ValueError("Azione WiiM non valida")
        return str(await self.command(command, json_response=False))

    async def _eq_json_command(self, action: str, payload: dict[str, Any]) -> Any:
        allowed = {"EQGetLV2SourceBandEx", "EQSetLV2SourceBand", "EQChangeSourceFX", "EQSourceOff", "EQv2SourceLoad", "EQSourceSave"}
        if action not in allowed:
            raise ValueError("Azione EQ WiiM non valida")
        value = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        async with httpx.AsyncClient(verify=False, timeout=self.timeout, transport=self._transport) as client:
            response = await client.get(f"https://{self.host}/httpapi.asp", params={"command": f"{action}:{value}"})
            response.raise_for_status()
            try: return response.json()
            except ValueError: return response.text.strip()

    async def eq_state(self, source: str = "wifi") -> dict[str, Any]:
        if source not in {"wifi", "bluetooth", "line-in", "optical"}:
            raise ValueError("Sorgente EQ WiiM non valida")
        plugin = "http://moddevices.com/plugins/caps/Eq10HP"
        state, presets = await asyncio.gather(
            self._eq_json_command("EQGetLV2SourceBandEx", {"source_name": source, "pluginURI": plugin}),
            self.command(f"EQv2GetList:{plugin}"),
        )
        if not isinstance(state, dict) or state.get("status") != "OK": raise RuntimeError("EQ WiiM non disponibile")
        lists = presets if isinstance(presets, dict) else {}
        return {"source": source, "enabled": str(state.get("EQStat") or "").lower() == "on", "name": str(state.get("Name") or "Custom"), "channel_mode": str(state.get("channelMode") or "Stereo"), "bands": state.get("EQBand") or [], "presets": list(lists.get("preset") or []) + list(lists.get("custom") or [])}

    async def set_eq(self, source: str, action: str, *, name: str = "", bands: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if source not in {"wifi", "bluetooth", "line-in", "optical"}: raise ValueError("Sorgente EQ WiiM non valida")
        plugin = "http://moddevices.com/plugins/caps/Eq10HP"
        base = {"source_name": source, "pluginURI": plugin}
        if action == "enable": await self._eq_json_command("EQChangeSourceFX", base)
        elif action == "disable": await self._eq_json_command("EQSourceOff", base)
        elif action == "preset":
            if not name or len(name) > 80: raise ValueError("Preset EQ WiiM non valido")
            await self._eq_json_command("EQv2SourceLoad", {**base, "Name": name})
        elif action in {"bands", "save"}:
            if not isinstance(bands, list) or len(bands) != 10: raise ValueError("Bande EQ WiiM non valide")
            clean = []
            for index, band in enumerate(bands):
                value = round(float(band.get("value")), 1)
                if not -12 <= value <= 12: raise ValueError("Valore banda EQ fuori intervallo")
                clean.append({"index": index, "param_name": str(band.get("param_name") or "")[:30], "value": value})
            await self._eq_json_command("EQSetLV2SourceBand", {**base, "channelMode": "Stereo", "EQBand": clean})
            if action == "save":
                name = str(name).strip()
                if not 1 <= len(name) <= 40: raise ValueError("Inserisci un nome per il preset custom")
                await self._eq_json_command("EQSourceSave", {**base, "Name": name})
        else: raise ValueError("Azione EQ WiiM non valida")
        return await self.eq_state(source)

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
            result.append({"index": index, "name": decode_linkplay_text(item.get("name") or item.get("title") or f"Preset {index}"), "source": str(item.get("source") or ""), "artwork": public_artwork(item.get("picurl") or item.get("artwork"))})
        return result

    async def play_preset(self, index: int) -> str:
        if not 1 <= int(index) <= 12:
            raise ValueError("Preset WiiM non valido")
        return str(await self.command(f"MCUKeyShortClick:{int(index)}", json_response=False))

    async def play_url(self, url: str) -> str:
        value = str(url).strip()
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or len(value) > 4096:
            raise ValueError("URL audio non valido")
        # Signed media URLs contain characters (~, _, signatures) intentionally
        # excluded from the generic command grammar. The URL is validated above
        # and passed as an encoded query parameter by httpx.
        async with httpx.AsyncClient(verify=False, timeout=self.timeout, transport=self._transport) as client:
            response = await client.get(
                f"https://{self.host}/httpapi.asp",
                params={"command": f"setPlayerCmd:play:{value}"},
            )
            response.raise_for_status()
            return response.text.strip()

    async def _playqueue(self, action: str, arguments: dict[str, Any]) -> str:
        if action not in {"CreateQueue", "ReplaceQueue", "BrowseQueue", "BrowseQueueEx", "PlayQueueWithIndex", "GetKeyMapping", "SetKeyMapping"}:
            raise ValueError("Azione coda WiiM non valida")
        service = "urn:schemas-wiimu-com:service:PlayQueue:1"
        values = "".join(f"<{key}>{html.escape(str(value))}</{key}>" for key, value in arguments.items())
        envelope = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
            f'<u:{action} xmlns:u="{service}">{values}</u:{action}>'
            '</s:Body></s:Envelope>'
        )
        async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as client:
            response = await client.post(
                f"http://{self.host}:49152/upnp/control/PlayQueue1",
                content=envelope.encode("utf-8"),
                headers={"Content-Type": 'text/xml; charset="utf-8"', "SOAPAction": f'"{service}#{action}"'},
            )
            response.raise_for_status()
        if action in {"CreateQueue", "ReplaceQueue", "PlayQueueWithIndex", "SetKeyMapping"}:
            return ""
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise RuntimeError("Risposta coda WiiM non valida") from exc
        node = next((item for item in root.iter() if item.tag.rsplit("}", 1)[-1] == "QueueContext"), None)
        return html.unescape(node.text or "") if node is not None else ""

    @staticmethod
    def _queue_value(block: str, name: str) -> str:
        match = re.search(fr"<{re.escape(name)}(?:\s[^>]*)?>(.*?)</{re.escape(name)}>", block, re.I | re.S)
        return html.unescape(match.group(1)).strip() if match else ""

    async def queue(self, *, start: int = 0, limit: int = 250) -> dict[str, Any]:
        start = max(0, int(start))
        limit = max(1, min(int(limit), 250))
        context = await self._playqueue("BrowseQueueEx", {"QueueName": "0", "TrackIndex": start, "TrackNums": limit})
        queue_name = self._queue_value(context, "ListName").strip()
        list_name = queue_name.split("_#~", 1)[0].strip()
        tracks = []
        for match in re.finditer(r"<Track(\d+)>(.*?)</Track\1>", context, re.I | re.S):
            block = match.group(2)
            metadata = self._queue_value(block, "Metadata")
            tracks.append({
                "index": int(match.group(1)),
                "track_id": self._queue_value(block, "Id"),
                "url": self._queue_value(block, "URL"),
                "title": self._queue_value(metadata, "dc:title"),
                "artist": self._queue_value(metadata, "upnp:artist"),
                "album": self._queue_value(metadata, "upnp:album"),
                "artwork": public_artwork(self._queue_value(metadata, "upnp:albumArtURI")),
                "source": self._queue_value(block, "Source"),
            })
        return {"name": list_name, "queue_name": queue_name, "total": int(self._queue_value(context, "TotalNumber") or len(tracks)), "tracks": tracks}

    async def play_queue_index(self, index: int, queue_name: str = "0") -> None:
        if not 1 <= int(index) <= 10_001:
            raise ValueError("Indice coda WiiM non valido")
        queue_name = str(queue_name or "0").strip()
        if len(queue_name) > 500:
            raise ValueError("Nome coda WiiM non valido")
        # This WiiM firmware expects the same one-based position exposed by
        # BrowseQueueEx (Track1, Track2, ...).
        await self._playqueue("PlayQueueWithIndex", {"QueueName": queue_name, "Index": int(index)})

    async def create_queue(self, context: str, queue_name: str) -> None:
        await self.load_queue(context)
        await self.play_queue_index(1, queue_name)
        await self.player_action("play")

    async def load_queue(self, context: str) -> None:
        """Load a queue without changing the current transport state."""
        if not context.startswith("<?xml") or len(context) > 1_000_000:
            raise ValueError("Coda WiiM non valida")
        await self._playqueue("CreateQueue", {"QueueContext": context})

    async def delete_preset(self, index: int) -> None:
        index = int(index)
        if not 1 <= index <= 33:
            raise ValueError("Preset WiiM non valido")
        context = await self._playqueue("GetKeyMapping", {})
        pattern = re.compile(fr"<Key{index}>.*?</Key{index}>", re.I | re.S)
        match = pattern.search(context)
        if not match or not self._queue_value(match.group(0), "Name"):
            raise ValueError("Preset WiiM non disponibile")
        updated = pattern.sub(f"<Key{index}><RoutineId>Empty</RoutineId></Key{index}>", context, count=1)
        await self._playqueue("SetKeyMapping", {"QueueContext": updated})
        remaining = await self.presets()
        if any(int(item["index"]) == index for item in remaining):
            raise RuntimeError("Il WiiM non ha confermato la cancellazione del preset")

    async def multiroom(self) -> dict[str, Any]:
        status, topology = await asyncio.gather(self.command("getStatusEx"), self.command("multiroom:getSlaveList"))
        status = status if isinstance(status, dict) else {}
        topology = topology if isinstance(topology, dict) else {}
        raw_members = topology.get("slave_list") or topology.get("slaves_list") or []
        members = []
        if isinstance(raw_members, list):
            for item in raw_members:
                if isinstance(item, dict):
                    members.append({"name": str(item.get("name") or item.get("DeviceName") or "WiiM"), "ip": str(item.get("ip") or item.get("IP") or "")})
        member_count = int(topology.get("slaves") or len(members) or 0)
        return {"grouped": str(status.get("group") or "0") != "0" or member_count > 0, "role": "master" if member_count > 0 else "standalone", "group_name": str(status.get("GroupName") or status.get("DeviceName") or "WiiM"), "members": members, "member_count": member_count, "protocol_version": str(topology.get("wmrm_version") or ""), "group_type": str(topology.get("group_type") or "")}

    async def snapshot(self) -> dict[str, Any]:
        status, player, metadata = await asyncio.gather(
            self.command("getStatusEx"), self.command("getPlayerStatus"), self.command("getMetaInfo"),
            return_exceptions=True,
        )
        if isinstance(status, BaseException): raise status
        if isinstance(player, BaseException): raise player
        # Idle WiiM firmware returns plain text "Failed" for getMetaInfo even
        # while status and player endpoints are healthy.
        if isinstance(metadata, BaseException): metadata = {}
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
