from __future__ import annotations

import asyncio
import base64
import hashlib
import ipaddress
import json
import re
import socket
from typing import Any, AsyncIterator

import httpx

from pyControl4.room import C4Room
from pyControl4.websocket import C4Websocket

from ..control4 import control4_director
from .base import Connector

ROOM_VARIABLES = ("POWER_STATE", "CURRENT_VOLUME", "IS_MUTED", "CURRENT_SELECTED_DEVICE", "CURRENT_AUDIO_DEVICE", "CURRENT_VIDEO_DEVICE", "CURRENT_VOLUME_DEVICE_ID", "PLAYING_AUDIO_DEVICE", "CURRENT MEDIA INFO", "QUEUE_STATUS_V2")
_artwork_urls: dict[str, tuple[str, str]] = {}
_source_icon_paths: dict[int, str] = {}
_source_icon_content: dict[int, tuple[str, bytes]] = {}
_source_labels: dict[int, str] = {}
_source_remote_actions: dict[int, set[str]] = {}
_source_custom_buttons: dict[int, tuple[int, set[str]]] = {}
_ARTWORK_HOSTS = ("i.scdn.co", "mosaic.scdn.co", "spotifycdn.com", "mzstatic.com", "media-amazon.com", "tunein.com", "sonosradio.imgix.net")


def _trusted_artwork_url(url: httpx.URL, controller_host: str, extra_hosts: str = "") -> bool:
    if url.scheme not in {"http", "https"} or url.username or url.password:
        return False
    host = (url.host or "").lower()
    if any(host == allowed or host.endswith(f".{allowed}") for allowed in _ARTWORK_HOSTS):
        return True
    # Local media servers often publish artwork on an application-specific high port.
    # Keep privileged ports blocked; never fetch from the Director itself.
    if url.port is not None and url.port not in {80, 443} and url.port < 1024:
        return False
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and literal.is_global:
        return True
    if literal is None:
        if not re.fullmatch(r"(?=.{1,253}$)[a-z0-9][a-z0-9.-]*[a-z0-9]", host) or "." not in host or host.endswith((".local", ".internal", ".localhost")):
            return False
        try:
            addresses = {ipaddress.ip_address(entry[4][0]) for entry in socket.getaddrinfo(host, url.port or (443 if url.scheme == "https" else 80), type=socket.SOCK_STREAM)}
        except (OSError, ValueError):
            return False
        return bool(addresses) and all(address.is_global for address in addresses)
    if host in {item.strip() for item in extra_hosts.split(",") if item.strip()}:
        try:
            target = ipaddress.ip_address(host)
            controller = ipaddress.ip_address(controller_host)
        except ValueError:
            return False
        return target.is_private and target != controller and not (target.is_loopback or target.is_multicast or target.is_unspecified)
    try:
        controller = ipaddress.ip_address(controller_host)
        target = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        isinstance(controller, ipaddress.IPv4Address)
        and isinstance(target, ipaddress.IPv4Address)
        and controller.is_private
        and target in ipaddress.ip_network(f"{controller}/24", strict=False)
        and target != controller
        and not target.is_loopback
        and not target.is_multicast
        and not target.is_unspecified
    )

REMOTE_COMMANDS = {
    "play": (2, "PLAY"), "stop": (3, "STOP"), "pause": (4, "PAUSE"), "skip_fwd": (5, "SKIP_FWD"), "skip_rev": (6, "SKIP_REV"),
    "scan_fwd": (7, "SCAN_FWD"), "scan_rev": (8, "SCAN_REV"), "menu": (9, "MENU"), "up": (10, "UP"), "down": (11, "DOWN"),
    "left": (12, "LEFT"), "right": (13, "RIGHT"), "enter": (14, "ENTER"), "channel_up": (20, "PULSE_CHANNEL_UP"),
    "channel_down": (21, "PULSE_CHANNEL_DOWN"), "record": (22, "RECORD"), "page_up": (23, "PAGE_UP"), "page_down": (24, "PAGE_DOWN"),
    "input": (25, "PULSE_INPUT"), "info": (26, "INFO"), "cancel": (27, "CANCEL"), "recall": (28, "RECALL"), "dvr": (29, "PVR"),
    "guide": (30, "GUIDE"), "digit_0": (31, "NUMBER_0"), "digit_1": (32, "NUMBER_1"), "digit_2": (33, "NUMBER_2"),
    "digit_3": (34, "NUMBER_3"), "digit_4": (35, "NUMBER_4"), "digit_5": (36, "NUMBER_5"), "digit_6": (37, "NUMBER_6"),
    "digit_7": (38, "NUMBER_7"), "digit_8": (39, "NUMBER_8"), "digit_9": (40, "NUMBER_9"), "dash": (41, "DASH"),
    "star": (42, "STAR"), "pound": (43, "POUND"),
}


