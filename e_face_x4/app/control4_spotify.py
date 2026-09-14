"""Spotify Connect media-service navigator backed by its installed C4 driver."""

from __future__ import annotations

import re
import secrets
import time
from typing import Any

from .control4_msp import _as_items, _command, _image_url
from .media_favorites import add_favorite, list_favorites, remove_favorite

_ITEMS: dict[str, tuple[float, int, int, str, dict[str, Any]]] = {}
_TTL = 900
_SCREENS = {"Presets": ("PresetsScreen", "ListPresets"), "Recently Played": ("RecentlyPlayedScreen", "ListRecentlyPlayed")}
_PLAY_FIELDS = ("blob", "title", "subtitle", "uri", "imageurl", "user")


def _favorite_id(proxy_id: int, item: dict[str, Any]) -> str:
    key = str(item.get("uri") or item.get("blob") or "")
    return f"msp:spotify:{proxy_id}:{key}" if key else ""


def _stored(token: str, proxy_id: int, room_id: int, tab: str) -> dict[str, Any]:
    record = _ITEMS.get(token)
    if not record or record[0] < time.monotonic() or record[1:4] != (proxy_id, room_id, tab):
        raise ValueError("Voce Spotify scaduta")
    return record[4]


async def spotify_browse(proxy_id: int, room_id: int, tab: str, offset: int = 0) -> dict[str, Any]:
    if tab not in _SCREENS or offset != 0:
        raise ValueError("Sezione Spotify non valida")
    screen, command = _SCREENS[tab]
    data = await _command(proxy_id, room_id, command, {"screenId": screen, "tabId": tab, "screenDepth": 0})
    raw, total = _as_items(data)
    now = time.monotonic()
    for token, record in list(_ITEMS.items()):
        if record[0] < now:
            _ITEMS.pop(token, None)
    favorites = {item["id"] for item in list_favorites()}
    items = []
    for entry in raw:
        if str(entry.get("isHeader") or "").lower() == "true":
            items.append({"id": "", "title": str(entry.get("title") or ""), "header": True, "subtitle": "", "image": "", "actions": [], "default_action": "", "link": False})
            continue
        token = secrets.token_urlsafe(18)
        _ITEMS[token] = (now + _TTL, proxy_id, room_id, tab, entry)
        actions = set(re.split(r"[\s,]+", str(entry.get("actions_list") or "")))
        play = "PresetPlay" if "PresetPlay" in actions else "PlayRecent" if "PlayRecent" in actions else ""
        favorite_id = _favorite_id(proxy_id, entry)
        visible = [play] if play else []
        if play and favorite_id:
            visible.append("UnpinFavorite" if favorite_id in favorites else "PinFavorite")
        items.append({"id": token, "title": str(entry.get("title") or ""), "subtitle": str(entry.get("subtitle") or ""),
                      "image": _image_url(entry.get("imageurl")), "actions": visible, "default_action": play, "link": False})
    return {"items": items, "offset": 0, "total": total, "more": False}


async def spotify_settings(proxy_id: int, room_id: int) -> dict[str, str]:
    data = await _command(proxy_id, room_id, "GetSpotifySettings", {})
    settings = data.get("Settings", {}) if isinstance(data, dict) else {}
    settings = settings if isinstance(settings, dict) else {}
    return {"status": str(settings.get("scName") or "Spotify Connect"), "username": str(settings.get("scLoggedInUser") or "")}


async def spotify_action(proxy_id: int, room_id: int, tab: str, token: str, action: str) -> dict[str, bool]:
    entry = _stored(token, proxy_id, room_id, tab)
    actions = set(re.split(r"[\s,]+", str(entry.get("actions_list") or "")))
    play = "PresetPlay" if "PresetPlay" in actions else "PlayRecent" if "PlayRecent" in actions else ""
    if not play or action not in {play, "PinFavorite", "UnpinFavorite"}:
        raise ValueError("Azione Spotify non disponibile")
    args = {key: str(entry[key]) for key in _PLAY_FIELDS if entry.get(key) is not None}
    if action == play:
        args["extraRooms"] = ""
        await _command(proxy_id, room_id, play, args, wait_response=False)
    else:
        identity = _favorite_id(proxy_id, entry)
        if not identity:
            raise ValueError("Contenuto Spotify senza identificativo")
        if action == "PinFavorite":
            add_favorite({"id": identity, "kind": "msp", "service": "spotify", "proxy_id": proxy_id,
                          "title": str(entry.get("title") or ""), "subtitle": str(entry.get("subtitle") or ""),
                          "image": _image_url(entry.get("imageurl")), "play_command": play, "play_args": args})
        else:
            remove_favorite(identity)
    return {"ok": True}
