"""Small, bounded Control4 MSP navigator for the installed TuneIn driver.

The protocol uses the media_service proxy (not its paired Lua device), XML
ARGS, and asynchronous OnDataToUI/data.RESPONSE messages correlated by SEQ.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from html import escape
from typing import Any
from urllib.parse import urlsplit

from pyControl4.websocket import C4Websocket

from .control4 import control4_director, load_control4_config

_ITEMS: dict[str, tuple[float, int, int, str, dict[str, Any]]] = {}
_TTL = 900
_FIELDS = ("Type", "ContainerType", "Title", "Subtitle", "GuideId", "Image", "Url")


def _args(values: dict[str, Any]) -> str:
    return "<args>" + "".join(
        f'<arg name="{escape(key, quote=True)}">{escape(str(value), quote=True)}</arg>'
        for key, value in values.items() if value is not None
    ) + "</args>"


def _image_url(value: Any) -> str:
    url = str(value or "")
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        return ""
    return url if len(url) <= 2048 else ""


def _as_items(data: Any) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(data, dict):
        return [], 0
    listing = data.get("List")
    if not isinstance(listing, dict):
        return [], 0
    raw = listing.get("item", [])
    items = raw if isinstance(raw, list) else [raw] if isinstance(raw, dict) else []
    length = listing.get("length")
    return [item for item in items if isinstance(item, dict)], int(length) if str(length).isdigit() else len(items)


async def _command(proxy_id: int, room_id: int, name: str, values: dict[str, Any], wait_response: bool = True) -> Any:
    config = load_control4_config()
    director, token = await control4_director(config)
    socket = C4Websocket(config["host"])
    seq = secrets.randbelow(2_000_000_000) + 1
    nav_id = secrets.token_hex(16)
    done: asyncio.Future[Any] = asyncio.get_running_loop().create_future()

    async def received(_item_id: int, message: Any) -> None:
        response = message.get("data", {}).get("RESPONSE") if isinstance(message, dict) else None
        if not isinstance(response, dict) or str(response.get("SEQ")) != str(seq) or str(response.get("NAVID")) != nav_id:
            return
        if not done.done():
            done.set_result(response.get("DATA"))

    socket.add_item_callback(proxy_id, received)
    try:
        await asyncio.wait_for(socket.sio_connect(token), 10)
        # The subscription acknowledgement follows socket connection.
        await asyncio.sleep(2)
        await director.send_post_request(
            f"/api/v1/items/{proxy_id}/commands", name,
            {"ROOMID": room_id, "SEQ": seq, "NAVID": nav_id, "ARGS": _args(values), "LOCALE": "it_IT"}, False,
        )
        return await asyncio.wait_for(done, 12) if wait_response else None
    finally:
        await socket.sio_disconnect()


async def tunein_browse(proxy_id: int, room_id: int, tab: str, parent: str | None = None, offset: int = 0, search: str = "") -> dict[str, Any]:
    if tab not in {"Home", "Browse", "Favorites"} or not 0 <= offset <= 1000 or len(search) > 120:
        raise ValueError("Parametri di navigazione non validi")
    item: dict[str, Any] = {}
    if parent:
        stored = _ITEMS.get(parent)
        if not stored or stored[0] < time.monotonic() or stored[1:4] != (proxy_id, room_id, tab):
            raise ValueError("Voce scaduta: riapri il servizio")
        item = stored[4]
    values = {key: item.get(key) for key in _FIELDS if key in item}
    values.update({"screenId": "BrowseScreen", "tabId": tab, "offset": offset, "limit": 30})
    if search:
        values["search"] = search
        values["filter"] = "fulltextsearch"
    data = await _command(proxy_id, room_id, "GetBrowseScreen", values)
    raw, total = _as_items(data)
    now = time.monotonic()
    for key, value in list(_ITEMS.items()):
        if value[0] < now:
            _ITEMS.pop(key, None)
    result = []
    for entry in raw:
        key = secrets.token_urlsafe(18)
        _ITEMS[key] = (now + _TTL, proxy_id, room_id, tab, entry)
        result.append({
            "id": key, "title": str(entry.get("Title") or ""),
            "subtitle": str(entry.get("Subtitle") or ""),
            "image": _image_url(entry.get("Image")),
            "actions": [part.strip() for part in str(entry.get("actions_list") or "").split(",") if part.strip() in {"Browse", "Play", "Follow", "Unfollow", "Profile", "FavoriteToRoom", "FavoriteToHome"}],
            "default_action": str(entry.get("default_action") or ""),
            "link": str(entry.get("isLink") or "").lower() == "true",
        })
    return {"items": result, "offset": offset, "total": total, "more": offset + len(raw) < total}


async def tunein_action(proxy_id: int, room_id: int, tab: str, item_id: str, action: str) -> dict[str, Any]:
    stored = _ITEMS.get(item_id)
    if not stored or stored[0] < time.monotonic() or stored[1:4] != (proxy_id, room_id, tab):
        raise ValueError("Voce scaduta: riapri il servizio")
    item = stored[4]
    allowed = {part.strip() for part in str(item.get("actions_list") or "").split(",")}
    if action not in {"Play", "Follow", "Unfollow", "FavoriteToRoom", "FavoriteToHome"} or action not in allowed:
        raise ValueError("Azione non disponibile")
    values = {key: item.get(key) for key in _FIELDS if key in item}
    values.update({"screenId": "BrowseScreen", "tabId": tab})
    await _command(proxy_id, room_id, action, values, wait_response=False)
    return {"ok": True}


async def tunein_settings(proxy_id: int, room_id: int) -> dict[str, str]:
    data = await _command(proxy_id, room_id, "GetSettings", {})
    values = data.get("Settings", {}) if isinstance(data, dict) else {}
    if not isinstance(values, dict):
        values = {}
    # GetSettings can include a password: expose only these two display fields.
    return {"status": str(values.get("status") or ""), "username": str(values.get("username") or "")}