class Control4MediaConnector(Connector):
    id = "control4"
    label = "Control4 Director"

    def __init__(self, config: dict[str, str]) -> None:
        self.config = config
        self._event_ids: set[int] = set()

    async def snapshot(self) -> dict[str, Any]:
        try:
            director, _ = await control4_director(self.config)
            ui, all_items, variables, queue_value = await asyncio.gather(
                director.get_ui_configuration(), director.get_all_item_info(),
                director.get_all_item_variable_value(ROOM_VARIABLES),
                director.get_item_variable_value(100002, "QUEUE_STATUS_V2"),
            )
            if not isinstance(variables, list):
                variables = []
            if control4_queues(queue_value):
                variables.append({"id": 100002, "varName": "QUEUE_STATUS_V2", "value": queue_value})
            items = normalize_control4_media(ui, all_items, variables)
            try:
                await cache_control4_source_icons(director)
            except Exception:
                # Icon metadata is optional and must never take the media connector offline.
                pass
            groups = normalize_control4_groups(items, variables)
            room_ids = {int(str(item["registry_id"]).removeprefix("c4room:")) for item in items}
            related = {
                int(item.get("value")) for item in variables
                if isinstance(item, dict) and str(item.get("id")) in {str(value) for value in room_ids}
                and item.get("varName") in {"CURRENT_AUDIO_DEVICE", "CURRENT_VIDEO_DEVICE", "CURRENT_VOLUME_DEVICE_ID", "PLAYING_AUDIO_DEVICE"}
                and str(item.get("value") or "0").isdigit() and int(item.get("value") or 0) > 0
            }
            self._event_ids = room_ids | related
            return {"id": self.id, "label": self.label, "status": "online", "connection_status": "online", "items": items, "groups": groups, "rooms": [item["room"] for item in items]}
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
        elif operation == "media_join":
            members = value if isinstance(value, list) else []
            requested = [str(item) for item in members]
            snapshot = await self.snapshot()
            valid = {str(item.get("registry_id")) for item in snapshot.get("items", []) if "listen" in (item.get("experiences") or [])}
            if not requested or len(requested) > 63 or len(set(requested)) != len(requested) or any(item not in valid or item == registry_id for item in requested):
                raise ValueError("Stanze Control4 da aggiungere non valide")
            group = next((item for item in snapshot.get("groups", []) if registry_id in item.get("member_registry_ids", [])), None)
            owner_id = str(group.get("owner_registry_id")) if group else registry_id
            owner_room_id = int(owner_id.removeprefix("c4room:"))
            room_list = ",".join(item.removeprefix("c4room:") for item in requested)
            await director.send_post_request("/api/v1/items/100002/commands", "ADD_ROOMS_TO_SESSION", {"ROOM_ID": owner_room_id, "ROOM_ID_LIST": room_list})
        elif operation == "media_unjoin":
            queue_value = await director.get_item_variable_value(100002, "QUEUE_STATUS_V2")
            queue = next((item for item in control4_queues(queue_value) if room_id in control4_queue_rooms(item)), None)
            if not queue:
                raise ValueError("La stanza non appartiene a una sessione Control4")
            owner = int(queue.get("owner") or room_id)
            if owner == room_id:
                raise ValueError("La stanza principale non può essere rimossa dalla propria sessione")
            await director.send_post_request("/api/v1/items/100002/commands", "REMOVE_ROOMS_FROM_SESSION", {"ROOM_ID": owner, "ROOM_ID_LIST": str(room_id)})
        elif operation == "select_source":
            experience, source_id = str(value).split(":", 1)
            if experience == "watch": await room.set_video_and_audio_source(int(source_id))
            elif experience == "listen": await room.set_audio_source(int(source_id))
            else: raise ValueError("Sorgente Control4 non valida")
        elif operation == "video_remote":
            if not isinstance(value, dict):
                raise ValueError("Comando telecomando non valido")
            source_id = int(value.get("source_id") or 0)
            action = str(value.get("command") or "")
            snapshot = await self.snapshot()
            player = next((item for item in snapshot.get("items", []) if item.get("registry_id") == registry_id), None)
            if not player or player.get("active_experience") != "watch" or int(player.get("active_source_id") or 0) != source_id:
                raise ValueError("La sorgente video non è attiva in questa stanza")
            if action in REMOTE_COMMANDS and action in _source_remote_actions.get(source_id, set()):
                await director.send_post_request(f"/api/v1/items/{source_id}/commands", REMOTE_COMMANDS[action][1], {})
            elif action.startswith("custom:"):
                button = action.split(":", 1)[1]
                protocol_id, allowed = _source_custom_buttons.get(source_id, (0, set()))
                if not protocol_id or button not in allowed:
                    raise ValueError("Pulsante non supportato dall'apparato")
                await director.send_post_request(f"/api/v1/items/{protocol_id}/commands", "Press Button", {"Button": button})
            else:
                raise ValueError("Comando non supportato dall'apparato")
        else: raise ValueError("Comando Control4 non supportato")
        return {"status": "success", "operation": operation, "registry_id": registry_id}

    async def group_volume(self, group_id: str, target: int) -> dict[str, Any]:
        snapshot = await self.snapshot()
        group = next((item for item in snapshot.get("groups", []) if item.get("group_id") == group_id), None)
        if not group:
            raise ValueError("Sessione Control4 non disponibile")
        players = {item["registry_id"]: item for item in snapshot.get("items", [])}
        members = [players[item] for item in group["member_registry_ids"] if item in players and isinstance(players[item].get("volume"), int)]
        if not members:
            raise ValueError("Volume della sessione non disponibile")
        target = max(0, min(100, int(target)))
        reference = next((item for item in members if item["registry_id"] == group.get("owner_registry_id")), members[0])
        delta = target - reference["volume"]
        director, _ = await control4_director(self.config)
        results = []
        for item in members:
            level = max(0, min(100, item["volume"] + delta))
            try:
                await C4Room(director, int(item["registry_id"].removeprefix("c4room:"))).set_volume(level)
                results.append({"registry_id": item["registry_id"], "status": "success", "volume": level})
            except Exception:
                results.append({"registry_id": item["registry_id"], "status": "failed"})
        return {"status": "success" if all(item["status"] == "success" for item in results) else "partial", "members": results}

    async def recently_played(self, room_ids: list[int], limit: int = 20) -> list[dict[str, Any]]:
        if not room_ids:
            return []
        director, _ = await control4_director(self.config)
        raw = await director.send_post_request(
            "/api/v1/items/12/commands", "GetHistoryItemsByRooms",
            {"rooms": ",".join(str(room_id) for room_id in room_ids), "limit": max(1, min(20, int(limit)))}, False,
        )
        envelope = json.loads(raw)
        encoded = str(envelope.get("b64json") or "")
        if not encoded:
            return []
        decoded = json.loads(base64.b64decode(encoded).decode("utf-8"))
        result: list[dict[str, Any]] = []
        for entry in decoded if isinstance(decoded, list) else []:
            if not isinstance(entry, dict):
                continue
            info = entry.get("info") if isinstance(entry.get("info"), dict) else {}
            container = info.get("container") if isinstance(info.get("container"), dict) else {}
            key = str(entry.get("key") or "")
            image_url = _decode_artwork_url(container.get("image"))
            fingerprint = hashlib.sha256(image_url.encode()).hexdigest() if image_url else None
            registry_id = f"c4recent:{hashlib.sha256(key.encode()).hexdigest()[:24]}"
            if image_url and fingerprint:
                _artwork_urls[registry_id] = (fingerprint, image_url)
            result.append({
                "key": key, "driver_id": int(entry.get("driverId") or info.get("driverId") or 0),
                "room_ids": [int(value) for value in re.findall(r"\d+", str(entry.get("roomIds") or ""))],
                "timestamp": int(entry.get("timestamp") or 0), "title": str(container.get("title") or ""),
                "subtitle": str(container.get("subtitle") or ""), "item_type": str(container.get("itemType") or ""),
                "registry_id": registry_id, "content_fingerprint": fingerprint,
            })
        return result

    async def select_recent(self, room_id: int, key: str) -> dict[str, Any]:
        if room_id <= 0 or not key or len(key) > 256:
            raise ValueError("Elemento recente Control4 non valido")
        director, _ = await control4_director(self.config)
        await director.send_post_request(
            "/api/v1/items/12/commands", "SelectHistoryItem",
            {"rooms": str(room_id), "key": key}, False,
        )
        return {"status": "success", "room_id": room_id}


    async def artwork(self, registry_id: str, fingerprint: str, if_none_match: str | None = None) -> httpx.Response:
        cached = _artwork_urls.get(registry_id)
        if not cached or cached[0] != fingerprint:
            return httpx.Response(404)
        url = httpx.URL(cached[1])
        director_alias = (url.host or "").lower() == "director"
        if director_alias:
            if url.scheme != "http" or url.port not in {None, 80} or url.username or url.password:
                return httpx.Response(415)
            try:
                ipaddress.ip_address(str(self.config.get("host") or ""))
            except ValueError:
                return httpx.Response(415)
            url = url.copy_with(host=str(self.config["host"]))
        headers = {"If-None-Match": if_none_match} if if_none_match else {}
        async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
            for hop in range(4):
                if not (director_alias and hop == 0) and not await asyncio.to_thread(_trusted_artwork_url, url, str(self.config.get("host") or ""), str(self.config.get("artwork_hosts") or "")):
                    return httpx.Response(415)
                response = await client.get(url, headers=headers)
                if response.status_code not in {301, 302, 303, 307, 308}:
                    return response
                location = response.headers.get("location")
                if not location:
                    return httpx.Response(502)
                url = url.join(location)
        return httpx.Response(502)

    @staticmethod
    def artwork_host(registry_id: str, fingerprint: str) -> str:
        cached = _artwork_urls.get(registry_id)
        return (httpx.URL(cached[1]).host or "") if cached and cached[0] == fingerprint else ""

    @staticmethod
    def artwork_origin(registry_id: str, fingerprint: str) -> dict[str, Any]:
        cached = _artwork_urls.get(registry_id)
        if not cached or cached[0] != fingerprint:
            return {}
        url = httpx.URL(cached[1])
        return {"scheme": url.scheme, "port": url.port or (443 if url.scheme == "https" else 80)}

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
    item_info = {str(item.get("id")): item for item in (all_items if isinstance(all_items, list) else []) if isinstance(item, dict) and item.get("id") is not None}
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
                source_id = int(source["id"])
                _source_labels[source_id] = str(label)
                icon_path = control4_icon_path(item_info.get(str(source_id)))
                if icon_path:
                    _source_icon_paths[source_id] = icon_path
                remote_actions = control4_remote_actions(item_info.get(str(source_id))) if experience["type"] == "watch" else []
                room["source_options"].append({"key": f"{experience['type']}:{source_id}", "label": str(label), "experience": str(experience["type"]), "type": str(source.get("type") or ""), "source_id": source_id, "icon": control4_source_fallback_icon(item_info.get(str(source_id))), "remote_actions": remote_actions})
    result = []
    for room_id, data in rooms.items():
        values = state.get(room_id, {})
        volume = values.get("CURRENT_VOLUME")
        volume = int(volume) if isinstance(volume, (int, float, str)) and str(volume).lstrip("-").isdigit() and int(volume) >= 0 else None
        selected = {str(values.get("CURRENT_AUDIO_DEVICE")), str(values.get("CURRENT_VIDEO_DEVICE")), str(values.get("CURRENT_SELECTED_DEVICE"))}
        selected_options = [source for source in data["source_options"] if str(source["source_id"]) in selected]
        active_option = next((source for source in selected_options if source["experience"] == "watch"), None) or (selected_options[0] if selected_options else None)
        active_source = active_option["label"] if active_option else None
        active_source_id = active_option["source_id"] if active_option else None
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
        playing_device = values.get("PLAYING_AUDIO_DEVICE")
        audio_device = values.get("CURRENT_AUDIO_DEVICE")
        video_device = values.get("CURRENT_VIDEO_DEVICE")
        playing_source_id = int(playing_device) if str(playing_device or "").isdigit() and int(playing_device) > 0 else None
        selected_source_id = active_source_id
        media_type = str(media.get("mediatypeV2") or media.get("mediatype") or "").upper()
        has_video_session = (
            (str(video_device or "0").isdigit() and int(video_device or 0) > 0)
            or (active_option is not None and active_option.get("experience") == "watch")
            or "VIDEO" in media_type
        )
        has_audio_session = not has_video_session and any(str(value or "0").isdigit() and int(value or 0) > 0 for value in (playing_device, audio_device))
        active_experience = "watch" if has_video_session else "listen" if has_audio_session else None
        display_source = active_source if active_experience == "watch" else (str(media.get("meta", {}).get("audioFormat") or active_source or "") if isinstance(media.get("meta"), dict) else active_source)
        if active_experience == "listen" and selected_source_id == 100002 and playing_source_id:
            playing_option = next((source for source in data["source_options"] if source["source_id"] == playing_source_id and source["experience"] == "listen"), None)
            if playing_option:
                active_source_id = playing_source_id
                display_source = playing_option["label"]
        can_group = "listen" in data["experiences"] and (has_audio_session or has_video_session)
        result.append({"id": f"c4media:{room_id}", "registry_id": registry_id, "entity_id": f"control4.room.{room_id}", "provider": "control4", "kind": "media_player", "icon": icon, "name": name, "room": name, "state": state_name, "availability": "available", "connection_status": "online", "volume": volume, "muted": str(values.get("IS_MUTED")) in {"1", "True", "true"}, "source": display_source, "active_source_id": active_source_id, "selected_source_id": selected_source_id, "playing_source_id": playing_source_id, "title": media.get("title"), "artist": media.get("artist"), "album": media.get("album"), "content_fingerprint": fingerprint, "source_options": data["source_options"], "source_list": [source["label"] for source in data["source_options"]], "experiences": data["experiences"], "active_experience": active_experience, "capabilities": {"play": True, "pause": True, "stop": True, "previous": True, "next": True, "turn_off": True, "set_volume": volume is not None, "mute": True, "select_source": bool(data["source_options"]), "grouping": can_group, "artwork": bool(fingerprint)}})
    return result


