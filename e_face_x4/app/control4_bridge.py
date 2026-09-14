"""Wireless Music Bridge Bluetooth navigator using its installed driver."""

from __future__ import annotations

import asyncio
import re
import secrets
import time
from typing import Any

from pyControl4.websocket import C4Websocket

from .control4 import control4_director, load_control4_config
from .control4_msp import _args, _as_items, _command

_ITEMS: dict[str, tuple[float, int, int, dict[str, Any]]] = {}
_TTL = 900
_PAIRING: dict[tuple[int, int], dict[str, Any]] = {}
_PAIRING_TASKS: dict[tuple[int, int], asyncio.Task] = {}


async def bridge_browse(proxy_id: int, room_id: int) -> dict[str, Any]:
    data = await _command(proxy_id, room_id, "PairedDeviceList", {"Menu": "Devices"}, is_async=True)
    raw, _ = _as_items(data)
    now = time.monotonic()
    for token, record in list(_ITEMS.items()):
        if record[0] < now:
            _ITEMS.pop(token, None)
    items: list[dict[str, Any]] = []
    for entry in raw:
        name = str(entry.get("Name") or entry.get("Title") or "")[:100]
        address = str(entry.get("Addr") or "")
        if not name or not re.fullmatch(r"[0-9A-Fa-f]{12}", address):
            continue
        token = secrets.token_urlsafe(18)
        _ITEMS[token] = (now + _TTL, proxy_id, room_id, entry)
        connected = str(entry.get("Connected") or "").lower() == "true"
        items.append({"id": token, "title": name, "subtitle": "Connesso" if connected else "",
                      "image": "", "icon": "mdi:bluetooth", "actions": ["BtConnectDisconnect", "BtRemoveDevice"],
                      "default_action": "", "link": False, "connected": connected})
    return {"items": items, "total": len(items), "offset": 0, "more": False, "max_devices": 5}


async def _watch_pairing(proxy_id: int, room_id: int, state: dict[str, Any], ready: asyncio.Event) -> None:
    config = load_control4_config()
    socket = C4Websocket(config["host"])
    nav_id = secrets.token_hex(16)
    seq = secrets.randbelow(2_000_000_000) + 1
    done = asyncio.Event()

    async def received(_item_id: int, message: Any) -> None:
        if not isinstance(message, dict):
            return
        data = message.get("data") or {}
        event = data.get("EVENT") if isinstance(data, dict) else None
        if isinstance(event, dict) and event.get("NAVID") == nav_id and event.get("NAME") == "DriverNotification":
            args = event.get("ARGS") or {}
            if isinstance(args, dict) and args.get("Id") == "Authenticate":
                state["status"] = "confirm"
                state["message"] = str(args.get("Message") or "Conferma il codice sul telefono")[:500]
        response = data.get("RESPONSE") if isinstance(data, dict) else None
        if isinstance(response, dict) and str(response.get("SEQ")) == str(seq) and response.get("NAVID") == nav_id:
            state["status"] = "complete"
            done.set()

    socket.add_item_callback(proxy_id, received)
    try:
        director, token = await control4_director(config)
        await asyncio.wait_for(socket.sio_connect(token), 10)
        await asyncio.sleep(2)
        await director.send_post_request(
            f"/api/v1/items/{proxy_id}/commands", "BtAddDevice",
            {"ROOMID": room_id, "SEQ": seq, "NAVID": nav_id, "ARGS": _args({"StartPairing": "true"}), "LOCALE": "it_IT"}, True,
        )
        if state["status"] == "starting":
            state["status"] = "waiting"
        ready.set()
        await asyncio.wait_for(done.wait(), 90)
    except asyncio.TimeoutError:
        state["status"] = "expired"
    except Exception:
        state["status"] = "error"
    finally:
        ready.set()
        await socket.sio_disconnect()


async def bridge_action(proxy_id: int, room_id: int, token: str, action: str) -> dict[str, Any]:
    pairing_key = (proxy_id, room_id)
    if action == "BtPairingStatus":
        state = _PAIRING.get(pairing_key) or {}
        return {"status": state.get("status", "idle"), "message": state.get("message", "")}
    if action == "BtAuthenticate":
        state = _PAIRING.get(pairing_key)
        if not state or state.get("status") != "confirm":
            raise ValueError("Nessuna conferma Bluetooth in attesa")
        await _command(proxy_id, room_id, "BtAuthenticate", {"Auth": "true"}, is_async=True)
        if state["status"] != "complete":
            state["status"] = "waiting"
        return {"ok": True}
    if action == "BtAddDevice":
        current = await bridge_browse(proxy_id, room_id)
        if len(current["items"]) >= 5:
            raise ValueError("Il bridge accetta al massimo 5 dispositivi: rimuovine uno prima di aggiungerne un altro")
        existing = _PAIRING_TASKS.get(pairing_key)
        if existing and not existing.done():
            return {"ok": True, "status": (_PAIRING.get(pairing_key) or {}).get("status", "waiting")}
        state: dict[str, Any] = {"status": "starting", "message": ""}
        _PAIRING[pairing_key] = state
        ready = asyncio.Event()
        task = asyncio.create_task(_watch_pairing(proxy_id, room_id, state, ready))
        _PAIRING_TASKS[pairing_key] = task
        await asyncio.wait_for(ready.wait(), 15)
        if state["status"] == "error":
            raise ValueError("Impossibile avviare l'abbinamento Bluetooth")
        return {"ok": True, "status": state["status"]}
    if action not in {"BtConnectDisconnect", "BtRemoveDevice"}:
        raise ValueError("Azione Wireless Music Bridge non valida")
    record = _ITEMS.get(token)
    if not record or record[0] < time.monotonic() or record[1:3] != (proxy_id, room_id):
        raise ValueError("Dispositivo Bluetooth scaduto: aggiorna la lista")
    entry = record[3]
    args = {key: str(entry.get(key) or "") for key in ("Name", "Addr", "Paired")}
    args["Connected"] = "true" if str(entry.get("Connected") or "").lower() == "true" else "false"
    await _command(proxy_id, room_id, action, args, is_async=True)
    if action == "BtRemoveDevice":
        _ITEMS.pop(token, None)
    return {"ok": True}
