"""Navigator for the installed Amazon Music and TIDAL MSP drivers.

Commands and first-selected arguments mirror their driver.xml screen definitions.
Opaque item handles keep driver IDs and metadata server-side.
"""

from __future__ import annotations

import re
import secrets
import time
from typing import Any

from .control4_msp import _as_items, _command, _image_url

_ITEMS: dict[str, tuple[float, str, int, int, str, dict[str, Any]]] = {}
_TTL = 900
_SERVICES = {"amazon": "Amazon Music", "tidal": "TIDAL"}
_ROOT_SCREENS = {"amazon": {"Home": "HomeScreen"}, "tidal": {
    "Library": "LibraryScreen", "Masters": "MastersScreen", "WhatsNew": "WhatsNewScreen",
    "Rising": "RisingScreen", "Discovery": "DiscoveryScreen", "Playlists": "PlaylistsScreen",
    "Genres": "GenresScreen",
}}
_CHILD_SCREENS = {"ListScreen", "CollectionScreen", "ViewArtistScreen", "ViewAlbumScreen"}
_AMAZON_FIELDS = ("id", "parentId", "itemType", "page", "isPlayable")
_TIDAL_FIELDS = ("title", "subtitle", "id", "artistId", "artist", "albumId", "album", "image", "itemType", "duration")
_PLAY_OPTIONS = {"PlayNow": "NOW", "PlayShuffle": "SHUFFLE", "PlayNext": "NEXT", "AddToQueue": "ADD", "ReplaceQueue": "REPLACE"}
_VISIBLE_ACTIONS = set(_PLAY_OPTIONS) | {"AddToLibrary", "RemoveFromLibrary", "FavoriteToRoom"}


def _stored(token: str, service: str, proxy_id: int, room_id: int, tab: str) -> dict[str, Any]:
    record = _ITEMS.get(token)
    if not record or record[0] < time.monotonic() or record[1:5] != (service, proxy_id, room_id, tab):
        raise ValueError("Voce scaduta: riapri il servizio")
    return record[5]


def _actions(entry: dict[str, Any]) -> list[str]:
    return [value for value in re.split(r"[\s,]+", str(entry.get("actions_list") or "")) if value in _VISIBLE_ACTIONS]


def _display_items(raw: list[dict[str, Any]], service: str, proxy_id: int, room_id: int, tab: str) -> list[dict[str, Any]]:
    now = time.monotonic()
    for token, record in list(_ITEMS.items()):
        if record[0] < now:
            _ITEMS.pop(token, None)
    result = []
    for entry in raw:
        token = secrets.token_urlsafe(18)
        _ITEMS[token] = (now + _TTL, service, proxy_id, room_id, tab, entry)
        image = entry.get("image_list") or entry.get("image") or ""
        if isinstance(image, dict):
            image = image.get("$t") or image.get("url") or ""
        actions = _actions(entry)
        if str(entry.get("isPlayable") or "").lower() == "true" and str(entry.get("itemType") or "") != "errorPopup" and "PlayNow" not in actions:
            actions.insert(0, "PlayNow")
        result.append({
            "id": token, "title": str(entry.get("title") or ""),
            "subtitle": str(entry.get("subtitle") or ""),
            "image": _image_url(image), "actions": actions,
            "default_action": str(entry.get("default_action") or ""),
            "link": str(entry.get("isLink") or "").lower() == "true" or str(entry.get("default_action") or "") == "SelectItem",
            "playable": str(entry.get("isPlayable") or "").lower() == "true",
        })
    return result


async def catalog_tabs(service: str, proxy_id: int, room_id: int) -> dict[str, Any]:
    if service not in _SERVICES:
        raise ValueError("Servizio non supportato")
    data = await _command(proxy_id, room_id, "GetTabList", {})
    tabs = data.get("Tabs", {}).get("Tab", []) if isinstance(data, dict) else []
    tabs = tabs if isinstance(tabs, list) else [tabs] if isinstance(tabs, dict) else []
    allowed = _ROOT_SCREENS[service]
    result = [{"id": tab["Id"], "name": tab.get("Name") or tab["Id"]} for tab in tabs
              if isinstance(tab, dict) and (tab.get("Id") in allowed or tab.get("Id") == "Settings")]
    return {"tabs": result}


async def catalog_settings(proxy_id: int, room_id: int) -> dict[str, str]:
    data = await _command(proxy_id, room_id, "GetSettings", {})
    values = data.get("Settings", {}) if isinstance(data, dict) else {}
    values = values if isinstance(values, dict) else {}
    return {"status": str(values.get("status") or ""), "username": str(values.get("username") or "")}


async def catalog_browse(service: str, proxy_id: int, room_id: int, tab: str,
                         parent: str | None = None, offset: int = 0, search: str = "") -> dict[str, Any]:
    if service not in _SERVICES or tab not in _ROOT_SCREENS[service] or not 0 <= offset <= 1000 or len(search) > 120:
        raise ValueError("Parametri di navigazione non validi")
    if parent:
        item = _stored(parent, service, proxy_id, room_id, tab)
        selected_fields = _AMAZON_FIELDS if service == "amazon" else _TIDAL_FIELDS
        selected = {key: item[key] for key in selected_fields if key in item}
        next_data = await _command(proxy_id, room_id, "SelectItem", selected)
        screen = str(next_data.get("NextScreen") or "") if isinstance(next_data, dict) else ""
        if screen not in _CHILD_SCREENS:
            raise ValueError("Schermata del driver non supportata")
        values = {"screenId": screen, **selected}
    else:
        values = {"screenId": _ROOT_SCREENS[service][tab]}
    if service == "tidal" and parent:
        values.update({"offset": offset, "limit": 30})
    if search and parent:
        values.update({"search": search, "filter": "fulltextsearch"})
    data = await _command(proxy_id, room_id, "Browse", values)
    raw, total = _as_items(data)
    return {"items": _display_items(raw, service, proxy_id, room_id, tab),
            "offset": offset, "total": total, "more": service == "tidal" and offset + len(raw) < total}


async def catalog_action(service: str, proxy_id: int, room_id: int, tab: str,
                         item_id: str, action: str) -> dict[str, bool]:
    if service not in _SERVICES:
        raise ValueError("Servizio non supportato")
    item = _stored(item_id, service, proxy_id, room_id, tab)
    if action not in _actions(item) and not (action == "PlayNow" and str(item.get("isPlayable") or "").lower() == "true" and str(item.get("itemType") or "") != "errorPopup"):
        raise ValueError("Azione non disponibile")
    if action in _PLAY_OPTIONS:
        values = {key: item[key] for key in ("id", "itemType") if key in item}
        values["playOption"] = _PLAY_OPTIONS[action]
        await _command(proxy_id, room_id, "Play", values, wait_response=False)
    elif service == "tidal" and action in {"AddToLibrary", "RemoveFromLibrary", "FavoriteToRoom"}:
        values = {key: item[key] for key in _TIDAL_FIELDS if key in item}
        await _command(proxy_id, room_id, action, values, wait_response=False)
    else:
        raise ValueError("Azione non disponibile")
    return {"ok": True}