def control4_queues(value: Any) -> list[dict[str, Any]]:
    container = value.get("queues") if isinstance(value, dict) else None
    queues = container.get("queue", []) if isinstance(container, dict) else []
    if isinstance(queues, dict):
        queues = [queues]
    return [item for item in queues if isinstance(item, dict)] if isinstance(queues, list) else []


def control4_icon_path(item: Any) -> str | None:
    if isinstance(item, list):
        item = item[0] if item else None
    if not isinstance(item, dict):
        return None
    capabilities = item.get("capabilities")
    display = capabilities.get("navigator_display_option") if isinstance(capabilities, dict) else None
    display_icons = display.get("display_icons") if isinstance(display, dict) else None
    icons = display_icons.get("Icon", []) if isinstance(display_icons, dict) else []
    if isinstance(icons, dict):
        icons = [icons]
    candidates = [icon for icon in icons if isinstance(icon, dict) and isinstance(icon.get("$t"), str)]
    candidates.sort(key=lambda icon: abs(int(icon.get("width") or 0) - 140))
    uri = str(candidates[0].get("$t")) if candidates else ""
    if not re.fullmatch(r"controller://driver/[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+\.(?:png|gif|jpe?g)", uri, re.IGNORECASE):
        return None
    return "/driver/" + uri.removeprefix("controller://driver/")


