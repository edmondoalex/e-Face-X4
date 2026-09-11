from __future__ import annotations

import asyncio
import base64
import hashlib
from typing import Any, AsyncIterator

import httpx

from pyControl4.room import C4Room
from pyControl4.websocket import C4Websocket

from ..control4 import control4_director
from .base import Connector

ROOM_VARIABLES = ("POWER_STATE", "CURRENT_VOLUME", "IS_MUTED", "CURRENT_SELECTED_DEVICE", "CURRENT_AUDIO_DEVICE", "CURRENT_VIDEO_DEVICE", "CURRENT_VOLUME_DEVICE_ID", "PLAYING_AUDIO_DEVICE", "CURRENT MEDIA INFO")
_artwork_urls: dict[str, tuple[str, str]] = {}
_ARTWORK_HOSTS = ("i.scdn.co", "mosaic.scdn.co", "spotifycdn.com", "mzstatic.com", "media-amazon.com", "tunein.com")


class Control4MediaConnector(Connector):
    id = "control4"
    label = "Control4 Director"

    def __init__(self, config: dict[str, str]) -> None:
        self.config = config
        self._event_ids: set[int] = set()

    async def snapshot(self) -> dict[str, Any]:
        try:
            director, _ = await control4_director(self.config)
            ui, all_items, variables = await asyncio.gather(
                director.get_ui_configuration(), director.get_all_item_info(),
                director.get_all_item_variable_value(ROOM_VARIABLES),
            )
            items = normalize_control4_media(ui, all_items, variables)
            room_ids = {int(str(item["registry_id"]).removeprefix("c4room:")) for item in items}
            related = {
                int(item.get("value")) for item in variables
                if isinstance(item, dict) and str(item.get("id")) in {str(value) for value in room_ids}
                and item.get("varName") in {"CURRENT_AUDIO_DEVICE", "CURRENT_VIDEO_DEVICE", "CURRENT_VOLUME_DEVICE_ID", "PLAYING_AUDIO_DEVICE"}
                and str(item.get("value") or "0").isdigit() and int(item.get("value") or 0) > 0
            }
            self._event_ids = room_ids | related
            return {"id": self.id, "label": self.label, "status": "online", "connection_status": "online", "items": items, "groups": [], "rooms": [item["room"] for item in items]}
        except Exception as exc:
            return {"id": self.id, "label": self.label, "status": "offline", "reason": f"{type(exc).__name__}", "items": [], "groups": [], "rooms": []}

    async def command(self, registry_id: str, operation: str, value: Any = None) -> dict[str, Any]:
        room_id = int(registry_id.removeprefix("c4room:"))
        director, _ = await control4_director(self.config)
        room = C4Room(director, room_id)
        if operation == "media_play": await room.set_play()
        elif operation == "media_pause": await room.set_pause()
        elif operation == "media_stop": await room.set_stop()
        elif operation == "media_previous": await director.send_post_request(f"/api/v1/items/{room_id}/commands", "SKIP_REV", {})
        elif operation == "media_next": await director.send_post_request(f"/api/v1/items/{room_id}/commands", "SKIP_FWD", {})
        elif operation == "volume_mute": await room.set_mute_on()
        elif operation == "volume_unmute": await room.set_mute_off()
        elif operation == "set_volume": await room.set_volume(max(0, min(100, int(value))))
        elif operation == "turn_off": await room.set_room_off()
        elif operation == "select_source":
            experience, source_id = str(value).split(":", 1)
            if experience == "watch": await room.set_video_and_audio_source(int(source_id))
            elif experience == "listen": await room.set_audio_source(int(source_id))
            else: raise ValueError("Sorgente Control4 non valida")
        else: raise ValueError("Comando Control4 non supportato")
        return {"status": "success", "operation": operation, "registry_id": registry_id}

    async def artwork(self, registry_id: str, fingerprint: str, if_none_match: str | None = None) -> httpx.Response:
        cached = _artwork_urls.get(registry_id)
        if not cached or cached[0] != fingerprint:
            return httpx.Response(404)
        url = httpx.URL(cached[1])
        host = (url.host or "").lower()
        if url.scheme != "https" or not any(host == allowed or host.endswith(f".{allowed}") for allowed in _ARTWORK_HOSTS):
            return httpx.Response(415)
        headers = {"If-None-Match": if_none_match} if if_none_match else {}
        async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
            return await client.get(url, headers=headers)

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        snapshot = await self.snapshot()
        event_ids = self._event_ids or {int(str(item["registry_id"]).removeprefix("c4room:")) for item in snapshot.get("items", [])}
        _, token = await control4_director(self.config)
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
        websocket = C4Websocket(self.config["host"])

        async def changed(room_id: int, message: Any) -> None:
            if queue.full():
                queue.get_nowait()
            await queue.put({"type": "control4.media_updated", "data": {"room_id": room_id}})

        for item_id in event_ids:
            websocket.add_item_callback(item_id, changed)
        await websocket.sio_connect(token)
        try:
            while True:
                yield await queue.get()
        finally:
            await websocket.sio_disconnect()


