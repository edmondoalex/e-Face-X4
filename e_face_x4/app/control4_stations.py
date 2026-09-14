"""Control4 Stations media-service browser (proxy 24 on the current system)."""

from __future__ import annotations

import re
import json
import secrets
import time
from pathlib import Path
from typing import Any

from .control4_msp import _as_items, _command, _image_url

_ITEMS: dict[str, tuple[float, int, int, str, dict[str, Any]]] = {}
_TTL = 900
_TABS = {"Stations": "Radio", "Sources": "Sorgenti", "Genres": "Generi"}
_FORMATTERS = {"Stations": ("getStations", "formatStations"), "Sources": ("getStations", "formatSources"), "Genres": ("getGenres", "formatGenres")}
_STATION_METADATA: dict[int, tuple[str, int, str]] = {}
_CATALOG_PATH = Path("/data/control4_stations_catalog.json")
try:
    _STATION_METADATA.update({int(key): (str(value[0]), int(value[1]), str(value[2])) for key, value in json.loads(_CATALOG_PATH.read_text(encoding="utf-8")).items() if isinstance(value, list) and len(value) == 3})
except (OSError, ValueError, TypeError, IndexError):
    pass


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


def station_artwork_path(token: str) -> str:
    record = _ITEMS.get(token)
    if not record or record[0] < time.monotonic():
        raise ValueError("Copertina scaduta")
    images = record[4].get("image")
    entries = images if isinstance(images, list) else [images]
    for entry in entries:
        uri = entry.get("$t") if isinstance(entry, dict) else entry
        if isinstance(uri, str) and re.fullmatch(r"controller://images/broadcast/[a-f0-9]{2}/[a-f0-9-]+(?:_s|_m|_t)?\.(?:jpg|jpeg|png)", uri, re.I):
            return "/" + uri.removeprefix("controller://")
    raise ValueError("Copertina non disponibile")


def station_identity(media_id: Any, channel: Any) -> tuple[str, int] | None:
    try:
        station = _STATION_METADATA.get(int(media_id))
    except (ValueError, TypeError):
        return None
    return (station[0], station[1]) if station and station[0].casefold() == str(channel or "").casefold() else None


def station_media_artwork(media_id: Any, channel: Any) -> str:
    if not station_identity(media_id, channel):
        return ""
    try:
        return _STATION_METADATA[int(media_id)][2]
    except (ValueError, KeyError, TypeError):
        return ""


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
        if station and str(entry.get("stationId") or "").isdigit():
            try:
                artwork_path = station_artwork_path(token)
            except ValueError:
                artwork_path = ""
            _STATION_METADATA[int(entry["stationId"])] = (_label(title), int(entry.get("deviceId") or 0), artwork_path)
        image = _artwork(entry.get("image"))
        if not image:
            try:
                station_artwork_path(token)
                image = f"api/control4/stations/image/{token}"
            except ValueError:
                if tab == "Sources" and _label(title).casefold() == "internet radio":
                    image = "assets/control4-icons/internet-radio.png"
                elif tab == "Sources" and str(entry.get("deviceId") or "").isdigit():
                    image = f"api/control4/source-icon/{entry['deviceId']}"
        items.append({"id": token, "title": _label(title), "subtitle": _label(entry.get("info")),
                      "image": image, "actions": ["SelectStation", "FavoriteToRoom"] if station else [],
                      "default_action": "SelectStation" if station else "Browse", "link": not station})
    if any(str(entry.get("stationId") or "").isdigit() for entry in raw):
        try:
            _CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            temporary = _CATALOG_PATH.with_suffix(".tmp")
            temporary.write_text(json.dumps(_STATION_METADATA, ensure_ascii=False), encoding="utf-8")
            temporary.replace(_CATALOG_PATH)
        except OSError:
            pass
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