def cached_control4_icon_path(source_id: int) -> str | None:
    return _source_icon_paths.get(source_id)


def cached_control4_icon(source_id: int) -> tuple[str, bytes] | None:
    return _source_icon_content.get(source_id)


def cached_control4_source_label(source_id: int) -> str | None:
    return _source_labels.get(source_id)


def control4_remote_actions(item: Any) -> list[str]:
    if isinstance(item, list):
        item = item[0] if item else None
    if not isinstance(item, dict):
        return []
    commands = item.get("commands", {}).get("command", []) if isinstance(item.get("commands"), dict) else []
    if isinstance(commands, dict):
        commands = [commands]
    ids = {int(command.get("id")) for command in commands if isinstance(command, dict) and str(command.get("id", "")).isdigit()}
    names = {str(command.get("name") or "").upper() for command in commands if isinstance(command, dict)}
    actions = [action for action, (command_id, command_name) in REMOTE_COMMANDS.items() if command_id in ids or command_name in names]
    source_id = int(item.get("id") or 0)
    if source_id:
        _source_remote_actions[source_id] = set(actions)
        protocol_id = int(item.get("protocolId") or 0)
        if protocol_id and "sky" in str(item.get("protocolFilename") or "").casefold():
            _source_custom_buttons[source_id] = (protocol_id, {"PROGRAM_A", "PROGRAM_B", "PROGRAM_C", "PROGRAM_D"})
            actions.extend(["custom:PROGRAM_A", "custom:PROGRAM_B", "custom:PROGRAM_C", "custom:PROGRAM_D"])
    return actions


