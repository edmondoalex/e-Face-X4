from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from pathlib import Path
from dataclasses import replace

import httpx
import uvicorn
import websockets
from fastapi import FastAPI, Header, HTTPException, Query, Response, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import load_settings
from .connectors import BusproConnector, EThermConnector, EkonexMediaConnector
from .connectors.supervisor import discover_addon_url
from .demo import dashboard as demo_dashboard

VERSION = "1.7.0"
STATIC = Path(__file__).parent / "static"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [e-face-x4] %(message)s")


def create_app() -> FastAPI:
    app = FastAPI(title="e-Face X4", version=VERSION, docs_url=None, redoc_url=None)
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

    async def resolved_provider(config, slug: str, port: int, timeout: float):
        manual = str(config.base_url or "").lower()
        if manual and "127.0.0.1" not in manual and "localhost" not in manual:
            return config
        discovered = await discover_addon_url(slug, port, timeout)
        return replace(config, base_url=discovered) if discovered else config

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True, "version": VERSION}

    @app.get("/api/bootstrap")
    async def bootstrap() -> dict:
        settings = load_settings()
        buspro_config, etherm_config = await asyncio.gather(
            resolved_provider(settings.buspro, "e_hdl_buspro_mqtt", 8124, settings.request_timeout_s),
            resolved_provider(settings.etherm, "e_therm_plus_ks", 8080, settings.request_timeout_s),
        )
        connectors = [
            BusproConnector(buspro_config, settings.request_timeout_s),
            EThermConnector(etherm_config, settings.request_timeout_s),
            EkonexMediaConnector(settings.evoice, settings.request_timeout_s),
        ]
        providers = await asyncio.gather(*(connector.snapshot() for connector in connectors))
        dashboard = demo_dashboard() if settings.demo_mode else {"rooms": [], "widgets": [], "media": None}
        dashboard.setdefault("home", {})["name"] = settings.home_name
        if not settings.demo_mode:
            buspro = next((item for item in providers if item.get("id") == "buspro" and item.get("status") == "online"), None)
            normalized = buspro.get("normalized", {}) if isinstance(buspro, dict) else {}
            counts = normalized.get("counts", {}) if isinstance(normalized, dict) else {}
            dashboard["rooms"] = normalized.get("rooms", []) if isinstance(normalized, dict) else []
            dashboard["devices"] = normalized.get("devices", []) if isinstance(normalized, dict) else []
            etherm = next((item for item in providers if item.get("id") == "etherm" and item.get("status") == "online"), None)
            if isinstance(etherm, dict):
                dashboard["devices"].extend(etherm.get("items", []))
            media = next((item for item in providers if item.get("id") == "evoice" and item.get("status") == "online"), None)
            if isinstance(media, dict):
                media_items = media.get("items", [])
                dashboard["devices"].extend(media_items)
                playing = next((item for item in media_items if str(item.get("state", "")).lower() == "playing"), None)
                selected = playing or next(iter(media_items), None)
                if isinstance(selected, dict):
                    dashboard["media"] = {
                        "title": selected.get("title") or selected.get("name"),
                        "artist": selected.get("artist"), "room": selected.get("room"),
                        "volume": selected.get("volume") or 0,
                    }
            room_map = {str(room.get("name", "")).casefold(): room for room in dashboard["rooms"] if isinstance(room, dict)}
            for device in dashboard["devices"]:
                room = str(device.get("room") or "Clima")
                key = room.casefold()
                if key not in room_map:
                    entry = {"id": f"room-{len(room_map)}", "name": room, "devices": 0}
                    room_map[key] = entry
                    dashboard["rooms"].append(entry)
                if device.get("provider") == "etherm":
                    room_map[key]["devices"] += 1
            dashboard["widgets"] = [
                {"id": "lights", "title": "Luci", "value": str(counts.get("lights", 0)), "detail": "dispositivi", "icon": "light"},
                {"id": "extra", "title": "Extra", "value": str(counts.get("switches", 0)), "detail": "switch", "icon": "energy"},
                {"id": "covers", "title": "Cover", "value": str(counts.get("covers", 0)), "detail": "dispositivi", "icon": "cover"},
                {"id": "locks", "title": "Sicurezza", "value": str(counts.get("locks", 0)), "detail": "serrature", "icon": "shield"},
            ]
        return {
            "version": VERSION,
            "nav_icons": settings.nav_icons,
            "mode": "demo" if settings.demo_mode else "live",
            "dashboard": dashboard,
            "providers": providers,
        }

    @app.get("/api/icons/mdi/{icon_name}.svg", include_in_schema=False)
    async def mdi_icon(icon_name: str) -> Response:
        name = icon_name.strip().lower()
        fallback = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2 22 12 12 22 2 12Z"/></svg>'
        if not re.fullmatch(r"[a-z0-9_-]{1,64}", name):
            return Response(fallback, media_type="image/svg+xml")
        settings = load_settings()
        cache_dir = Path("/data/mdi")
        cache_file = cache_dir / f"{name}.svg"
        try:
            if cache_file.is_file():
                content = cache_file.read_bytes()
                if len(content) <= 200_000:
                    return Response(content, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})
            async with httpx.AsyncClient(timeout=settings.request_timeout_s, follow_redirects=False) as client:
                upstream = await client.get(f"https://raw.githubusercontent.com/Templarian/MaterialDesign/master/svg/{name}.svg")
                upstream.raise_for_status()
            if len(upstream.content) > 200_000 or "svg" not in upstream.headers.get("content-type", ""):
                raise ValueError("invalid icon")
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(upstream.content)
            return Response(upstream.content, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})
        except (httpx.HTTPError, OSError, ValueError):
            return Response(fallback, media_type="image/svg+xml")

    @app.post("/api/devices/{device_id}/command")
    async def device_command(device_id: str, payload: dict) -> dict:
        settings = load_settings()
        if device_id.startswith("media:"):
            config = settings.evoice
            if not config.enabled or not config.base_url or not config.installation_id:
                raise HTTPException(status_code=503, detail="Ekonex Media non disponibile")
            operation = str(payload.get("action") or "")
            allowed = {"media_play", "media_pause", "media_stop", "media_next", "media_previous", "set_volume", "volume_mute", "volume_unmute", "select_source", "media_unjoin"}
            if operation not in allowed:
                raise HTTPException(status_code=400, detail="Comando multimedia non valido")
            arguments = {}
            if operation == "set_volume":
                arguments["volume_percent"] = int(payload.get("value"))
            elif operation == "select_source":
                arguments["source"] = str(payload.get("value") or "")
            command = {"request_id": str(uuid.uuid4()), "operation": operation, "arguments": arguments, "expected_resource_revision": payload.get("resource_revision") if operation == "media_unjoin" else None}
            try:
                return await EkonexMediaConnector(config, settings.request_timeout_s).command(device_id.split(":", 1)[1], command)
            except httpx.HTTPStatusError as exc:
                detail = None
                if exc.response.headers.get("content-type", "").startswith("application/json"):
                    try:
                        error_payload = exc.response.json()
                        detail = (error_payload.get("error") or {}).get("message") if isinstance(error_payload, dict) else None
                    except ValueError:
                        pass
                raise HTTPException(status_code=exc.response.status_code, detail=detail or "Comando Ekonex Media rifiutato")
            except httpx.HTTPError:
                raise HTTPException(status_code=502, detail="Ekonex Media non raggiungibile")
            except (ValueError, TypeError) as exc:
                raise HTTPException(status_code=400, detail=str(exc))
        if device_id.startswith("therm:"):
            config = await resolved_provider(settings.etherm, "e_therm_plus_ks", 8080, settings.request_timeout_s)
            if not config.enabled or not config.base_url:
                raise HTTPException(status_code=503, detail="Connettore e-Therm non disponibile")
            try:
                return await EThermConnector(config, settings.request_timeout_s).command(device_id.split(":", 1)[1], str(payload.get("action") or ""), payload.get("value"))
            except httpx.HTTPError:
                raise HTTPException(status_code=502, detail="e-Therm non raggiungibile")
            except (ValueError, TypeError) as exc:
                raise HTTPException(status_code=400, detail=str(exc))
        config = await resolved_provider(settings.buspro, "e_hdl_buspro_mqtt", 8124, settings.request_timeout_s)
        if not config.enabled or not config.base_url:
            raise HTTPException(status_code=503, detail="Connettore e-HDL non disponibile")
        try:
            return await BusproConnector(config, settings.request_timeout_s).command(device_id, str(payload.get("action") or ""), payload.get("value"))
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=502, detail=f"e-HDL ha risposto HTTP {exc.response.status_code}")
        except httpx.HTTPError:
            raise HTTPException(status_code=502, detail="e-HDL non raggiungibile")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/media/{registry_id}/artwork")
    async def media_artwork(registry_id: str, fingerprint: str = Query(..., min_length=8, max_length=256), if_none_match: str | None = Header(None)) -> Response:
        settings = load_settings()
        config = settings.evoice
        if not config.enabled or not config.base_url or not config.installation_id:
            raise HTTPException(status_code=503, detail="Ekonex Media non disponibile")
        try:
            upstream = await EkonexMediaConnector(config, settings.request_timeout_s).artwork(registry_id, fingerprint, if_none_match)
        except httpx.HTTPError:
            raise HTTPException(status_code=502, detail="Ekonex Media non raggiungibile")
        if upstream.status_code == 304:
            return Response(status_code=304, headers={"Cache-Control": "private, max-age=300"})
        if upstream.status_code != 200:
            raise HTTPException(status_code=upstream.status_code, detail="Copertina non disponibile")
        media_type = upstream.headers.get("content-type", "").split(";", 1)[0]
        if media_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"} or len(upstream.content) > 700_000:
            raise HTTPException(status_code=415, detail="Copertina non valida")
        headers = {"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"}
        if upstream.headers.get("etag"):
            headers["ETag"] = upstream.headers["etag"]
        return Response(upstream.content, media_type=media_type, headers=headers)

    @app.websocket("/api/realtime")
    async def realtime(websocket: WebSocket) -> None:
        await websocket.accept()
        settings = load_settings()
        buspro, etherm = await asyncio.gather(
            resolved_provider(settings.buspro, "e_hdl_buspro_mqtt", 8124, settings.request_timeout_s),
            resolved_provider(settings.etherm, "e_therm_plus_ks", 8080, settings.request_timeout_s),
        )
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=100)

        async def buspro_events() -> None:
            ws_url = re.sub(r"^http", "ws", buspro.base_url.rstrip("/"), count=1) + "/ws"
            headers = {"Authorization": f"Bearer {buspro.token}"} if buspro.token else None
            async with websockets.connect(ws_url, additional_headers=headers, open_timeout=settings.request_timeout_s) as upstream:
                async for message in upstream:
                    try:
                        event = json.loads(message)
                    except (TypeError, json.JSONDecodeError):
                        continue
                    event_type = str(event.get("type") or "") if isinstance(event, dict) else ""
                    if event_type == "devices":
                        await queue.put({"type": "devices_changed"})
                        continue
                    allowed = {"light_state", "cover_state", "temp_value", "humidity_value", "illuminance_value", "air_quality", "gas_percent", "pir_state", "ultrasonic_state", "dry_contact_state", "ha_light_state", "ha_switch_state", "ha_cover_state", "ha_lock_state", "light_scenario_state", "light_scenario_running"}
                    data = event.get("data") if isinstance(event, dict) else None
                    if event_type in allowed and isinstance(data, dict):
                        safe = {key: data.get(key) for key in ("subnet_id", "device_id", "channel", "entity_id", "id", "state", "running", "value", "position", "brightness") if key in data}
                        await queue.put({"type": event_type, "data": safe})

        async def etherm_events() -> None:
            headers = EThermConnector(etherm, settings.request_timeout_s).headers()
            async with httpx.AsyncClient(timeout=None, follow_redirects=False) as client:
                async with client.stream("GET", f"{etherm.base_url}/api/stream?type=thermostats", headers=headers) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            await queue.put({"type": "thermostats_changed"})

        async def media_events() -> None:
            connector = EkonexMediaConnector(settings.evoice, settings.request_timeout_s)
            while True:
                try:
                    async for event in connector.events():
                        event_type = str(event.get("type") or "")
                        if event_type != "heartbeat":
                            await queue.put({"type": "media_changed", "event_type": event_type})
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logging.warning("Ekonex Media realtime disconnected; retrying")
                    await asyncio.sleep(2)

        tasks = []
        if buspro.enabled and buspro.base_url:
            tasks.append(asyncio.create_task(buspro_events()))
        if etherm.enabled and etherm.base_url:
            tasks.append(asyncio.create_task(etherm_events()))
        if settings.evoice.enabled and settings.evoice.base_url and settings.evoice.installation_id:
            tasks.append(asyncio.create_task(media_events()))
        if not tasks:
            await websocket.close(code=1013, reason="Nessun connettore realtime disponibile")
            return
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                except asyncio.TimeoutError:
                    if tasks and all(task.done() for task in tasks):
                        raise RuntimeError("connettori realtime disconnessi")
                    event = {"type": "keepalive"}
                await websocket.send_json(event)
        except Exception as exc:
            logging.warning("Realtime bridge closed: %s", type(exc).__name__)
            try:
                await websocket.close(code=1011)
            except RuntimeError:
                pass
        finally:
            for task in tasks:
                task.cancel()

    async def buspro_config():
        settings = load_settings()
        config = await resolved_provider(settings.buspro, "e_hdl_buspro_mqtt", 8124, settings.request_timeout_s)
        if not config.enabled or not config.base_url:
            raise HTTPException(status_code=503, detail="Connettore e-HDL non disponibile")
        return settings, config

    @app.get("/api/scenarios")
    async def scenarios() -> dict:
        settings, config = await buspro_config()
        headers = {"Authorization": f"Bearer {config.token}"} if config.token else {}
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_s, follow_redirects=False) as client:
                items_response, status_response = await asyncio.gather(
                    client.get(f"{config.base_url}/api/user/light_scenarios", headers=headers),
                    client.get(f"{config.base_url}/api/user/light_scenarios_status", headers=headers),
                )
                items_response.raise_for_status()
                status_response.raise_for_status()
            raw_items = items_response.json().get("items", [])
            status = status_response.json()
        except (httpx.HTTPError, ValueError, AttributeError):
            raise HTTPException(status_code=502, detail="Scenari e-HDL non disponibili")
        states = status.get("states", {}) if isinstance(status, dict) else {}
        running = status.get("running", {}) if isinstance(status, dict) else {}
        return {"items": [
            {
                "id": str(item.get("id") or ""), "name": str(item.get("name") or "Scenario"),
                "lights": len(item.get("items") or []), "covers": len(item.get("covers") or []),
                "run_enabled": bool(item.get("run_enabled")),
                "onoff_enabled": bool(item.get("onoff_enabled", True)),
                "state": str(states.get(str(item.get("id") or ""), "")),
                "running": bool(running.get(str(item.get("id") or ""))),
            }
            for item in raw_items if isinstance(item, dict) and item.get("id")
        ]}

    @app.post("/api/scenarios/{scenario_id}/command")
    async def scenario_command(scenario_id: str, payload: dict) -> dict:
        action = str(payload.get("action") or "").strip().lower()
        if action not in {"run", "stop", "on", "off"}:
            raise HTTPException(status_code=400, detail="Comando scenario non valido")
        settings, config = await buspro_config()
        headers = {"Authorization": f"Bearer {config.token}"} if config.token else {}
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_s, follow_redirects=False) as client:
                listing = await client.get(f"{config.base_url}/api/user/light_scenarios", headers=headers)
                listing.raise_for_status()
                valid_ids = {str(item.get("id")) for item in listing.json().get("items", []) if isinstance(item, dict)}
                if scenario_id not in valid_ids:
                    raise HTTPException(status_code=404, detail="Scenario non trovato")
                body = {"command": action.upper()} if action in {"run", "stop"} else {"state": action.upper()}
                response = await client.post(f"{config.base_url}/api/control/light_scenario/{scenario_id}", headers=headers, json=body)
                response.raise_for_status()
            return {"ok": True}
        except httpx.HTTPError:
            raise HTTPException(status_code=502, detail="Comando scenario e-HDL fallito")

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str) -> FileResponse:
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    return app


def main() -> None:
    uvicorn.run(create_app(), host="0.0.0.0", port=8099, access_log=False)


if __name__ == "__main__":
    main()
