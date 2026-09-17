from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import time
from typing import Any

import httpx

_artwork: dict[str, str] = {}
_cache: dict[str, Any] = {"host": "", "expires": 0.0, "value": None}
_lock = asyncio.Lock()
_command_lock = asyncio.Lock()
_remotes: dict[str, Any] = {}
_digit_buffers: dict[str, list[str]] = {}
_digit_tasks: dict[str, asyncio.Task] = {}
_app_icons: dict[str, tuple[str, str]] = {}
REMOTE_ACTIONS = ["play", "pause", "stop", "scan_fwd", "scan_rev", "skip_fwd", "skip_rev", "menu", "up", "down", "left", "right", "enter", "channel_up", "channel_down", "record", "page_up", "page_down", "info", "cancel", "dvr", "guide", *[f"digit_{value}" for value in range(10)], "custom:PROGRAM_A", "custom:PROGRAM_B", "custom:PROGRAM_C", "custom:PROGRAM_D"]
COMMANDS = {"play": "play", "pause": "pause", "stop": "stop", "scan_fwd": "fastforward", "skip_fwd": "fastforward", "scan_rev": "rewind", "skip_rev": "rewind", "menu": "home", "up": "up", "down": "down", "left": "left", "right": "right", "enter": "select", "channel_up": "channelup", "channel_down": "channeldown", "record": "record", "page_up": "channelup", "page_down": "channeldown", "info": "i", "cancel": "dismiss", "dvr": "sky", "guide": "tvguide", "custom:PROGRAM_A": "red", "custom:PROGRAM_B": "green", "custom:PROGRAM_C": "yellow", "custom:PROGRAM_D": "blue"}
COMMANDS.update({f"digit_{value}": str(value) for value in range(10)})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_box(host: str) -> dict[str, Any]:
    from pyskyqremote.skyq_remote import SkyQRemote

    remote = SkyQRemote(host)
    if not remote.device_setup:
        raise ConnectionError("Decoder Sky Q non raggiungibile")
    device = remote.get_device_information()
    power = _text(remote.power_status()).lower()
    result: dict[str, Any] = {
        "status": "online", "power": power, "state": "off" if power in {"off", "standby"} else "playing",
        "device": {key: getattr(device, key, None) for key in ("hardwareName", "hardwareModel", "deviceType", "manufacturer", "modelNumber", "serialNumber", "versionNumber", "countryCode", "uhdCapable", "hdrCapable")},
    }
    raw_apps = remote._remote_config.device_access.retrieve_information("apps") or {}
    apps = []
    excluded_ids = ("com.bskyb.broadcast", "com.bskyb.ca-", "com.bskyb.epgui", "com.bskyb.local", "com.bskyb.metric", "com.sky.my-sky", "com.skyita.channelchange", "com.skyita.dxxx")
    for entry in raw_apps.get("apps", []) if isinstance(raw_apps, dict) else []:
        app_id = _text(entry.get("appId"))
        title = _text(entry.get("title"))
        if not app_id or not title or entry.get("blocked") or app_id.startswith(excluded_ids):
            continue
        icon = ""
        for icon_entry in entry.get("icons", []) if isinstance(entry.get("icons"), list) else []:
            if isinstance(icon_entry, dict) and icon_entry.get("APPTRAY"):
                icon = _text(icon_entry["APPTRAY"])
                break
        if icon:
            path = httpx.URL(icon).path
            _app_icons[app_id] = (host, path)
        apps.append({"id": app_id, "title": title, "icon": bool(icon)})
    result["apps"] = sorted(apps, key=lambda item: item["title"].casefold())
    if result["state"] == "off":
        return result
    transport = remote.get_current_state()
    result["state"] = _text(getattr(transport, "state", "playing")).lower() or "playing"
    app = remote.get_active_application()
    result.update({"app_id": _text(getattr(app, "appId", "")), "app": _text(getattr(app, "title", ""))})
    media = remote.get_current_media()
    if not media:
        result["title"] = result["app"]
        return result
    result.update({
        "channel": _text(getattr(media, "channel", "")), "channel_number": _text(getattr(media, "channelno", "")),
        "artwork": _text(getattr(media, "image_url", "")), "media_type": "live" if getattr(media, "live", False) else "recording",
    })
    if getattr(media, "live", False) and getattr(media, "sid", None):
        programme = remote.get_current_live_tv_programme(media.sid)
        if programme:
            result.update({
                "title": _text(getattr(programme, "title", "")), "description": _text(getattr(programme, "synopsis", "")),
                "season": _text(getattr(programme, "season", "")), "episode": _text(getattr(programme, "episode", "")),
                "artwork": _text(getattr(programme, "image_url", "")) or result["artwork"],
            })
    elif getattr(media, "pvrid", None):
        recording = remote.get_recording(media.pvrid)
        if recording:
            result.update({
                "title": _text(getattr(recording, "title", "")), "description": _text(getattr(recording, "synopsis", "")),
                "season": _text(getattr(recording, "season", "")), "episode": _text(getattr(recording, "episode", "")),
                "channel": _text(getattr(recording, "channelname", "")),
                "artwork": _text(getattr(recording, "image_url", "")) or result["artwork"],
            })
    result["title"] = result.get("title") or result.get("app") or result.get("channel")
    return result