def normalize_control4_media(ui: Any, all_items: Any, variables: Any) -> list[dict[str, Any]]:
    experiences = ui.get("experiences", []) if isinstance(ui, dict) else []
    if isinstance(experiences, dict): experiences = experiences.get("experience", [])
    names = {str(item.get("id")): str(item.get("name")) for item in (all_items if isinstance(all_items, list) else []) if isinstance(item, dict) and item.get("id") is not None and item.get("name")}
    state: dict[str, dict[str, Any]] = {}
    for item in variables if isinstance(variables, list) else []:
        if isinstance(item, dict): state.setdefault(str(item.get("id")), {})[str(item.get("varName"))] = item.get("value")
    rooms: dict[str, dict[str, Any]] = {}
    for experience in experiences if isinstance(experiences, list) else []:
        if not isinstance(experience, dict) or experience.get("type") not in {"watch", "listen"}: continue
        room_id = str(experience.get("room_id"))
        if room_id == "None": continue
        room = rooms.setdefault(room_id, {"experiences": [], "source_options": []})
        room["experiences"].append(str(experience["type"]))
        raw = experience.get("sources", {})
        sources = raw.get("source", []) if isinstance(raw, dict) else []
        if isinstance(sources, dict): sources = [sources]
        for source in sources if isinstance(sources, list) else []:
            if not isinstance(source, dict) or source.get("id") is None: continue
            label = source.get("name") or names.get(str(source.get("id")))
            if label:
                room["source_options"].append({"key": f"{experience['type']}:{source['id']}", "label": str(label), "experience": str(experience["type"]), "type": str(source.get("type") or "")})
    result = []
    for room_id, data in rooms.items():
        values = state.get(room_id, {})
        volume = values.get("CURRENT_VOLUME")
        volume = int(volume) if isinstance(volume, (int, float, str)) and str(volume).lstrip("-").isdigit() and int(volume) >= 0 else None
        selected = {str(values.get("CURRENT_AUDIO_DEVICE")), str(values.get("CURRENT_VIDEO_DEVICE")), str(values.get("CURRENT_SELECTED_DEVICE"))}
        active_source = next((source["label"] for source in data["source_options"] if source["key"].split(":", 1)[1] in selected), None)
        media = values.get("CURRENT MEDIA INFO")
        media = media.get("mediainfo", {}) if isinstance(media, dict) else {}
        media = media if isinstance(media, dict) else {}
        artwork_url = _decode_artwork_url(media.get("img"))
        fingerprint = hashlib.sha256(artwork_url.encode()).hexdigest() if artwork_url else None
        registry_id = f"c4room:{room_id}"
        if artwork_url and fingerprint:
            _artwork_urls[registry_id] = (fingerprint, artwork_url)
        else:
            _artwork_urls.pop(registry_id, None)
        powered = str(values.get("POWER_STATE")) in {"1", "True", "true"}
        stream_status = str(media.get("streamStatus") or "").lower()
        playback_state = "playing" if "playing" in stream_status else "paused" if "pause" in stream_status else "idle" if any(value in stream_status for value in ("stop", "idle")) else "playing"
        state_name = playback_state if powered else "off"
        name = names.get(room_id, f"Room {room_id}")
        icon = "mdi:television-speaker" if "watch" in data["experiences"] else "mdi:speaker"
        result.append({"id": f"c4media:{room_id}", "registry_id": registry_id, "entity_id": f"control4.room.{room_id}", "provider": "control4", "kind": "media_player", "icon": icon, "name": name, "room": name, "state": state_name, "availability": "available", "connection_status": "online", "volume": volume, "muted": str(values.get("IS_MUTED")) in {"1", "True", "true"}, "source": str(media.get("meta", {}).get("audioFormat") or active_source or "") if isinstance(media.get("meta"), dict) else active_source, "title": media.get("title"), "artist": media.get("artist"), "album": media.get("album"), "content_fingerprint": fingerprint, "source_options": data["source_options"], "source_list": [source["label"] for source in data["source_options"]], "experiences": data["experiences"], "capabilities": {"play": True, "pause": True, "stop": True, "previous": True, "next": True, "turn_off": True, "set_volume": volume is not None, "mute": True, "select_source": bool(data["source_options"]), "grouping": False, "artwork": bool(fingerprint)}})
    return result


def _decode_artwork_url(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096:
        return ""
    try:
        decoded = base64.b64decode(value, validate=True).decode("utf-8")
        url = httpx.URL(decoded)
        return decoded if url.scheme == "https" and url.host else ""
    except (ValueError, UnicodeError):
        return ""