def control4_source_fallback_icon(item: Any) -> str:
    if isinstance(item, list):
        item = item[0] if item else None
    if not isinstance(item, dict):
        return "mdi:play-box"
    identity = " ".join(str(item.get(key) or "") for key in ("name", "proxy", "filename", "protocolFilename")).casefold()
    if "xbox" in identity or "game" in identity:
        return "mdi:microsoft-xbox-controller"
    if "apple" in identity:
        return "mdi:apple"
    if "dlna" in identity:
        return "mdi:cast-audio"
    if "pc" in identity or "computer" in identity:
        return "mdi:monitor"
    if "media_service" in identity or " app" in f" {identity}":
        return "mdi:apps"
    if "receiver" in identity or "onkyo" in identity or "integra" in identity:
        return "mdi:audio-video"
    if "tv" in identity or "television" in identity:
        return "mdi:television"
    if "satellite" in identity or "sky" in identity:
        return "mdi:satellite-variant"
    if "media_player" in identity:
        return "mdi:multimedia"
    return "mdi:play-box"


async def cache_control4_source_icons(director: Any) -> None:
    pending = [(source_id, path) for source_id, path in _source_icon_paths.items() if source_id not in _source_icon_content]
    if not pending:
        return
    semaphore = asyncio.Semaphore(6)

    async def download(source_id: int, path: str) -> None:
        async with semaphore:
            try:
                async with httpx.AsyncClient(verify=False, timeout=8, follow_redirects=False) as client:
                    response = await client.get(director.base_url + path, headers=director.headers)
                media_type = response.headers.get("content-type", "").split(";", 1)[0]
                if response.status_code == 200 and media_type in {"image/png", "image/jpeg", "image/gif", "image/webp"} and len(response.content) <= 300_000:
                    _source_icon_content[source_id] = (media_type, response.content)
            except httpx.HTTPError:
                return

    await asyncio.gather(*(download(source_id, path) for source_id, path in pending))