async def snapshot(config: dict[str, Any]) -> dict[str, Any]:
    host = _text(config.get("host"))
    if not config.get("enabled") or not host:
        return {"status": "disabled"}
    async with _lock:
        if _cache["host"] == host and time.monotonic() < float(_cache["expires"]) and isinstance(_cache["value"], dict):
            return dict(_cache["value"])
        try:
            value = await asyncio.wait_for(asyncio.to_thread(_read_box, host), timeout=12)
        except asyncio.TimeoutError as exc:
            raise ConnectionError("Sky Q non risponde entro 12 secondi") from exc
        _cache.update({"host": host, "expires": time.monotonic() + 5, "value": value})
        return dict(value)


def overlay_control4(providers: list[dict], data: dict[str, Any], config: dict[str, Any]) -> bool:
    if data.get("status") != "online":
        return False
    room_id = int(config.get("control4_room_id") or 0)
    source_id = int(config.get("control4_source_id") or 0)
    linked = False
    selected_apps = {str(title).strip().casefold() for title in config.get("services", []) if str(title).strip()}
    visible_apps = [app for app in data.get("apps", []) if _text(app.get("title")).casefold() in selected_apps]
    for provider in providers:
        if provider.get("id") != "control4":
            continue
        for item in provider.get("items", []):
            item_room = int(_text(item.get("registry_id")).removeprefix("c4room:") or 0)
            active_source = int(item.get("active_source_id") or 0)
            automatic = "sky" in _text(item.get("source")).casefold()
            if not ((room_id and item_room == room_id and (not source_id or active_source == source_id)) or (not room_id and ((source_id and active_source == source_id) or (not source_id and automatic)))):
                continue
            linked = True
            artwork_url = _text(data.get("artwork"))
            fingerprint = f"skyq-{hashlib.sha256(artwork_url.encode()).hexdigest()[:24]}" if artwork_url else ""
            if fingerprint:
                _artwork[fingerprint] = artwork_url
            item.update({
                "metadata_provider": "skyq", "skyq": True, "skyq_app": data.get("app"),
                "skyq_app_id": data.get("app_id"), "channel": data.get("channel"),
                "skyq_services": list(config.get("services") or []), "skyq_apps": visible_apps,
                "channel_number": data.get("channel_number"), "description": data.get("description"),
                "season": data.get("season"), "episode": data.get("episode"),
                "title": data.get("title") or item.get("title"), "artist": data.get("channel") or data.get("app"),
                "content_fingerprint": fingerprint or item.get("content_fingerprint"), "skyq_artwork": bool(fingerprint),
            })
            item.setdefault("capabilities", {})["artwork"] = bool(fingerprint) or bool(item["capabilities"].get("artwork"))
            for source in item.get("source_options", []):
                if int(source.get("source_id") or 0) == active_source and source.get("experience") == "watch":
                    source["remote_actions"] = REMOTE_ACTIONS
    return linked


def _remote(host: str) -> Any:
    from pyskyqremote.skyq_remote import SkyQRemote
    remote = _remotes.get(host)
    if remote is None:
        remote = SkyQRemote(host)
        if not remote.device_setup:
            raise ConnectionError("Decoder Sky Q non raggiungibile")
        _remotes[host] = remote
    return remote


async def _press(host: str, keys: str | list[str]) -> None:
    async with _command_lock:
        await asyncio.wait_for(asyncio.to_thread(lambda: _remote(host).press(keys)), timeout=max(8, len(keys) if isinstance(keys, list) else 1))


async def _flush_digits(host: str, delay: float = 0.55) -> None:
    task = asyncio.current_task()
    try:
        await asyncio.sleep(delay)
        keys = _digit_buffers.pop(host, [])
        if keys:
            await _press(host, keys)
    finally:
        if _digit_tasks.get(host) is task:
            _digit_tasks.pop(host, None)


async def command(config: dict[str, Any], action: str) -> dict[str, Any]:
    sky_command = COMMANDS.get(action)
    if not sky_command:
        raise ValueError("Tasto non supportato dal telecomando Sky Q")
    host = _text(config.get("host"))
    if not config.get("enabled") or not host:
        raise ValueError("Sky Q nativo non configurato")

    if action.startswith("digit_"):
        _digit_buffers.setdefault(host, []).append(sky_command)
        previous = _digit_tasks.pop(host, None)
        if previous:
            previous.cancel()
        _digit_tasks[host] = asyncio.create_task(_flush_digits(host))
        return {"ok": True, "provider": "skyq", "command": sky_command, "queued": True}
    pending = _digit_tasks.pop(host, None)
    if pending:
        pending.cancel()
        keys = _digit_buffers.pop(host, [])
        if keys:
            await _press(host, keys)
    await _press(host, sky_command)
    _cache["expires"] = 0.0
    return {"ok": True, "provider": "skyq", "command": sky_command}


async def artwork(fingerprint: str) -> httpx.Response:
    url_text = _artwork.get(fingerprint, "")
    if not url_text:
        return httpx.Response(404)
    url = httpx.URL(url_text)
    if url.scheme != "https" or url.username or url.password:
        return httpx.Response(415)
    host = (url.host or "").lower()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None or not (host == "sky.com" or host.endswith(".sky.com") or host.endswith(".skycdn.it") or host.endswith(".sky.it")):
        return httpx.Response(415)
    async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
        return await client.get(url)


async def app_icon(app_id: str) -> httpx.Response:
    cached = _app_icons.get(app_id)
    if not cached:
        return httpx.Response(404)
    host, path = cached
    async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
        return await client.get(f"http://{host}:8008{path}")


async def test(config: dict[str, Any]) -> dict[str, Any]:
    data = await snapshot({**config, "enabled": True})
    return {**data, "host": config.get("host")}
