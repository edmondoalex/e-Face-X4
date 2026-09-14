"""Control4 Stations media-service browser (proxy 24 on the current system)."""

from __future__ import annotations

import re
import secrets
import time
from typing import Any

from .control4_msp import _as_items, _command, _image_url

_ITEMS: dict[str, tuple[float, int, int, str, dict[str, Any]]] = {}
_TTL = 900
_TABS = {"Stations": "Radio", "Sources": "Sorgenti", "Genres": "Generi"}
_FORMATTERS = {"Stations": ("getStations", "formatStations"), "Sources": ("getStations", "formatSources"), "Genres": ("getGenres", "formatGenres")}


def _label(value: Any) -> str:
    text = str(value or "")
    match = re.search(r'(?:^|;)\w+="([^"]*)"', text) if text.startswith('#!') else None
    return match.group(1) if match else text


def _artwork(value: Any) -> str:
    if isinstance(value, list):
        value = next((entry.get("$t") for entry in value if isinstance(entry, dict) and str(entry.get("$t") or "").startswith("https://")), "")
    elif isinstance(value, dict):
        value = value.get("$t") or ""
    return _image_url(value)


def _stored(token: str, proxy_id: int, room_id: int, tab: str) -> dict[str, Any]:
    record = _ITEMS.get(token)
    if not record or record[0] < time.monotonic() or record[1:4] != (proxy_id, room_id, tab):
        raise ValueError("Voce scaduta: riapri Stations")
    return record[4]


async def stations_browse(proxy_id: int, room_id: int, tab: str, parent: str = "", offset: int = 0) -> dict[str, Any]:
    if tab not in _TABS or not 0 <= offset <= 1000 or (parent and tab == "Stations"):
        raise ValueError("Navigazione Stations non valida")
    if parent:
        selected = _stored(parent, proxy_id, room_id, tab)
        values = {"name": "getStations", "formatter": "formatStations"}
        if tab == "Sources":
            values["deviceId"] = selected["deviceId"]
        else:
            values["genre"] = selected["genre"]
    else:
        name, formatter = _FORMATTERS[tab]
        values = {"name": name, "formatter": formatter}
    if parent or tab == "Stations":
        values.update({"start": offset, "count": 30})
    data = await _command(proxy_id, room_id, "getData", values)
    raw, total = _as_items(data)
    now = time.monotonic()
    for token, record in list(_ITEMS.items()):
        if record[0] < now:
            _ITEMS.pop(token, None)
    items = []
    for entry in raw:
        token = secrets.token_urlsafe(18)
        _ITEMS[token] = (now + _TTL, proxy_id, room_id, tab, entry)
        station = bool(parent or tab == "Stations")
        title = (entry.get("name") or entry.get("stationName")) if station else (entry.get("sourceName") if tab == "Sources" else entry.get("genreName"))
        items.append({"id": token, "title": _label(title), "subtitle": _label(entry.get("info")),
                      "image": _artwork(entry.get("image")), "actions": ["SelectStation", "FavoriteToRoom"] if station else [],
                      "default_action": "SelectStation" if station else "Browse", "link": not station})
    return {"items": items, "offset": offset, "total": total, "more": offset + len(raw) < total}


async def stations_action(proxy_id: int, room_id: int, tab: str, item_id: str, action: str) -> dict[str, bool]:
    item = _stored(item_id, proxy_id, room_id, tab)
    if "stationId" not in item or action not in {"SelectStation", "FavoriteToRoom"}:
        raise ValueError("Azione Stations non disponibile")
    if action == "SelectStation":
        await _command(proxy_id, room_id, "selectStation", {"id": item["stationId"], "genre": item.get("genre") or ""}, wait_response=False)
    else:
        await _command(proxy_id, room_id, "FavoriteToRoom", {"stationId": item["stationId"]}, wait_response=False)
    return {"ok": True}