def control4_queue_rooms(queue: dict[str, Any]) -> list[int]:
    values = queue.get("rooms", {}).get("id", []) if isinstance(queue.get("rooms"), dict) else []
    if not isinstance(values, list):
        values = [values]
    return [int(value) for value in values if str(value).isdigit()]


def normalize_control4_groups(items: list[dict[str, Any]], variables: Any) -> list[dict[str, Any]]:
    player_ids = {str(item.get("registry_id")) for item in items}
    queue_value = next((
        item.get("value") for item in (variables if isinstance(variables, list) else [])
        if isinstance(item, dict) and item.get("varName") == "QUEUE_STATUS_V2" and control4_queues(item.get("value"))
    ), None)
    groups = []
    for queue in control4_queues(queue_value):
        members = [f"c4room:{room_id}" for room_id in control4_queue_rooms(queue) if f"c4room:{room_id}" in player_ids]
        if len(members) < 2:
            continue
        owner = f"c4room:{queue.get('owner')}"
        group = {"group_id": f"c4queue:{queue.get('id')}", "name": str(queue.get("name") or "Sessione audio"), "owner_registry_id": owner, "member_registry_ids": members, "completeness": "complete", "resource_revision": int(queue.get("id") or 0)}
        groups.append(group)
        for player in items:
            if player.get("registry_id") in members:
                player["group"] = group
    shared_streams: dict[tuple[int, str, str], list[dict[str, Any]]] = {}
    for player in items:
        if player.get("group") or player.get("active_experience") != "listen":
            continue
        source_id = int(player.get("playing_source_id") or 0)
        fingerprint = str(player.get("content_fingerprint") or "")
        album = str(player.get("album") or "").strip().casefold()
        if source_id > 0 and fingerprint and album:
            shared_streams.setdefault((source_id, fingerprint, album), []).append(player)
    for (source_id, fingerprint, _album), players in shared_streams.items():
        direct = [player for player in players if player.get("selected_source_id") == source_id]
        digital = [player for player in players if player.get("selected_source_id") == 100002]
        if not direct or not digital:
            continue
        members = [str(player["registry_id"]) for player in players]
        owner = str(direct[0]["registry_id"])
        group = {
            "group_id": f"c4stream:{source_id}:{fingerprint[:16]}",
            "name": "Sessione audio", "owner_registry_id": owner,
            "member_registry_ids": members, "completeness": "complete",
            "resource_revision": source_id, "inferred_from_stream": True,
        }
        groups.append(group)
        for player in players:
            player["group"] = group
    routed: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for player in items:
        if player.get("group") or player.get("active_experience") != "listen":
            continue
        route_id = int(player.get("active_source_id") or 0)
        playback_identity = "\x1f".join(str(player.get(key) or "").strip().casefold() for key in ("title", "artist", "album"))
        if route_id > 0 and playback_identity.replace("\x1f", ""):
            routed.setdefault((route_id, playback_identity), []).append(player)
    for (route_id, playback_identity), players in routed.items():
        if len(players) < 2:
            continue
        members = [str(player["registry_id"]) for player in players]
        owner = members[0]
        group = {
            "group_id": f"c4route:{route_id}:{hashlib.sha256(playback_identity.encode()).hexdigest()[:12]}",
            "name": "Sessione audio",
            "owner_registry_id": owner,
            "member_registry_ids": members,
            "completeness": "complete",
            "resource_revision": route_id,
            "inferred_from_route": True,
        }
        groups.append(group)
        for player in players:
            player["group"] = group
    return groups


def _decode_artwork_url(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096:
        return ""
    direct = httpx.URL(value)
    if direct.scheme in {"http", "https"} and direct.host:
        return value
    try:
        decoded = base64.b64decode(value, validate=True).decode("utf-8")
        url = httpx.URL(decoded)
        return decoded if url.scheme in {"http", "https"} and url.host else ""
    except (ValueError, UnicodeError):
        return ""
