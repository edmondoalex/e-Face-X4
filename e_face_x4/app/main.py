from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from dataclasses import replace
from urllib.parse import quote, urlsplit

import httpx
import uvicorn
import websockets
from pyControl4.websocket import C4Websocket
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

from .config import load_settings
from .control4 import control4_director, load_control4_config, public_control4_config, save_control4_config, test_control4_connection
from .control4_msp import tunein_browse, tunein_action, tunein_settings
from .control4_msp_catalog import catalog_action, catalog_browse, catalog_settings, catalog_tabs
from .control4_stations import station_artwork_path, station_catalog_artwork, station_identity, station_media_artwork, stations_action, stations_browse
from .control4_spotify import spotify_action, spotify_browse, spotify_settings
from .control4_bridge import bridge_action, bridge_browse
from .media_favorites import add_favorite, enrich_recent_favorites, favorite_by_id, list_favorites, load_favorite_artwork, remove_favorite, save_favorite_artwork
from .recent_visibility import filter_recents, hidden_recents, hide_recent, restore_recent, restore_recents
from .installer_auth import COOKIE, create_session, valid_session
from . import user_auth
from . import intercom_settings
from . import external_stations
from . import internal_stations
from . import control4_tablets
from . import voip_phones
from . import personal_devices
from . import intercom_groups
from . import push_notifications
from . import provisioner_client
from . import installation
from . import credential_inventory
from . import sip_accounts
from . import asterisk_ami
from . import doorbird_api
from . import wiim_settings
from . import wiim_services
from . import soundcloud_settings
from . import soundcloud_library
from . import startup_settings
from .connectors.soundcloud import SoundCloudClient
from .media_preferences import apply_preferences, load_preferences, save_preferences
from .source_icons import delete_source_icon, hidden_source_ids, load_builtin_source_icon, load_builtin_source_icon_by_id, load_source_icon, save_source_icon, set_source_hidden
from .backgrounds import CARD_THEMES, PRESETS, load_background, load_background_image, load_backgrounds, load_card_theme, load_card_glow, load_room_order, load_security_order, load_shortcuts, load_home_widgets, load_home_camera_entity, save_background_image, save_card_theme, save_card_glow, save_room_order, save_security_order, save_shortcuts, save_home_widgets, save_home_camera_entity, save_inherit, save_preset
from .connectors import BusproConnector, Control4MediaConnector, EThermConnector, EkonexMediaConnector, EvoiceLocalMediaConnector, KseniaConnector
from .connectors.ksenia import normalize_ksenia
from .connectors.wiim import WiiMClient
from .connectors.control4_media import cached_control4_icon, cached_control4_icon_path, cached_control4_source_label, control4_icon_path
from .connectors.supervisor import discover_addon_url, discover_host_url
from .demo import dashboard as demo_dashboard

VERSION = os.environ.get("EFACE_VERSION", "2.21.113")
STATIC = Path(__file__).parent / "static"
logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s [e-face-x4] %(message)s")
_reconnect_warning_at: dict[str, float] = {}


def log_reconnect_warning(source: str) -> None:
    """Keep a broken realtime source from flooding Supervisor logs."""
    now = time.monotonic()
    if now - _reconnect_warning_at.get(source, -60.0) >= 60.0:
        _reconnect_warning_at[source] = now
        logging.warning("%s realtime disconnected; retrying", source)


def artwork_media_type(declared: str, content: bytes) -> str:
    media_type = declared.split(";", 1)[0].strip().lower()
    if media_type in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        return media_type
    if media_type not in {"", "application/octet-stream"}:
        return ""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return ""


def wiim_media_fingerprint(snapshot: dict) -> str:
    identity = "|".join(str(snapshot.get(key) or "") for key in ("track_id", "title", "artist", "album", "artwork"))
    return f"wiim-{hashlib.sha256(identity.encode()).hexdigest()[:24]}" if identity.strip("|") else ""


def native_wiim_media_item(snapshot: dict) -> dict:
    name = str(snapshot.get("name") or "WiiM")
    identity = str(snapshot.get("id") or "player")
    return {
        "id": f"wiim:{identity}", "registry_id": f"wiim:{identity}", "entity_id": f"wiim.{identity}",
        "provider": "wiim", "transport_provider": "wiim", "kind": "media_player", "icon": "mdi:speaker-wireless",
        "name": name, "room": name, "state": snapshot.get("state") or "unknown", "availability": "available",
        "connection_status": "online", "volume": snapshot.get("volume"), "muted": bool(snapshot.get("muted")),
        "source": str(snapshot.get("source") or "WiiM"), "wiim_source": str(snapshot.get("source") or "WiiM"), "title": snapshot.get("title"), "artist": snapshot.get("artist"),
        "track_id": snapshot.get("track_id"), "native_artwork": snapshot.get("artwork"),
        "album": snapshot.get("album"), "content_fingerprint": wiim_media_fingerprint(snapshot), "wiim_artwork": bool(snapshot.get("artwork")),
        "active_experience": "listen", "experiences": ["listen"], "source_options": [], "source_list": [],
        "capabilities": {"play": True, "pause": True, "stop": True, "previous": True, "next": True,
                         "turn_off": False, "set_volume": True, "mute": True, "select_source": False,
                         "grouping": False, "artwork": bool(snapshot.get("artwork"))},
    }


def overlay_wiim_on_control4(providers: list[dict], snapshot: dict, source_id: int) -> bool:
    linked = False
    for provider in providers:
        if provider.get("id") != "control4":
            continue
        for item in provider.get("items", []):
            if item.get("kind") != "media_player" or int(item.get("active_source_id") or 0) != source_id:
                continue
            linked = True
            item.update({
                "transport_provider": "wiim", "state": snapshot.get("state") or item.get("state"),
                "title": snapshot.get("title"), "artist": snapshot.get("artist"), "album": snapshot.get("album"),
                "wiim_source": str(snapshot.get("source") or "WiiM"), "track_id": snapshot.get("track_id"),
                "native_artwork": snapshot.get("artwork"),
                "content_fingerprint": wiim_media_fingerprint(snapshot), "wiim_artwork": bool(snapshot.get("artwork")),
            })
            item.setdefault("capabilities", {}).update({"play": True, "pause": True, "stop": True, "previous": True,
                                                        "next": True, "set_volume": True, "mute": True,
                                                        "artwork": bool(snapshot.get("artwork"))})
    return linked


class AppAssets(StaticFiles):
    async def get_response(self, path: str, scope: dict) -> Response:
        if path in {"", ".", "/"}:
            return RedirectResponse("../", status_code=307)
        return await super().get_response(path, scope)


def create_app() -> FastAPI:
    app = FastAPI(title="e-Face X4", version=VERSION, docs_url=None, redoc_url=None)
    app.mount("/assets", AppAssets(directory=STATIC / "assets"), name="assets")
    login_failures: dict[tuple[str, str], list[float]] = {}
    reveal_failures: dict[str, list[float]] = {}
    voip_lock = asyncio.Lock()
    personal_lock = asyncio.Lock()
    push_wake_tokens: dict[str, dict] = {}
    control4_support_tokens: dict[str, float] = {}
    doorbird_video_slots = asyncio.Semaphore(2)
    wiim_presets_cache: dict[str, object] = {"expires": 0.0, "items": []}

    async def sync_default_intercom_group(records: dict | None = None) -> None:
        remote = await provisioner_client.request("GET", "/v1/intercom-groups")
        groups = intercom_groups.with_default(remote.get("groups", []), records)
        if groups != intercom_groups.validate(remote.get("groups", [])):
            await provisioner_client.request("PUT", "/v1/intercom-groups", {"groups": groups})

    def secure_cookie(request: Request) -> bool:
        return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https"

    @app.middleware("http")
    async def user_login_guard(request: Request, call_next):
        path = request.url.path
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and urlsplit(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Origine non consentita"}, status_code=403)
        if not user_auth.enabled() or path in {"/health", "/login", "/service-worker.js"} or path.startswith("/intercom/wake/") or path.startswith("/api/auth/") or path.startswith("/assets/") or path.startswith("/api/support/control4/artwork/"):
            return await call_next(request)
        username = user_auth.session_user(request.cookies.get(user_auth.COOKIE))
        if not username:
            if path.startswith("/api/"):
                return JSONResponse({"detail": "Accesso richiesto"}, status_code=401)
            return RedirectResponse("login", status_code=303)
        return await call_next(request)

    @app.get("/api/auth/status")
    async def auth_status(request: Request) -> dict:
        username = user_auth.session_user(request.cookies.get(user_auth.COOKIE)) if user_auth.enabled() else None
        account = user_auth.account(username) if username else None
        return {"enabled": user_auth.enabled(), "user": username, "name": account["name"] if account else None, "role": account["role"] if account else None}

    def require_admin(request: Request) -> str:
        username = user_auth.session_user(request.cookies.get(user_auth.COOKIE))
        if username != "admin":
            raise HTTPException(status_code=403, detail="Accesso amministratore richiesto")
        return username

    @app.get("/api/admin/startup")
    async def admin_startup_get(request: Request) -> dict:
        require_admin(request)
        return startup_settings.load()

    @app.put("/api/admin/startup")
    async def admin_startup_put(request: Request, payload: dict) -> dict:
        require_admin(request)
        try:
            return startup_settings.save(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/admin/wiim")
    async def admin_wiim(request: Request) -> dict:
        require_admin(request)
        return {"settings": wiim_settings.load()}

    @app.put("/api/admin/wiim")
    async def admin_wiim_save(request: Request) -> dict:
        require_admin(request)
        try:
            candidate = wiim_settings.validate(await request.json())
            device = await WiiMClient(candidate["host"]).snapshot()
            settings = wiim_settings.save(candidate)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="WiiM non raggiungibile") from exc
        return {"settings": settings, "device": device}

    @app.post("/api/admin/wiim/test")
    async def admin_wiim_test(request: Request) -> dict:
        require_admin(request)
        try:
            payload = await request.json()
            device = await WiiMClient(str(payload.get("host") or "")).snapshot()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="WiiM non raggiungibile") from exc
        return {"ok": True, "device": device}

    @app.get("/api/admin/wiim/services")
    async def admin_wiim_services(request: Request) -> dict:
        require_admin(request)
        return {"items": wiim_services.catalog(), "first_provider": "soundcloud"}

    @app.get("/api/admin/wiim/soundcloud")
    async def admin_soundcloud(request: Request) -> dict:
        require_admin(request)
        return {"settings": soundcloud_settings.public()}

    @app.put("/api/admin/wiim/soundcloud")
    async def admin_soundcloud_save(request: Request) -> dict:
        require_admin(request)
        try:
            previous = soundcloud_settings.load()
            saved = soundcloud_settings.save(await request.json())
            SoundCloudClient.clear_token(previous.get("client_id", ""))
            SoundCloudClient.clear_token(saved.get("client_id", ""))
            return {"settings": soundcloud_settings.public()}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def configured_soundcloud() -> SoundCloudClient:
        settings = soundcloud_settings.load()
        return SoundCloudClient(settings["client_id"], settings["client_secret"])

    @app.get("/api/wiim/services/soundcloud/search")
    async def soundcloud_search(request: Request, q: str = "", kind: str = "tracks") -> dict:
        require_admin(request)
        try:
            return {"items": await configured_soundcloud().search(q, kind)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="SoundCloud non raggiungibile o credenziali rifiutate") from exc

    @app.get("/api/wiim/services/soundcloud/collection")
    async def soundcloud_collection(request: Request, urn: str, kind: str) -> dict:
        require_admin(request)
        try:
            client = configured_soundcloud()
            if kind == "playlist":
                items = await client.playlist_tracks(urn)
            elif kind == "user":
                items = await client.user_tracks(urn)
            elif kind == "related":
                items = await client.related_tracks(urn)
            else:
                raise ValueError("Raccolta SoundCloud non valida")
            return {"items": items}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="Contenuto SoundCloud non disponibile") from exc

    @app.post("/api/wiim/services/soundcloud/play")
    async def soundcloud_play(request: Request) -> dict:
        require_admin(request)
        try:
            payload = await request.json()
            stream = await configured_soundcloud().stream(str(payload.get("urn") or ""))
            await configured_wiim().play_url(stream["url"])
            soundcloud_library.remember(payload)
            await asyncio.sleep(0.25)
            return {"ok": True, "quality": stream["quality"], "device": await configured_wiim().snapshot()}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="Riproduzione SoundCloud sul WiiM non riuscita") from exc

    @app.get("/api/wiim/services/soundcloud/library")
    async def soundcloud_local_library() -> dict:
        return soundcloud_library.load()

    @app.post("/api/wiim/services/soundcloud/favorite")
    async def soundcloud_local_favorite(request: Request) -> dict:
        require_admin(request)
        try:
            return soundcloud_library.toggle(await request.json())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/wiim/services/soundcloud/playlists")
    async def soundcloud_playlist_add(request: Request) -> dict:
        try:
            payload = await request.json()
            track = payload.get("track") if isinstance(payload.get("track"), dict) else {}
            if not re.fullmatch(r"soundcloud:tracks:\d+", str(track.get("urn") or "")):
                snapshot = await configured_wiim().snapshot()
                track_id = str(snapshot.get("track_id") or "").strip()
                if not re.fullmatch(r"soundcloud:tracks:\d+", track_id):
                    queue = await configured_wiim().queue(limit=250)
                    title = str(snapshot.get("title") or "").strip().casefold()
                    artist = str(snapshot.get("artist") or "").strip().casefold()
                    current = next((item for item in queue.get("tracks", []) if re.fullmatch(r"soundcloud:tracks:\d+", str(item.get("track_id") or "")) and (not title or str(item.get("title") or "").strip().casefold() == title) and (not artist or str(item.get("artist") or "").strip().casefold() == artist)), None)
                    track_id = str((current or {}).get("track_id") or "")
                track = {"urn": track_id, "title": snapshot.get("title"), "artist": snapshot.get("artist"), "artwork": snapshot.get("artwork"), "duration": snapshot.get("duration"), "type": "track", "playable": True}
            return soundcloud_library.save_to_playlist(str(payload.get("name") or ""), track, str(payload.get("playlist_id") or ""))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="Dati del brano SoundCloud non disponibili dal WiiM") from exc

    @app.delete("/api/wiim/services/soundcloud/playlists/{playlist_id}")
    async def soundcloud_playlist_delete(playlist_id: str) -> dict:
        try: return soundcloud_library.delete_playlist(playlist_id)
        except ValueError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/wiim/services/soundcloud/playlists/{playlist_id}/play")
    async def soundcloud_playlist_play(playlist_id: str) -> dict:
        try:
            playlist = soundcloud_library.playlist(playlist_id)
            tracks = playlist.get("tracks", [])
            if not tracks: raise ValueError("La lista SoundCloud è vuota")
            client = configured_soundcloud()
            try:
                streams = await asyncio.gather(*(client.stream(str(track["urn"])) for track in tracks))
                resolved = list(zip(tracks, streams))
            except httpx.HTTPError:
                # Un account SoundCloud usato nell'app WiiM non espone necessariamente
                # credenziali API. Finche la coda nativa contiene i brani, riutilizziamo
                # gli URL gia risolti dal WiiM invece di perdere la playlist e-Face.
                native_queue = await configured_wiim().queue(limit=250)
                native_by_id = {str(item.get("track_id") or ""): item for item in native_queue.get("tracks", [])}
                resolved = []
                for track in tracks:
                    native = native_by_id.get(str(track["urn"]))
                    url = str((native or {}).get("url") or "").strip()
                    if url: resolved.append((track, {"url": url, "quality": "wiim_queue"}))
                if not resolved and len(tracks) == 1:
                    current = await configured_wiim().snapshot()
                    current_url = str(current.get("title") or "").strip()
                    if str(current.get("source") or "").lower() == "custompushurl" and current_url.startswith("https://"):
                        resolved = [(tracks[0], {"url": current_url, "quality": "wiim_current_stream"})]
                if not resolved:
                    soundcloud_library.delete_playlist(playlist_id)
                    raise HTTPException(status_code=410, detail="Playlist rimossa: nessun brano è più riproducibile")
                soundcloud_library.retain_playlist_tracks(playlist_id, [str(track["urn"]) for track, _ in resolved])
            queue_name = f"e-Face SoundCloud - {playlist['name']}"
            blocks = []
            for index, (track, stream) in enumerate(resolved, 1):
                title, artist, artwork = (escape(str(track.get(key) or "")) for key in ("title", "artist", "artwork"))
                track_id = escape(str(track["urn"]))
                stream_url = escape(stream["url"])
                metadata = f'<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"><item id="{track_id}" parentID="0" restricted="0"><dc:title>{title}</dc:title><upnp:artist>{artist}</upnp:artist><upnp:albumArtURI>{artwork}</upnp:albumArtURI><upnp:class>object.item.audioItem.musicTrack</upnp:class><res protocolInfo="http-get:*:audio/mpeg:*">{stream_url}</res></item></DIDL-Lite>'
                blocks.append(f'<Track{index}><Id>{track_id}</Id><URL>{stream_url}</URL><Metadata>{escape(metadata)}</Metadata><Source>SoundCloud</Source></Track{index}>')
            context = f'<?xml version="1.0"?><PlayList><ListName>{escape(queue_name)}</ListName><ListInfo><QueueVersion>2.0</QueueVersion><SourceName>SoundCloud</SourceName><ContentType>songlist</ContentType><TotalNumber>{len(blocks)}</TotalNumber><TrackNumber>{len(blocks)}</TrackNumber><LastPlayIndex>1</LastPlayIndex><Loop>1</Loop><Shuffle>0</Shuffle></ListInfo><Tracks>{"".join(blocks)}</Tracks></PlayList>'
            await configured_wiim().create_queue(context, queue_name)
            await asyncio.sleep(0.25)
            accepted = await configured_wiim().queue(limit=250)
            if int(accepted.get("total") or 0) != len(blocks) or any(not str(item.get("title") or "").strip() for item in accepted.get("tracks", [])):
                raise RuntimeError("Il WiiM non ha confermato la coda completa")
            # Il firmware puo assegnare alla coda un nome interno (_#~...). Avviare
            # usando il nome descrittivo accetta il SOAP ma lascia il player idle.
            await configured_wiim().play_queue_index(1, str(accepted.get("queue_name") or "0"))
            await configured_wiim().player_action("play")
            await asyncio.sleep(0.35)
            playback = await configured_wiim().snapshot()
            if str(playback.get("state") or "").lower() != "playing":
                if len(resolved) == 1:
                    await configured_wiim().play_url(str(resolved[0][1]["url"]))
                    await asyncio.sleep(1.0)
                    playback = await configured_wiim().snapshot()
                    if str(playback.get("state") or "").lower() == "playing":
                        # CustomPushUrl clears BrowseQueueEx. Reload only the
                        # catalogue after transport starts, without interrupting it.
                        await configured_wiim().load_queue(context)
                        await asyncio.sleep(0.25)
                if str(playback.get("state") or "").lower() != "playing":
                    raise RuntimeError("Il WiiM ha accettato la coda ma non ha avviato la riproduzione")
            return {"ok": True, "playlist": playlist, "count": len(blocks), "total": len(tracks), "skipped": len(tracks) - len(blocks), "pruned": len(tracks) - len(blocks)}
        except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
        except HTTPException: raise
        except (httpx.HTTPError, RuntimeError) as exc: raise HTTPException(status_code=502, detail="Riproduzione lista SoundCloud sul WiiM non riuscita") from exc

    def configured_wiim() -> WiiMClient:
        settings = wiim_settings.load()
        if not settings["enabled"] or not settings["host"]:
            raise HTTPException(status_code=503, detail="WiiM non configurato")
        return WiiMClient(settings["host"])

    @app.get("/api/wiim/snapshot")
    async def wiim_snapshot() -> dict:
        try:
            client = configured_wiim()
            device = await client.snapshot()
            if str(device.get("source") or "").lower() == "custompushurl":
                queue = await client.queue(limit=2)
                items = queue.get("tracks", [])
                if len(items) == 1:
                    track = items[0]
                    device.update({
                        "source": str(track.get("source") or "SoundCloud"),
                        "title": str(track.get("title") or device.get("title") or ""),
                        "artist": str(track.get("artist") or ""),
                        "album": str(track.get("album") or ""),
                        "artwork": str(track.get("artwork") or ""),
                        "track_id": str(track.get("track_id") or ""),
                    })
            return {"device": device}
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="WiiM non raggiungibile") from exc

    @app.get("/api/wiim/eq")
    async def wiim_eq(source: str = "wifi") -> dict:
        try: return await configured_wiim().eq_state(source)
        except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (httpx.HTTPError, RuntimeError) as exc: raise HTTPException(status_code=502, detail="Equalizzatore WiiM non disponibile") from exc

    @app.post("/api/wiim/eq")
    async def wiim_eq_update(payload: dict) -> dict:
        try: return await configured_wiim().set_eq(str(payload.get("source") or "wifi"), str(payload.get("action") or ""), name=str(payload.get("name") or ""), bands=payload.get("bands"))
        except (ValueError, TypeError) as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (httpx.HTTPError, RuntimeError) as exc: raise HTTPException(status_code=502, detail="Modifica equalizzatore WiiM non riuscita") from exc

    @app.get("/api/wiim/queue")
    async def wiim_queue() -> dict:
        try:
            return await configured_wiim().queue(limit=250)
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="Coda WiiM non disponibile") from exc

    @app.post("/api/wiim/queue/play")
    async def wiim_queue_play(payload: dict) -> dict:
        try:
            index = int(payload.get("index") or 0)
            await configured_wiim().play_queue_index(index, str(payload.get("queue_name") or "0"))
            return {"ok": True, "index": index}
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="Brano della coda WiiM non disponibile") from exc

    @app.get("/api/wiim/artwork")
    async def wiim_artwork(fingerprint: str = Query(..., min_length=8, max_length=80)) -> Response:
        try:
            snapshot = await configured_wiim().snapshot()
            if wiim_media_fingerprint(snapshot) != fingerprint or not snapshot.get("artwork"):
                raise HTTPException(status_code=404, detail="Copertina WiiM non più disponibile")
            async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
                upstream = await client.get(str(snapshot["artwork"]))
            media_type = artwork_media_type(upstream.headers.get("content-type", ""), upstream.content)
            if upstream.status_code != 200 or not media_type or len(upstream.content) > 700_000:
                raise HTTPException(status_code=415, detail="Copertina WiiM non valida")
            return Response(upstream.content, media_type=media_type, headers={"Cache-Control": "private, max-age=30", "X-Content-Type-Options": "nosniff"})
        except HTTPException:
            raise
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="Copertina WiiM non raggiungibile") from exc

    @app.get("/api/wiim/presets")
    async def wiim_presets() -> dict:
        try:
            return {"items": await configured_wiim().presets()}
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="Preset WiiM non disponibili") from exc

    @app.delete("/api/wiim/presets/{index}")
    async def wiim_delete_preset(index: int) -> dict:
        try:
            await configured_wiim().delete_preset(index)
            wiim_presets_cache["expires"] = 0.0
            wiim_presets_cache["items"] = []
            return {"ok": True, "index": index}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="Cancellazione preset WiiM non riuscita") from exc

    @app.post("/api/wiim/action")
    async def wiim_action(request: Request) -> dict:
        try:
            payload = await request.json()
            await configured_wiim().player_action(str(payload.get("action") or ""), payload.get("value"))
            return {"ok": True, "device": await configured_wiim().snapshot()}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="Comando WiiM non riuscito") from exc

    @app.post("/api/wiim/presets/{index}")
    async def wiim_play_preset(index: int) -> dict:
        try:
            await configured_wiim().play_preset(index)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="Preset WiiM non avviato") from exc
        return {"ok": True}

    @app.get("/api/wiim/multiroom")
    async def wiim_multiroom() -> dict:
        try:
            return {"multiroom": await configured_wiim().multiroom()}
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="Stato multiroom WiiM non disponibile") from exc

    @app.get("/api/admin/installation/preflight")
    async def admin_installation_preflight(request: Request) -> dict:
        require_admin(request)
        return await installation.preflight()

    @app.get("/api/admin/intercom/composer-guide")
    async def admin_intercom_composer_guide(request: Request) -> Response:
        require_admin(request)
        sip_eface = credential_inventory.load().get("sip_eface", {})
        sip_control4 = credential_inventory.load().get("sip_control4", {})
        tablets = control4_tablets.load()
        active_routes = set()
        if provisioner_client.public()["configured"]:
            try:
                remote = await provisioner_client.request("GET", "/v1/control4-tablets")
                active_routes = {(item["extension"], item["sip_user"]) for item in remote.get("tablets", [])}
            except (RuntimeError, KeyError, TypeError):
                pass
        return JSONResponse({
            "control4": public_control4_config(),
            "asterisk_host": intercom_settings.load()["asterisk_host"],
            "eface_extension": "8301",
            "eface_password_present": sip_eface.get("username") == "8301" and bool(sip_eface.get("password")),
            "eface_password_managed": False,
            "control4_sip_user": sip_control4.get("username", ""),
            "control4_sip_copy_present": bool(sip_control4.get("password")),
            "tablet_aliases": internal_stations.load(),
            "additional_tablets": [{**tablet, "status": "route_present" if (tablet["extension"], tablet["sip_user"]) in active_routes else "pending_route"} for tablet in tablets],
            "asterisk_paired": provisioner_client.public()["configured"],
        }, headers={"Cache-Control": "no-store, private"})

    @app.put("/api/admin/intercom/control4-tablets")
    async def admin_save_control4_tablets(request: Request, payload: dict) -> Response:
        require_admin(request)
        previous_tablets = control4_tablets.load()
        try:
            if set(payload) != {"tablets"}:
                raise ValueError("Elenco tablet non valido")
            tablets = control4_tablets.validate(payload["tablets"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            old_routes = await provisioner_client.request("GET", "/v1/control4-tablets")
            routes = [{"extension": tablet["extension"], "sip_user": tablet["sip_user"]} for tablet in tablets]
            await provisioner_client.request("PUT", "/v1/control4-tablets", {"tablets": routes})
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        try:
            control4_tablets.save(tablets)
            await sync_default_intercom_group()
        except Exception:
            control4_tablets.save(previous_tablets)
            await provisioner_client.request("PUT", "/v1/control4-tablets", {"tablets": old_routes["tablets"]})
            raise
        return JSONResponse({"tablets": [{**tablet, "status": "route_present"} for tablet in tablets]}, headers={"Cache-Control": "no-store, private"})

    async def voip_public() -> list[dict]:
        records = voip_phones.load()
        present = set()
        if records and provisioner_client.public()["configured"]:
            try:
                remote = await provisioner_client.request("GET", "/v1/voip-phones")
                present = {(item["extension"], item["profile"]) for item in remote.get("phones", [])}
            except (RuntimeError, KeyError, TypeError):
                pass
        return [{**phone, "endpoint_present": (phone["extension"], phone["profile"]) in present}
                for phone in voip_phones.public(records)]

    @app.get("/api/admin/intercom/voip-phones")
    async def admin_voip_phones(request: Request) -> Response:
        require_admin(request)
        return JSONResponse({"phones": await voip_public()}, headers={"Cache-Control": "no-store, private"})

    @app.get("/api/intercom/voip-phones")
    async def intercom_voip_phones(request: Request) -> Response:
        if not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        return JSONResponse({"phones": await voip_public()}, headers={"Cache-Control": "no-store, private"})

    @app.post("/api/admin/intercom/voip-phones")
    async def admin_create_voip_phone(request: Request, payload: dict) -> Response:
        require_admin(request)
        if set(payload) != {"name", "profile"}:
            raise HTTPException(status_code=400, detail="Dati telefono non validi")
        async with voip_lock:
            current = voip_phones.load()
            reserved = {str(record.get("extension")) for record in sip_accounts.load().values() if isinstance(record, dict)}
            try:
                extension, record = voip_phones.new_record(payload["name"], payload["profile"], {**current, **dict.fromkeys(reserved)})
            except (ValueError, TypeError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            remote_payload = {"username": f"voip_{extension}", "extension": extension, **record}
            try:
                await provisioner_client.request("POST", "/v1/voip-phones", remote_payload)
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            try:
                voip_phones.save({**current, extension: record})
                await sync_default_intercom_group()
            except Exception:
                voip_phones.save(current)
                await provisioner_client.request("DELETE", f"/v1/voip-phones/voip_{extension}")
                raise
        return JSONResponse({"extension": extension, "username": extension, "password": record["password"],
                             "profile": record["profile"], "endpoint_present": True},
                            headers={"Cache-Control": "no-store, private", "Pragma": "no-cache"})

    @app.put("/api/admin/intercom/voip-phones/{extension}")
    async def admin_update_voip_phone(extension: str, request: Request, payload: dict) -> Response:
        require_admin(request)
        if set(payload) != {"name", "profile"}:
            raise HTTPException(status_code=400, detail="Dati telefono non validi")
        async with voip_lock:
            current = voip_phones.load()
            if extension not in current:
                raise HTTPException(status_code=404, detail="Telefono non trovato")
            old = current[extension]
            new = {**old, "name": payload["name"], "profile": payload["profile"]}
            try:
                voip_phones.validate({extension: new})
                await provisioner_client.request("POST", "/v1/voip-phones", {"username": f"voip_{extension}", "extension": extension, **new})
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            try:
                voip_phones.save({**current, extension: new})
            except Exception:
                await provisioner_client.request("POST", "/v1/voip-phones", {"username": f"voip_{extension}", "extension": extension, **old})
                raise
        return JSONResponse({"extension": extension, "endpoint_present": True}, headers={"Cache-Control": "no-store, private"})

    @app.delete("/api/admin/intercom/voip-phones/{extension}")
    async def admin_delete_voip_phone(extension: str, request: Request) -> Response:
        require_admin(request)
        async with voip_lock:
            current = voip_phones.load()
            if extension not in current:
                raise HTTPException(status_code=404, detail="Telefono non trovato")
            old = current[extension]
            try:
                await provisioner_client.request("DELETE", f"/v1/voip-phones/voip_{extension}")
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            try:
                voip_phones.save({key: value for key, value in current.items() if key != extension})
                await sync_default_intercom_group()
            except Exception:
                voip_phones.save(current)
                await provisioner_client.request("POST", "/v1/voip-phones", {"username": f"voip_{extension}", "extension": extension, **old})
                raise
        return JSONResponse({"removed": True}, headers={"Cache-Control": "no-store, private"})

    @app.post("/api/admin/intercom/voip-phones/{extension}/credentials")
    async def admin_voip_credentials(extension: str, request: Request, payload: dict) -> Response:
        require_admin(request)
        session = request.cookies.get(user_auth.COOKIE, "")
        key = hashlib.sha256(session.encode()).hexdigest()
        now = time.monotonic()
        attempts = [instant for instant in reveal_failures.get(key, []) if now - instant < 900]
        if len(attempts) >= 5:
            raise HTTPException(status_code=429, detail="Troppi tentativi. Riprova più tardi")
        if set(payload) != {"admin_password"} or not user_auth.verify("admin", str(payload["admin_password"])):
            reveal_failures[key] = attempts + [now]
            raise HTTPException(status_code=403, detail="Password admin non valida")
        reveal_failures.pop(key, None)
        record = voip_phones.load().get(extension)
        if record is None:
            raise HTTPException(status_code=404, detail="Telefono non trovato")
        return JSONResponse({"username": extension, "password": record["password"]},
                            headers={"Cache-Control": "no-store, private", "Pragma": "no-cache"})

    @app.get("/api/admin/credentials")
    async def admin_credentials(request: Request) -> Response:
        require_admin(request)
        turn = intercom_settings.load_turn()
        control4 = load_control4_config()
        imported = credential_inventory.load()
        entries = [
            {"kind": "eface_admin", "label": "Admin e-Face", "username": "admin", "configured": True, "managed": True, "revealable": False},
            {"kind": "control4", "label": "Control4", "username": control4["username"], "configured": bool(control4["password"]), "managed": True, "revealable": bool(control4["password"])},
            {"kind": "turn", "label": "TURN / audio remoto", "username": turn["turn_username"], "configured": bool(turn["turn_password"]), "managed": True, "revealable": bool(turn["turn_password"])},
            {"kind": "sip_doorbird", "label": "SIP DoorBird / Asterisk", "username": imported.get("sip_doorbird", {}).get("username", ""), "configured": bool(imported.get("sip_doorbird", {}).get("password")), "managed": False, "revealable": bool(imported.get("sip_doorbird", {}).get("password"))},
            {"kind": "sip_eface", "label": "SIP e-Face 8301", "username": imported.get("sip_eface", {}).get("username", ""), "configured": bool(imported.get("sip_eface", {}).get("password")), "managed": False, "revealable": bool(imported.get("sip_eface", {}).get("password"))},
            {"kind": "sip_control4", "label": "SIP Control4", "username": imported.get("sip_control4", {}).get("username", ""), "configured": bool(imported.get("sip_control4", {}).get("password")), "managed": False, "revealable": bool(imported.get("sip_control4", {}).get("password"))},
            {"kind": "doorbird", "label": "DoorBird amministrazione", "username": imported.get("doorbird", {}).get("username", ""), "configured": bool(imported.get("doorbird", {}).get("password")), "managed": False, "revealable": bool(imported.get("doorbird", {}).get("password"))},
        ]
        return JSONResponse({"credentials": entries}, headers={"Cache-Control": "no-store, private"})

    @app.put("/api/admin/credentials/{kind}")
    async def admin_import_credential(kind: str, request: Request, payload: dict) -> Response:
        require_admin(request)
        if set(payload) != {"username", "password", "confirmed"} or payload["confirmed"] is not True:
            raise HTTPException(status_code=400, detail="Conferma la verifica della credenziale originale")
        try:
            credential_inventory.save(kind, str(payload["username"]), str(payload["password"]))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse({"configured": True, "synchronized": False}, headers={"Cache-Control": "no-store, private"})

    @app.delete("/api/admin/credentials/{kind}")
    async def admin_delete_imported_credential(kind: str, request: Request) -> Response:
        require_admin(request)
        try:
            removed = credential_inventory.delete(kind)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse({"removed": removed, "device_changed": False}, headers={"Cache-Control": "no-store, private"})

    @app.post("/api/admin/credentials/{kind}/reveal")
    async def admin_reveal_credential(kind: str, request: Request, payload: dict) -> Response:
        require_admin(request)
        session = request.cookies.get(user_auth.COOKIE, "")
        key = hashlib.sha256(session.encode()).hexdigest()
        now = time.monotonic()
        attempts = [instant for instant in reveal_failures.get(key, []) if now - instant < 900]
        if len(attempts) >= 5:
            raise HTTPException(status_code=429, detail="Troppi tentativi. Riprova più tardi")
        if set(payload) != {"admin_password"} or not user_auth.verify("admin", str(payload["admin_password"])):
            reveal_failures[key] = attempts + [now]
            raise HTTPException(status_code=403, detail="Password admin non valida")
        reveal_failures.pop(key, None)
        if kind == "turn":
            secret = intercom_settings.load_turn()["turn_password"]
        elif kind == "control4":
            secret = load_control4_config()["password"]
        elif kind in credential_inventory.KINDS:
            secret = credential_inventory.load().get(kind, {}).get("password", "")
        else:
            raise HTTPException(status_code=400, detail="Questa password non può essere mostrata")
        if not secret:
            raise HTTPException(status_code=404, detail="Credenziale non configurata")
        return JSONResponse({"password": secret}, headers={"Cache-Control": "no-store, private", "Pragma": "no-cache", "X-Content-Type-Options": "nosniff"})

    @app.get("/api/admin/users")
    async def admin_users(request: Request) -> dict:
        require_admin(request)
        return {"users": user_auth.accounts()}

    @app.post("/api/admin/users")
    async def admin_create_user(request: Request, payload: dict) -> dict:
        require_admin(request)
        origin = str(payload.get("origin") or "local")
        try:
            user = user_auth.create_account(str(payload.get("username") or ""), str(payload.get("name") or ""), str(payload.get("password") or ""), origin, payload.get("trusted_access") is True)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"user": user}

    @app.patch("/api/admin/users/{username}")
    async def admin_update_user(username: str, request: Request, payload: dict) -> dict:
        require_admin(request)
        if not payload or set(payload) - {"name", "password", "active", "trusted_access"}:
            raise HTTPException(status_code=400, detail="Campi non validi")
        if "active" in payload and not isinstance(payload["active"], bool):
            raise HTTPException(status_code=400, detail="Stato non valido")
        if "name" in payload and not isinstance(payload["name"], str):
            raise HTTPException(status_code=400, detail="Nome non valido")
        if "password" in payload and not isinstance(payload["password"], str):
            raise HTTPException(status_code=400, detail="Password non valida")
        if "trusted_access" in payload and not isinstance(payload["trusted_access"], bool):
            raise HTTPException(status_code=400, detail="Impostazione accesso persistente non valida")
        try:
            user = user_auth.update_account(username, name=payload.get("name"), password=payload.get("password"), active=payload.get("active"), trusted_access=payload.get("trusted_access"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"user": user}

    @app.delete("/api/admin/users/{username}")
    async def admin_delete_user(username: str, request: Request) -> dict:
        require_admin(request)
        if username == "admin":
            raise HTTPException(status_code=400, detail="Non puoi eliminare l'account admin")
        owned_devices = [item for item in personal_devices.load().values() if item.get("owner") == username]
        if owned_devices:
            raise HTTPException(status_code=409, detail="Elimina prima i dispositivi personali associati all'utente")
        sip_record = sip_accounts.load().get(username)
        if sip_record and sip_record.get("provisioned"):
            raise HTTPException(status_code=409, detail="Rimuovi prima l'interno SIP provisionato dall'impianto")
        try:
            user_auth.delete_account(username)
            sip_accounts.remove(username)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"removed": True}

    @app.get("/api/admin/intercom")
    async def admin_intercom(request: Request) -> dict:
        require_admin(request)
        turn = intercom_settings.load_turn()
        return {"settings": intercom_settings.load(), "turn": {"turn_url": turn["turn_url"], "turn_username": turn["turn_username"], "password_configured": bool(turn["turn_password"])}, "sip_ready": False}

    @app.get("/api/intercom/external-stations")
    async def intercom_external_stations(request: Request) -> dict:
        if not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        return {"stations": external_stations.public()}

    @app.get("/api/intercom/internal-stations")
    async def intercom_internal_stations(request: Request) -> dict:
        if not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        tablets = control4_tablets.load()
        active_routes = set()
        if tablets and provisioner_client.public()["configured"]:
            try:
                remote = await provisioner_client.request("GET", "/v1/control4-tablets")
                active_routes = {(item["extension"], item["sip_user"]) for item in remote.get("tablets", [])}
            except (RuntimeError, KeyError, TypeError):
                pass
        return {"names": internal_stations.load(), "tablets": [
            {"extension": tablet["extension"], "name": tablet["name"], "ready": (tablet["extension"], tablet["sip_user"]) in active_routes}
            for tablet in tablets
        ]}

    @app.put("/api/admin/intercom/internal-stations")
    async def admin_save_internal_stations(request: Request, payload: dict) -> dict:
        require_admin(request)
        try:
            if set(payload) != {"names"}:
                raise ValueError("Elenco postazioni interne non valido")
            return {"names": internal_stations.save(payload["names"])}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/admin/intercom/external-stations")
    async def admin_external_stations(request: Request) -> dict:
        require_admin(request)
        return {"stations": external_stations.admin_public()}

    @app.get("/api/admin/intercom/provisioner")
    async def admin_provisioner(request: Request) -> dict:
        require_admin(request)
        return provisioner_client.public()

    @app.put("/api/admin/intercom/provisioner")
    async def admin_save_provisioner(request: Request, payload: dict) -> dict:
        require_admin(request)
        try:
            proposed = provisioner_client.validate(payload)
            await provisioner_client.request("GET", "/v1/external-stations", config=proposed)
            provisioner_client.save(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (OSError, RuntimeError, TimeoutError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return provisioner_client.public()

    @app.put("/api/admin/intercom/external-stations")
    async def admin_save_external_stations(request: Request, payload: dict) -> dict:
        require_admin(request)
        if set(payload) != {"stations"}:
            raise HTTPException(status_code=400, detail="Elenco postazioni non valido")
        try:
            proposed = external_stations.validate(payload["stations"])
            current = external_stations.load()
            if any(not (station["username"] and station["password"]) for station in proposed[1:]):
                raise ValueError("Credenziale API richiesta per ogni nuova postazione")
            new_routes = [{"extension": station["sip_extension"], "host": station["host"]} for station in proposed[1:]]
            old_routes = [{"extension": station["sip_extension"], "host": station["host"]} for station in current[1:]]
            if new_routes or old_routes:
                await provisioner_client.request("GET", "/v1/external-stations")
            changed_doorbirds = []
            try:
                for station in proposed:
                    account = {"username": station["username"], "password": station["password"]}
                    if station["id"] == "ingresso" and not (account["username"] and account["password"]):
                        account = credential_inventory.load().get("doorbird", {})
                    if not account.get("username") or not account.get("password"):
                        raise ValueError(f"Credenziale API mancante per {station['name']}")
                    previous = await doorbird_api.ensure_incoming_sip(
                        station["id"], station["host"], station["http_port"],
                        account["username"], account["password"], intercom_settings.load()["asterisk_host"])
                    if previous is not None:
                        changed_doorbirds.append((station, account, previous))
                if new_routes or old_routes:
                    await provisioner_client.request("PUT", "/v1/external-stations", {"stations": new_routes})
                    for station in proposed[1:]:
                        station["ready"] = True
                external_stations.save(proposed)
            except Exception:
                if new_routes or old_routes:
                    try:
                        await provisioner_client.request("PUT", "/v1/external-stations", {"stations": old_routes})
                    except Exception:
                        logging.exception("Ripristino rotte SIP esterne non riuscito")
                for station, account, previous in reversed(changed_doorbirds):
                    try:
                        await doorbird_api.restore_incoming_sip(
                            station["host"], station["http_port"], account["username"], account["password"], previous)
                    except Exception:
                        logging.exception("Ripristino SIP DoorBird non riuscito")
                raise
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (OSError, RuntimeError, TimeoutError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {"stations": external_stations.admin_public()}

    async def control4_artwork_diagnostic() -> dict:
        config = load_control4_config()
        if not config.get("username") or not config.get("password"):
            raise HTTPException(status_code=409, detail="Control4 non configurato in e-Face")
        connector = Control4MediaConnector(config)
        try:
            snapshot = await connector.snapshot()
        except Exception as exc:
            logging.warning("Diagnostica cover Control4: %s", type(exc).__name__)
            raise HTTPException(status_code=502, detail="Control4 non raggiungibile da e-Face") from exc
        if snapshot.get("status") == "offline":
            raise HTTPException(status_code=502, detail=f"Control4 non raggiungibile da e-Face ({snapshot.get('reason') or 'errore sconosciuto'})")
        results = []
        for player in snapshot.get("items", []):
            if player.get("provider") != "control4" or player.get("state") not in {"playing", "paused"}:
                continue
            registry_id = str(player.get("registry_id") or "")
            fingerprint = str(player.get("content_fingerprint") or "")
            item = {"room": player.get("room"), "title": player.get("title"), "source": player.get("source"), "artwork_host": connector.artwork_host(registry_id, fingerprint) if fingerprint else "", "artwork_origin": connector.artwork_origin(registry_id, fingerprint) if fingerprint else {}, "artwork_status": "missing_metadata" if not fingerprint else "pending"}
            if fingerprint:
                try:
                    upstream = await connector.artwork(registry_id, fingerprint)
                    item["artwork_status"] = upstream.status_code
                    item["content_type"] = upstream.headers.get("content-type", "").split(";", 1)[0]
                    item["detected_content_type"] = artwork_media_type(item["content_type"], upstream.content)
                    item["bytes"] = len(upstream.content)
                except httpx.HTTPError as exc:
                    item["artwork_status"] = type(exc).__name__
            results.append(item)
        return {"players": results}

    @app.post("/api/control4/music/amazon/auth-link")
    @app.post("/api/control4/music/tidal/auth-link")
    @app.post("/api/control4/music/tunein/auth-link")
    async def control4_music_auth_link(request: Request) -> Response:
        if not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        service_name = "TIDAL" if request.url.path.endswith("/tidal/auth-link") else "TuneIn" if request.url.path.endswith("/tunein/auth-link") else "Amazon Music"
        config = load_control4_config()
        if not config.get("username") or not config.get("password"):
            raise HTTPException(status_code=409, detail="Control4 non configurato")
        try:
            director, token = await control4_director(config)
            all_items = await director.get_all_item_info()
        except Exception as exc:
            logging.warning("Login servizio musicale: Director non raggiungibile (%s)", type(exc).__name__)
            raise HTTPException(status_code=502, detail="Controller Control4 non raggiungibile") from exc
        candidates = [item for item in all_items if isinstance(item, dict) and str(item.get("name") or "").casefold() == service_name.casefold() and str(item.get("proxy") or "").lower() == "media_service" and str(item.get("id") or "").isdigit()] if isinstance(all_items, list) else []
        driver = next((item for item in candidates if "deviceOrder" not in item), candidates[0] if candidates else None)
        if not driver:
            raise HTTPException(status_code=404, detail=f"{service_name} non presente nell'impianto")
        driver_id = int(driver["id"])
        found = asyncio.Event()
        link = ""
        armed = False

        def capture(value: object) -> None:
            nonlocal link
            try:
                serialized = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
            except (TypeError, ValueError):
                return
            match = re.search(r"https://link\.ctrl4\.co/[A-Za-z0-9_/-]{1,160}", serialized[:100_000].replace("\\/", "/"))
            if match:
                link = match.group(0)
                found.set()

        async def on_event(_item_id: int, message: object) -> None:
            if armed:
                capture(message)

        socket = C4Websocket(config["host"])
        for item_id in {driver_id, driver_id + 1}:
            socket.add_item_callback(item_id, on_event)
        try:
            await asyncio.wait_for(socket.sio_connect(token), timeout=10)
            armed = True
            try:
                raw = await director.send_post_request(
                    f"/api/v1/items/{driver_id}/commands", "LUA_ACTION",
                    {"ACTION": "GetLinkForAPIAuthentication"}, False,
                )
                capture(raw)
            except Exception:
                if service_name != "TuneIn":
                    raise
            if not found.is_set():
                if service_name == "TuneIn":
                    try:
                        await asyncio.wait_for(found.wait(), timeout=8)
                    except asyncio.TimeoutError:
                        raw = await director.send_post_request(
                            f"/api/v1/items/{driver_id}/commands", "LogInCommand",
                            {"username": "username", "password": "password"}, False,
                        )
                        capture(raw)
                if not found.is_set():
                    await asyncio.wait_for(found.wait(), timeout=17 if service_name == "TuneIn" else 25)
        except asyncio.TimeoutError as exc:
            raise HTTPException(status_code=504, detail=f"Il link {service_name} non è arrivato dal controller; riprova") from exc
        except Exception as exc:
            logging.warning("Login servizio musicale non disponibile (%s)", type(exc).__name__)
            raise HTTPException(status_code=502, detail=f"Generazione link {service_name} non disponibile") from exc
        finally:
            await socket.sio_disconnect()
        return JSONResponse({"url": link}, headers={"Cache-Control": "no-store, private", "Pragma": "no-cache", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"})

    @app.get("/api/control4/music/account-services")
    async def control4_music_account_services(request: Request) -> Response:
        if not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        config = load_control4_config()
        if not config.get("username") or not config.get("password"):
            return JSONResponse({"services": []}, headers={"Cache-Control": "no-store, private"})
        try:
            director, _ = await control4_director(config)
            all_items = await director.get_all_item_info()
        except Exception as exc:
            logging.warning("Elenco servizi musicali non disponibile (%s)", type(exc).__name__)
            raise HTTPException(status_code=502, detail="Servizi Control4 non disponibili") from exc
        by_name: dict[str, dict[str, object]] = {}
        for item in all_items if isinstance(all_items, list) else []:
            if not isinstance(item, dict) or str(item.get("proxy") or "").lower() != "media_service":
                continue
            name = str(item.get("name") or "").strip()
            if not name or not str(item.get("id") or "").isdigit():
                continue
            key = name.casefold()
            if key not in by_name or "deviceOrder" in item:
                by_name[key] = {"name": name, "proxy_id": int(item["id"]), "status": "ready" if key in {"amazon music", "tunein", "spotify connect", "wireless music bridge"} else "test" if key == "tidal" else "external" if key == "shairbridge" else "pending"}
        services = sorted(by_name.values(), key=lambda service: str(service["name"]).casefold())
        return JSONResponse({"services": services}, headers={"Cache-Control": "no-store, private"})

    @app.post("/api/control4/music/tunein/navigate")
    async def control4_tunein_navigate(request: Request, payload: dict) -> Response:
        if not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        try:
            proxy_id, room_id = int(payload.get("proxy_id")), int(payload.get("room_id"))
            if proxy_id <= 0 or room_id <= 0:
                raise ValueError
            director, _ = await control4_director(load_control4_config())
            info = await director.get_item_info(proxy_id)
            source = info[0] if isinstance(info, list) and info else info
            if not isinstance(source, dict) or str(source.get("name") or "").casefold() != "tunein" or source.get("proxy") != "media_service":
                raise ValueError
            tab = str(payload.get("tab") or "Home")
            parent = str(payload.get("parent") or "") or None
            offset = int(payload.get("offset") or 0)
            search = str(payload.get("search") or "")
            if tab == "Settings":
                result = await tunein_settings(proxy_id, room_id)
            elif payload.get("action"):
                result = await tunein_action(proxy_id, room_id, tab, str(payload.get("item_id") or ""), str(payload["action"]))
            else:
                result = await tunein_browse(proxy_id, room_id, tab, parent, offset, search)
            return JSONResponse(result, headers={"Cache-Control": "no-store, private"})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Navigazione TuneIn non valida o voce scaduta") from exc
        except asyncio.TimeoutError as exc:
            raise HTTPException(status_code=504, detail="TuneIn non ha risposto: riprova") from exc
        except HTTPException:
            raise
        except Exception as exc:
            logging.warning("Navigazione TuneIn non disponibile (%s)", type(exc).__name__)
            raise HTTPException(status_code=502, detail="Navigazione TuneIn non disponibile") from exc

    @app.post("/api/control4/music/{service}/navigate")
    async def control4_catalog_navigate(service: str, request: Request, payload: dict) -> Response:
        if service == "bridge":
            if user_auth.enabled() and not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
                raise HTTPException(status_code=401, detail="Accesso richiesto")
            try:
                proxy_id, room_id = int(payload.get("proxy_id") or 0), int(payload.get("room_id") or 0)
                if proxy_id <= 0 or room_id <= 0:
                    raise ValueError("Bridge o stanza non validi")
                director, _ = await control4_director(load_control4_config())
                info = await director.get_item_info(proxy_id)
                source = info[0] if isinstance(info, list) and info else info
                if not isinstance(source, dict) or str(source.get("name") or "").casefold() != "wireless music bridge" or source.get("proxy") != "media_service":
                    raise ValueError("Wireless Music Bridge non disponibile")
                result = await bridge_action(proxy_id, room_id, str(payload.get("item_id") or ""), str(payload["action"])) if payload.get("action") else await bridge_browse(proxy_id, room_id)
                return JSONResponse(result, headers={"Cache-Control": "no-store, private"})
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except asyncio.TimeoutError as exc:
                raise HTTPException(status_code=504, detail="Wireless Music Bridge non ha risposto") from exc
            except HTTPException:
                raise
            except Exception as exc:
                logging.warning("Navigazione Wireless Music Bridge non disponibile (%s)", type(exc).__name__)
                raise HTTPException(status_code=502, detail="Navigazione Wireless Music Bridge non disponibile") from exc
        if service == "spotify":
            if user_auth.enabled() and not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
                raise HTTPException(status_code=401, detail="Accesso richiesto")
            try:
                proxy_id, room_id = int(payload.get("proxy_id")), int(payload.get("room_id"))
                if proxy_id <= 0 or room_id <= 0:
                    raise ValueError
                director, _ = await control4_director(load_control4_config())
                info = await director.get_item_info(proxy_id)
                source = info[0] if isinstance(info, list) and info else info
                if not isinstance(source, dict) or str(source.get("name") or "").casefold() != "spotify connect" or source.get("proxy") != "media_service":
                    raise ValueError
                tab = str(payload.get("tab") or "Presets")
                if tab == "Settings":
                    result = await spotify_settings(proxy_id, room_id)
                elif payload.get("action"):
                    result = await spotify_action(proxy_id, room_id, tab, str(payload.get("item_id") or ""), str(payload["action"]))
                else:
                    result = await spotify_browse(proxy_id, room_id, tab, int(payload.get("offset") or 0))
                return JSONResponse(result, headers={"Cache-Control": "no-store, private"})
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Navigazione Spotify non valida o voce scaduta") from exc
            except asyncio.TimeoutError as exc:
                raise HTTPException(status_code=504, detail="Spotify Connect non ha risposto") from exc
            except HTTPException:
                raise
            except Exception as exc:
                logging.warning("Navigazione Spotify non disponibile (%s)", type(exc).__name__)
                raise HTTPException(status_code=502, detail="Navigazione Spotify non disponibile") from exc
        if service == "stations":
            if user_auth.enabled() and not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
                raise HTTPException(status_code=401, detail="Accesso richiesto")
            try:
                proxy_id, room_id = int(payload.get("proxy_id")), int(payload.get("room_id"))
                if proxy_id <= 0 or room_id <= 0:
                    raise ValueError
                director, _ = await control4_director(load_control4_config())
                info = await director.get_item_info(proxy_id)
                source = info[0] if isinstance(info, list) and info else info
                if not isinstance(source, dict) or str(source.get("name") or "").casefold() != "stations" or source.get("proxy") != "media_service":
                    raise ValueError
                tab = str(payload.get("tab") or "Stations")
                if payload.get("action"):
                    result = await stations_action(proxy_id, room_id, tab, str(payload.get("item_id") or ""), str(payload["action"]))
                else:
                    result = await stations_browse(proxy_id, room_id, tab, str(payload.get("parent") or ""), int(payload.get("offset") or 0))
                return JSONResponse(result, headers={"Cache-Control": "no-store, private"})
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Navigazione Stations non valida o voce scaduta") from exc
            except asyncio.TimeoutError as exc:
                raise HTTPException(status_code=504, detail="Stations non ha risposto: riprova") from exc
            except HTTPException:
                raise
            except Exception as exc:
                logging.warning("Navigazione Stations non disponibile (%s)", type(exc).__name__)
                raise HTTPException(status_code=502, detail="Navigazione Stations non disponibile") from exc
        if service not in {"amazon", "tidal"}:
            raise HTTPException(status_code=404, detail="Servizio non disponibile")
        if user_auth.enabled() and not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        try:
            proxy_id, room_id = int(payload.get("proxy_id")), int(payload.get("room_id"))
            if proxy_id <= 0 or room_id <= 0:
                raise ValueError
            director, _ = await control4_director(load_control4_config())
            info = await director.get_item_info(proxy_id)
            source = info[0] if isinstance(info, list) and info else info
            expected = "amazon music" if service == "amazon" else "tidal"
            if not isinstance(source, dict) or str(source.get("name") or "").casefold() != expected or source.get("proxy") != "media_service":
                raise ValueError
            operation = str(payload.get("operation") or "")
            tab = str(payload.get("tab") or ("Home" if service == "amazon" else "Library"))
            if operation == "tabs":
                result = await catalog_tabs(service, proxy_id, room_id)
            elif tab == "Settings":
                result = await catalog_settings(proxy_id, room_id)
            elif payload.get("action"):
                result = await catalog_action(service, proxy_id, room_id, tab, str(payload.get("item_id") or ""), str(payload["action"]))
            else:
                result = await catalog_browse(service, proxy_id, room_id, tab, str(payload.get("parent") or "") or None,
                                              int(payload.get("offset") or 0), str(payload.get("search") or ""))
            return JSONResponse(result, headers={"Cache-Control": "no-store, private"})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Navigazione servizio non valida o voce scaduta") from exc
        except asyncio.TimeoutError as exc:
            raise HTTPException(status_code=504, detail="Il servizio non ha risposto: riprova") from exc
        except HTTPException:
            raise
        except Exception as exc:
            logging.warning("Navigazione %s non disponibile (%s)", service, type(exc).__name__)
            raise HTTPException(status_code=502, detail="Navigazione servizio non disponibile") from exc

    @app.get("/api/control4/stations/image/{token}")
    async def control4_stations_image(token: str, request: Request) -> Response:
        if user_auth.enabled() and not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        try:
            path = station_artwork_path(token)
            host = load_control4_config()["host"]
            async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
                upstream = await client.get(f"http://{host}{path}")
            content_type = upstream.headers.get("content-type", "").split(";", 1)[0]
            if upstream.status_code != 200 or content_type not in {"image/jpeg", "image/png"} or len(upstream.content) > 500_000:
                raise ValueError
            return Response(upstream.content, media_type=content_type, headers={"Cache-Control": "private, max-age=600", "X-Content-Type-Options": "nosniff"})
        except (ValueError, httpx.HTTPError, KeyError) as exc:
            raise HTTPException(status_code=404, detail="Copertina Stations non disponibile") from exc

    @app.get("/api/control4/stations/catalog-image/{station_id}")
    async def control4_stations_catalog_image(station_id: int) -> Response:
        try:
            path = station_catalog_artwork(station_id)
            host = load_control4_config()["host"]
            async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
                upstream = await client.get(f"http://{host}{path}")
            content_type = upstream.headers.get("content-type", "").split(";", 1)[0]
            if upstream.status_code != 200 or content_type not in {"image/jpeg", "image/png"} or len(upstream.content) > 500_000:
                raise ValueError
            return Response(upstream.content, media_type=content_type, headers={"Cache-Control": "private, max-age=600", "X-Content-Type-Options": "nosniff"})
        except (ValueError, httpx.HTTPError, KeyError) as exc:
            raise HTTPException(status_code=404, detail="Copertina Stations non disponibile") from exc

    @app.get("/api/control4/favorites")
    async def control4_list_favorites() -> dict:
        playlist_items = []
        for playlist in soundcloud_library.load()["playlists"]:
            tracks = playlist.get("tracks", [])
            playlist_items.append({"id": f"soundcloud:playlist:{playlist['id']}", "kind": "soundcloud_playlist", "title": playlist["name"], "subtitle": f"{len(tracks)} brani", "item_type": "Playlist", "service": "SoundCloud", "artwork": str(tracks[0].get("artwork") or "") if tracks else "", "saved_at": float(playlist.get("updated_at") or 0)})
        stored_favorites = list_favorites()
        # Nuovi a sinistra, in un solo ordine cronologico per tutti i servizi.
        # I record storici senza data mantengono il precedente ordine relativo.
        items = playlist_items + stored_favorites
        historical_order = {item.get("id"): index for index, item in enumerate(items)}
        items.sort(key=lambda item: (float(item.get("saved_at") or 0), historical_order.get(item.get("id"), 0)), reverse=True)
        try:
            if time.monotonic() >= float(wiim_presets_cache["expires"]):
                wiim_presets_cache["items"] = await configured_wiim().presets()
                wiim_presets_cache["expires"] = time.monotonic() + 10.0
            for preset in wiim_presets_cache["items"]:
                items.append({"id": f"wiim:preset:{preset['index']}", "kind": "wiim_preset", "title": preset["name"], "subtitle": f"Preset {preset['index']}", "item_type": "Preset", "service": preset.get("source", ""), "artwork": preset.get("artwork", ""), "preset_index": preset["index"]})
        except (HTTPException, httpx.HTTPError, RuntimeError, ValueError):
            pass
        return {"items": items}

    @app.post("/api/control4/favorites/current-station")
    async def control4_toggle_current_station_favorite(payload: dict) -> dict:
        try:
            room_id = int(payload.get("room_id") or 0)
            proxy_id = int(payload.get("proxy_id") or 0)
            if room_id <= 0 or proxy_id <= 0:
                raise ValueError("Stanza o servizio Stations non valido")
            director, _ = await control4_director(load_control4_config())
            source_info = await director.get_item_info(proxy_id)
            source = source_info[0] if isinstance(source_info, list) and source_info else source_info
            if not isinstance(source, dict) or str(source.get("name") or "").casefold() != "stations" or source.get("proxy") != "media_service":
                raise ValueError("Servizio Stations non disponibile")
            value = await director.get_item_variable_value(room_id, "CURRENT MEDIA INFO")
            media = value.get("mediainfo") if isinstance(value, dict) else None
            if not isinstance(media, dict) or str(media.get("mediatypeV2") or "").upper() != "INTERNET_MEDIA":
                raise ValueError("Nessuna stazione Stations attiva")
            identity = station_identity(media.get("mediaid"), media.get("channel"))
            if not identity:
                raise ValueError("Stazione non presente nel catalogo Stations")
            station_id = int(media["mediaid"])
            favorite_id = f"station:{proxy_id}:{station_id}"
            if any(item["id"] == favorite_id for item in list_favorites()):
                return {"items": remove_favorite(favorite_id)}
            return {"items": add_favorite({"id": favorite_id, "kind": "station", "title": identity[0], "subtitle": "", "proxy_id": proxy_id, "station_id": station_id, "genre": "", "artwork": station_media_artwork(station_id, media.get("channel"))})}
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logging.warning("Preferito Stations corrente non disponibile (%s)", type(exc).__name__)
            raise HTTPException(status_code=502, detail="Preferito Stations non disponibile") from exc

    @app.post("/api/control4/favorites/current-spotify-playlist")
    async def control4_toggle_current_spotify_playlist(payload: dict) -> dict:
        try:
            room_id = int(payload.get("room_id") or 0)
            proxy_id = int(payload.get("proxy_id") or 0)
            if room_id <= 0 or proxy_id <= 0:
                raise ValueError("Stanza o servizio Spotify non valido")
            director, _ = await control4_director(load_control4_config())
            source_info = await director.get_item_info(proxy_id)
            source = source_info[0] if isinstance(source_info, list) and source_info else source_info
            if not isinstance(source, dict) or str(source.get("name") or "").casefold() != "spotify connect" or source.get("proxy") != "media_service":
                raise ValueError("Spotify Connect non disponibile")
            media_value = await director.get_item_variable_value(room_id, "CURRENT MEDIA INFO")
            media = media_value.get("mediainfo") if isinstance(media_value, dict) else None
            if not isinstance(media, dict) or str(media.get("medSrcDev") or "") != str(proxy_id):
                raise ValueError("Spotify Connect non è la sorgente attiva nella stanza")
            connector = Control4MediaConnector(load_control4_config())
            history = await connector.recently_played([room_id], 20)
            current = history[0] if history else None
            if not current or current.get("driver_id") != proxy_id or str(current.get("item_type") or "").casefold() != "playlist":
                raise ValueError("Non trovo la playlist Spotify attiva. Apri Spotify Connect e scegli la playlist dai recenti.")
            favorite_id = f"recent:{current['key']}"
            if any(item["id"] == favorite_id for item in list_favorites()):
                return {"items": remove_favorite(favorite_id), "title": current["title"], "added": False}
            favorite = {"id": favorite_id, "kind": "recent", "key": current["key"], "title": current["title"],
                        "subtitle": current["subtitle"], "item_type": "Playlist", "driver_id": proxy_id,
                        "registry_id": current["registry_id"], "content_fingerprint": current["content_fingerprint"]}
            items = add_favorite(favorite)
            if current["content_fingerprint"]:
                try:
                    upstream = await connector.artwork(current["registry_id"], current["content_fingerprint"])
                    if upstream.status_code == 200 and artwork_media_type(upstream.headers.get("content-type", ""), upstream.content) and len(upstream.content) <= 700_000:
                        save_favorite_artwork(favorite_id, upstream.content)
                except (httpx.HTTPError, OSError, ValueError):
                    pass
            return {"items": items, "title": current["title"], "added": True}
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logging.warning("Preferito playlist Spotify corrente non disponibile (%s)", type(exc).__name__)
            raise HTTPException(status_code=502, detail="Preferito playlist Spotify non disponibile") from exc

    @app.post("/api/control4/favorites/current-wiim-track")
    async def control4_toggle_current_wiim_track_favorite() -> dict:
        try:
            client = configured_wiim()
            snapshot, queue, presets = await asyncio.gather(client.snapshot(), client.queue(limit=250), client.presets())
            track_id = str(snapshot.get("track_id") or "").strip()
            track = next((item for item in queue["tracks"] if item["track_id"] == track_id), None)
            if not track:
                raise ValueError("Il brano corrente non è identificabile nella coda WiiM")
            queue_name = str(queue.get("name") or "").strip().casefold()
            preset = next((item for item in presets if str(item.get("name") or "").strip().casefold() == queue_name), None)
            if not preset:
                raise ValueError("La coda corrente non è associata a un preset WiiM")
            identity = f"wiim:track:{preset['index']}:{track_id}"
            if any(item["id"] == identity for item in list_favorites()):
                remove_favorite(identity)
                added = False
            else:
                add_favorite({
                    "id": identity,
                    "kind": "wiim_track",
                    "title": str(track.get("title") or snapshot.get("title") or "Brano WiiM")[:200],
                    "subtitle": str(track.get("artist") or snapshot.get("artist") or "")[:200],
                    "item_type": "Brano preset",
                    "service": str(track.get("source") or snapshot.get("source") or "WiiM")[:80],
                    "artwork": str(track.get("artwork") or snapshot.get("artwork") or "")[:2048],
                    "preset_index": int(preset["index"]),
                    "preset_name": str(preset["name"])[:200],
                    "track_id": track_id[:300],
                    "queue_index": int(track["index"]),
                    "queue_total": int(queue.get("total") or len(queue["tracks"])),
                })
                added = True
            result = await control4_list_favorites()
            return {"items": result["items"], "added": added, "title": track.get("title")}
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="Coda WiiM non disponibile") from exc

    @app.get("/api/control4/favorites/artwork")
    async def control4_favorite_artwork(identity: str = Query(..., min_length=1, max_length=300)) -> Response:
        try:
            item = favorite_by_id(identity)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Preferito non disponibile") from exc
        if item.get("kind") != "recent":
            raise HTTPException(status_code=404, detail="Copertina non disponibile")
        content = load_favorite_artwork(identity)
        if content is None and item.get("registry_id") and item.get("content_fingerprint"):
            try:
                upstream = await Control4MediaConnector(load_control4_config()).artwork(str(item["registry_id"]), str(item["content_fingerprint"]))
                if upstream.status_code == 200 and artwork_media_type(upstream.headers.get("content-type", ""), upstream.content) and len(upstream.content) <= 700_000:
                    content = upstream.content
                    save_favorite_artwork(identity, content)
            except (httpx.HTTPError, OSError, ValueError):
                pass
        media_type = artwork_media_type("", content) if content else ""
        if not media_type:
            raise HTTPException(status_code=404, detail="Copertina non disponibile")
        return Response(content, media_type=media_type, headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"})

    @app.post("/api/control4/favorites/recent")
    async def control4_add_recent_favorite(payload: dict) -> dict:
        key = str(payload.get("key") or "")
        title = str(payload.get("title") or "")
        if not key or len(key) > 256 or not title or len(title) > 200:
            raise HTTPException(status_code=400, detail="Elemento preferito non valido")
        item = {"id": f"recent:{key}", "kind": "recent", "key": key, "title": title,
                "subtitle": str(payload.get("subtitle") or "")[:200], "item_type": str(payload.get("item_type") or "")[:50],
                "driver_id": str(payload.get("driver_id") or "")[:20],
                "registry_id": str(payload.get("registry_id") or "")[:100], "content_fingerprint": str(payload.get("content_fingerprint") or "")[:128]}
        try:
            items = add_favorite(item)
            if item["registry_id"] and item["content_fingerprint"] and load_favorite_artwork(item["id"]) is None:
                try:
                    upstream = await Control4MediaConnector(load_control4_config()).artwork(item["registry_id"], item["content_fingerprint"])
                    if upstream.status_code == 200 and artwork_media_type(upstream.headers.get("content-type", ""), upstream.content) and len(upstream.content) <= 700_000:
                        save_favorite_artwork(item["id"], upstream.content)
                except (httpx.HTTPError, OSError, ValueError):
                    pass
            return {"items": items}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/control4/favorites/remove")
    async def control4_remove_favorite(payload: dict) -> dict:
        try:
            return {"items": remove_favorite(str(payload.get("id") or ""))}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/control4/favorites/select")
    async def control4_select_favorite(payload: dict) -> dict:
        try:
            identity = str(payload.get("id") or "")
            room_id = int(payload.get("room_id") or 0)
            if room_id <= 0:
                raise ValueError("Stanza non valida")
            if identity.startswith("soundcloud:playlist:"):
                playlist_id = identity.removeprefix("soundcloud:playlist:")
                result = await soundcloud_playlist_play(playlist_id)
                source_id = int(wiim_settings.load().get("control4_source_id") or 0)
                if source_id > 0:
                    await Control4MediaConnector(load_control4_config()).command(f"c4room:{room_id}", "select_source", f"listen:{source_id}")
                return {"ok": True, "target": "soundcloud_playlist", "playlist_id": playlist_id, "count": result["count"], "total": result.get("total", result["count"]), "skipped": result.get("skipped", 0), "pruned": result.get("pruned", 0), "room_id": room_id}
            match = re.fullmatch(r"wiim:preset:(\d{1,2})", identity)
            if match:
                preset_index = int(match.group(1))
                source_id = int(wiim_settings.load().get("control4_source_id") or 0)
                if source_id <= 0:
                    raise ValueError("Sorgente WiiM Control4 non configurata")
                await configured_wiim().play_preset(preset_index)
                try:
                    await Control4MediaConnector(load_control4_config()).command(
                        f"c4room:{room_id}", "select_source", f"listen:{source_id}"
                    )
                except Exception as exc:
                    logging.warning("Preset WiiM avviato ma routing Control4 non disponibile (%s)", type(exc).__name__)
                    raise HTTPException(
                        status_code=502,
                        detail="Preset avviato sul WiiM, ma selezione della sorgente Control4 non riuscita",
                    ) from exc
                return {"ok": True, "target": "wiim", "preset_index": preset_index, "room_id": room_id, "control4_source_id": source_id}
            item = favorite_by_id(identity)
            if item["kind"] == "wiim_track":
                client = configured_wiim()
                preset_index = int(item.get("preset_index") or 0)
                source_id = int(wiim_settings.load().get("control4_source_id") or 0)
                if not 1 <= preset_index <= 12 or source_id <= 0:
                    raise ValueError("Preferito WiiM non valido")
                presets = await client.presets()
                preset = next((entry for entry in presets if int(entry.get("index") or 0) == preset_index), None)
                if not preset:
                    raise ValueError("Il preset WiiM collegato a questo preferito non esiste più")
                await client.play_preset(preset_index)
                # Cloud presets can be regenerated without the saved track. Keep playback paused
                # until its stable provider ID is found; never leave an unrelated first item playing.
                await client.player_action("pause")
                await Control4MediaConnector(load_control4_config()).command(
                    f"c4room:{room_id}", "select_source", f"listen:{source_id}"
                )
                wanted = str(item.get("track_id") or "")
                expected_name = str(preset.get("name") or item.get("preset_name") or "").strip().casefold()
                saved_total = max(0, int(item.get("queue_total") or 0))
                minimum_total = 1 if saved_total == 1 else 2
                found = None
                queue = None
                for _ in range(30):
                    await asyncio.sleep(0.5)
                    queue = await client.queue(limit=250)
                    queue_name = str(queue.get("name") or "").strip().casefold()
                    candidate = next((track for track in queue["tracks"] if track["track_id"] == wanted), None)
                    if queue_name == expected_name and int(queue.get("total") or 0) >= minimum_total and candidate:
                        found = candidate
                        break
                if not found:
                    if queue and int(queue.get("total") or 0) < minimum_total:
                        raise ValueError("La coda completa del preset WiiM non è stata caricata; riprova tra pochi secondi")
                    raise ValueError("Il provider ha rigenerato il preset: il brano salvato non è attualmente presente")
                queue_name = str(queue.get("queue_name") or queue.get("name") or "0")
                await client.play_queue_index(int(found["index"]), queue_name)
                return {"ok": True, "target": "wiim_track", "preset_index": preset_index, "queue_index": int(found["index"]), "queue_total": int(queue.get("total") or 0), "room_id": room_id}
            if item["kind"] == "recent":
                return await Control4MediaConnector(load_control4_config()).select_recent(room_id, str(item["key"]))
            proxy_id = int(item["proxy_id"])
            director, _ = await control4_director(load_control4_config())
            info = await director.get_item_info(proxy_id)
            source = info[0] if isinstance(info, list) and info else info
            expected = {"station": "stations", "tunein": "tunein", "amazon": "amazon music", "tidal": "tidal", "spotify": "spotify connect"}.get(item["kind"] if item["kind"] == "station" else item.get("service"))
            if not isinstance(source, dict) or str(source.get("name") or "").casefold() != expected or source.get("proxy") != "media_service":
                raise ValueError("Servizio del preferito non disponibile")
            from .control4_msp import _command
            if item["kind"] == "station":
                await _command(proxy_id, room_id, "selectStation", {"id": int(item["station_id"]), "genre": str(item.get("genre") or "")}, wait_response=False)
            elif item["service"] == "spotify":
                command = str(item.get("play_command") or "")
                if command not in {"PresetPlay", "PlayRecent"}:
                    raise ValueError("Preferito Spotify non valido")
                fields = {key: str(value)[:2048] for key, value in item.get("play_args", {}).items() if key in {"blob", "title", "subtitle", "uri", "imageurl", "user"} and isinstance(value, (str, int))}
                if not fields.get("blob") and not fields.get("uri"):
                    raise ValueError("Preferito Spotify non valido")
                await _command(proxy_id, room_id, command, {**fields, "extraRooms": ""}, wait_response=False)
            elif item["service"] == "tunein":
                fields = {key: str(value)[:2048] for key, value in item.get("play_args", {}).items() if key in {"Type", "ContainerType", "Title", "Subtitle", "GuideId", "Image", "Url"} and isinstance(value, (str, int))}
                fields.update({"screenId": "BrowseScreen", "tabId": str(item.get("tab") or "Home")})
                if not fields.get("GuideId") and not fields.get("Url"):
                    raise ValueError("Preferito TuneIn non valido")
                await _command(proxy_id, room_id, "Play", fields, wait_response=False)
            else:
                fields = {key: str(value)[:512] for key, value in item.get("play_args", {}).items() if key in {"id", "itemType"} and isinstance(value, (str, int))}
                if not fields.get("id"):
                    raise ValueError("Preferito non valido")
                await _command(proxy_id, room_id, "Play", {**fields, "playOption": "NOW"}, wait_response=False)
            return {"ok": True}
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except asyncio.TimeoutError as exc:
            raise HTTPException(status_code=504, detail="Il preferito non ha risposto") from exc
        except HTTPException:
            raise
        except Exception as exc:
            logging.warning("Riproduzione preferito non disponibile (%s)", type(exc).__name__)
            raise HTTPException(status_code=502, detail="Riproduzione preferito non disponibile") from exc

    @app.get("/api/admin/control4/artwork-diagnostic")
    async def admin_control4_artwork_diagnostic(request: Request) -> dict:
        require_admin(request)
        return await control4_artwork_diagnostic()

    @app.post("/api/admin/control4/artwork-support-link")
    async def admin_control4_artwork_support_link(request: Request) -> Response:
        require_admin(request)
        control4_support_tokens.clear()
        token = secrets.token_urlsafe(32)
        control4_support_tokens[token] = time.monotonic() + 600
        return JSONResponse({"path": f"/api/support/control4/artwork/{token}", "expires_seconds": 600}, headers={"Cache-Control": "no-store, private"})

    @app.get("/api/support/control4/artwork/{token}")
    async def control4_artwork_support(token: str) -> Response:
        expires = control4_support_tokens.pop(token, 0)
        if expires < time.monotonic():
            raise HTTPException(status_code=404, detail="Link diagnostico scaduto o già usato")
        result = await control4_artwork_diagnostic()
        return JSONResponse(result, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"})

    @app.put("/api/admin/intercom/turn")
    async def admin_save_intercom_turn(request: Request, payload: dict) -> dict:
        require_admin(request)
        try:
            if not payload.get("turn_password") and payload.get("turn_url"):
                payload = {**payload, "turn_password": intercom_settings.load_turn()["turn_password"]}
            value = intercom_settings.save_turn(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"turn_url": value["turn_url"], "turn_username": value["turn_username"], "password_configured": bool(value["turn_password"])}

    @app.get("/api/intercom/ice")
    async def intercom_ice(request: Request) -> dict:
        if not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        turn = intercom_settings.load_turn()
        if not all(turn.values()):
            return {"iceServers": []}
        return {"iceServers": [{"urls": turn["turn_url"], "username": turn["turn_username"], "credential": turn["turn_password"]}]}

    @app.get("/api/intercom/sip/credential")
    async def intercom_sip_credential(request: Request) -> Response:
        username = user_auth.session_user(request.cookies.get(user_auth.COOKIE))
        if not username:
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        if username == "admin":
            account = credential_inventory.load().get("sip_eface", {})
            if account.get("username") != "8301" or not account.get("password"):
                raise HTTPException(status_code=409, detail="Credenziale SIP 8301 non configurata in Credenziali impianto")
            extension, password = "8301", account["password"]
        else:
            account = sip_accounts.load().get(username, {})
            if not account.get("provisioned"):
                raise HTTPException(status_code=409, detail="Interno personale non ancora attivato su Asterisk")
            extension, password = account["extension"], account["password"]
        return JSONResponse(
            {"username": extension, "password": password},
            headers={"Cache-Control": "no-store, private", "Pragma": "no-cache", "Vary": "Cookie", "X-Content-Type-Options": "nosniff"},
        )

    @app.post("/api/intercom/sip/personal-device")
    async def personal_device_credential(request: Request, payload: dict) -> Response:
        owner = user_auth.session_user(request.cookies.get(user_auth.COOKIE))
        if not owner or owner == "admin" or not user_auth.account(owner)["active"]:
            raise HTTPException(status_code=403, detail="Utente personale attivo richiesto")
        if not {"device_id", "name"}.issubset(payload) or set(payload) - {"device_id", "name", "device_type", "video_capable"} or payload.get("device_type", "desktop") not in {"phone", "tablet", "desktop"} or not isinstance(payload.get("video_capable", False), bool):
            raise HTTPException(status_code=400, detail="Dati dispositivo non validi")
        device_id, name = payload["device_id"], payload["name"]
        try:
            personal_devices.validate_id(device_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if device_id in personal_devices.revoked():
            raise HTTPException(status_code=403, detail="Dispositivo revocato in Admin")
        async with personal_lock:
            records = personal_devices.load()
            existing = records.get(device_id)
            if existing and existing["owner"] != owner:
                raise HTTPException(status_code=403, detail="Dispositivo assegnato a un altro utente")
            if existing:
                record = {**existing, "video_capable": existing.get("video_capable", False) or payload.get("video_capable", False)}
                if record["video_capable"] and not existing.get("video_capable", False):
                    record["video_enabled"] = True
            else:
                reserved = {str(item.get("extension")) for item in sip_accounts.load().values() if isinstance(item, dict)}
            username = personal_devices.asterisk_username(device_id)
            while True:
                if not existing:
                    try:
                        record = personal_devices.new_record(device_id, owner, name, records, reserved, payload.get("device_type", "desktop"))
                        record["video_capable"] = payload.get("video_capable", False)
                        record["video_enabled"] = record["video_capable"]
                    except (ValueError, TypeError) as exc:
                        raise HTTPException(status_code=409, detail=str(exc)) from exc
                try:
                    await provisioner_client.request("POST", "/v1/phones", {
                        "username": username, "extension": record["extension"],
                        "password": record["password"], "name": record["name"],
                    })
                    break
                except RuntimeError as exc:
                    if not existing and "già assegnato" in str(exc):
                        reserved.add(record["extension"])
                        continue
                    raise HTTPException(status_code=503, detail=str(exc)) from exc
            if not existing:
                try:
                    updated_records = {**records, device_id: record}
                    await sync_default_intercom_group(updated_records)
                    personal_devices.save(updated_records)
                except Exception:
                    await provisioner_client.request("DELETE", f"/v1/phones/{username}")
                    raise
            else:
                updated_records = {**records, device_id: record}
                personal_devices.save(updated_records)
                await sync_default_intercom_group(updated_records)
        return JSONResponse({"username": record["extension"], "password": record["password"], "name": record["name"], **personal_devices.preferences(record)},
                            headers={"Cache-Control": "no-store, private", "Pragma": "no-cache", "Vary": "Cookie", "X-Content-Type-Options": "nosniff"})

    @app.get("/api/intercom/personal-device/{device_id}/preferences")
    async def personal_device_preferences(device_id: str, request: Request) -> Response:
        owner = user_auth.session_user(request.cookies.get(user_auth.COOKIE))
        record = personal_devices.load().get(device_id)
        if not owner or not record or record["owner"] != owner:
            raise HTTPException(status_code=404, detail="Dispositivo personale non trovato")
        return JSONResponse({"device_id": device_id, "name": record["name"], **personal_devices.preferences(record)}, headers={"Cache-Control": "no-store, private"})

    @app.put("/api/intercom/personal-device/{device_id}/preferences")
    async def update_personal_device_preferences(device_id: str, request: Request, payload: dict) -> Response:
        owner = user_auth.session_user(request.cookies.get(user_auth.COOKIE))
        required_preferences = {"name", "ringtone", "ring_volume", "vibration", "silent"}
        optional_preferences = {"dnd", "video_enabled", "camera_facing"}
        if not required_preferences.issubset(payload) or set(payload) - required_preferences - optional_preferences:
            raise HTTPException(status_code=400, detail="Impostazioni dispositivo non valide")
        async with personal_lock:
            records = personal_devices.load()
            old = records.get(device_id)
            if not owner or not old or old["owner"] != owner:
                raise HTTPException(status_code=404, detail="Dispositivo personale non trovato")
            new = {**old, **payload, "dnd": payload.get("dnd", old.get("dnd", False))}
            try:
                personal_devices.validate({device_id: new})
                await provisioner_client.request("POST", "/v1/phones", {
                    "username": personal_devices.asterisk_username(device_id), "extension": new["extension"],
                    "password": new["password"], "name": new["name"],
                })
                personal_devices.save({**records, device_id: new})
                if new["dnd"] != old.get("dnd", False):
                    await sync_default_intercom_group({**records, device_id: new})
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except RuntimeError as exc:
                if personal_devices.load().get(device_id) == new:
                    personal_devices.save(records)
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        return JSONResponse({"device_id": device_id, "name": new["name"], **personal_devices.preferences(new)}, headers={"Cache-Control": "no-store, private"})

    @app.get("/api/intercom/personal-devices")
    async def intercom_personal_devices(request: Request) -> Response:
        if not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        return JSONResponse({"devices": personal_devices.public(personal_devices.load())}, headers={"Cache-Control": "no-store, private"})

    @app.get("/api/intercom/push/key")
    async def intercom_push_key(request: Request) -> Response:
        if not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        _, public_key = await asyncio.to_thread(push_notifications.keys)
        return JSONResponse({"public_key": public_key}, headers={"Cache-Control": "no-store, private"})

    @app.put("/api/intercom/push/subscription/{device_id}")
    async def intercom_push_subscribe(device_id: str, request: Request, payload: dict) -> Response:
        owner = user_auth.session_user(request.cookies.get(user_auth.COOKIE))
        device = personal_devices.load().get(device_id)
        if not owner or not device or device["owner"] != owner:
            raise HTTPException(status_code=404, detail="Dispositivo personale non trovato")
        try:
            subscription = push_notifications.validate(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        values = push_notifications.load()
        values[device_id] = {"owner": owner, "extension": device["extension"], "subscription": subscription}
        push_notifications.save(values)
        return JSONResponse({"enabled": True}, headers={"Cache-Control": "no-store, private"})

    @app.delete("/api/intercom/push/subscription/{device_id}")
    async def intercom_push_unsubscribe(device_id: str, request: Request) -> Response:
        owner = user_auth.session_user(request.cookies.get(user_auth.COOKIE))
        values = push_notifications.load()
        current = values.get(device_id)
        if not owner or not current or current.get("owner") != owner:
            raise HTTPException(status_code=404, detail="Sottoscrizione non trovata")
        values.pop(device_id)
        push_notifications.save(values)
        return JSONResponse({"enabled": False}, headers={"Cache-Control": "no-store, private"})

    @app.post("/api/intercom/push/call/{extension}")
    async def intercom_push_call(extension: str, request: Request) -> Response:
        caller = user_auth.session_user(request.cookies.get(user_auth.COOKIE))
        if not caller or not re.fullmatch(r"(?:828[0-9]|8290|83(?:0[2-9]|[1-4][0-9]))", extension):
            raise HTTPException(status_code=403, detail="Chiamata push non autorizzata")
        target_extensions = {extension}
        if extension.startswith("828") or extension == "8290":
            try:
                remote = await provisioner_client.request("GET", "/v1/intercom-groups")
                group = next((item for item in intercom_groups.with_default(remote.get("groups", [])) if item["extension"] == extension), None)
                target_extensions = {member for member in (group or {}).get("members", []) if member.startswith("83")}
            except RuntimeError:
                target_extensions = set()
        targets = [(device_id, item) for device_id, item in push_notifications.load().items() if item.get("extension") in target_extensions]
        for key, value in list(push_wake_tokens.items()):
            if value["expires"] < time.monotonic():
                push_wake_tokens.pop(key, None)
        sent = 0
        for device_id, item in targets:
            token = secrets.token_urlsafe(32)
            push_wake_tokens[token] = {"owner": item["owner"], "caller": user_auth.account(caller)["name"], "expires": time.monotonic() + 120}
            ok = await asyncio.to_thread(push_notifications.send, item["subscription"], {
                "title": "Chiamata Intercom", "body": f"Chiamata da {user_auth.account(caller)['name']}",
                "caller": user_auth.account(caller)["name"], "extension": item["extension"], "target": f"intercom/wake/{token}",
            })
            if ok:
                sent += 1
            else:
                push_wake_tokens.pop(token, None)
        return JSONResponse({"sent": sent}, headers={"Cache-Control": "no-store, private"})

    @app.get("/intercom/wake/{token}", include_in_schema=False)
    async def intercom_push_wake(token: str, request: Request) -> Response:
        wake = push_wake_tokens.pop(token, None)
        if not wake or wake["expires"] < time.monotonic():
            return RedirectResponse("/login", status_code=303)
        account = user_auth.account(wake["owner"])
        if not account or account.get("active") is False:
            return RedirectResponse("/login", status_code=303)
        lifetime = user_auth.TRUSTED_DEVICE_SECONDS if account.get("trusted_access") else user_auth.SESSION_SECONDS
        caller = str(wake.get("caller") or "")
        response = RedirectResponse(f"/intercom?push=1&from={quote(caller, safe='')}", status_code=303)
        response.set_cookie(user_auth.COOKIE, user_auth.create_session(wake["owner"], lifetime), max_age=lifetime,
                            expires=datetime.now(timezone.utc) + timedelta(seconds=lifetime),
                            httponly=True, samesite="lax", secure=secure_cookie(request), path="/")
        return response

    @app.get("/api/admin/intercom/personal-devices")
    async def admin_personal_devices(request: Request) -> Response:
        require_admin(request)
        return JSONResponse({"devices": personal_devices.public(personal_devices.load())}, headers={"Cache-Control": "no-store, private"})

    @app.get("/api/admin/intercom/groups")
    async def admin_intercom_groups(request: Request) -> Response:
        require_admin(request)
        remote = await provisioner_client.request("GET", "/v1/intercom-groups")
        groups = intercom_groups.with_default(remote.get("groups", []))
        return JSONResponse({"groups": groups, "members": intercom_groups.available_members()}, headers={"Cache-Control":"no-store, private"})

    @app.get("/api/intercom/groups")
    async def public_intercom_groups(request: Request) -> Response:
        if not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        remote = await provisioner_client.request("GET", "/v1/intercom-groups")
        return JSONResponse({"groups": intercom_groups.with_default(remote.get("groups", []))}, headers={"Cache-Control":"no-store, private"})

    @app.put("/api/admin/intercom/groups")
    async def admin_save_intercom_groups(request: Request, payload: dict) -> Response:
        require_admin(request)
        if set(payload) != {"groups"}: raise HTTPException(status_code=400, detail="Elenco gruppi non valido")
        try:
            groups = intercom_groups.with_default(payload["groups"])
            result = await provisioner_client.request("PUT", "/v1/intercom-groups", {"groups": groups})
        except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc: raise HTTPException(status_code=503, detail=str(exc)) from exc
        return JSONResponse({"groups": result["groups"]}, headers={"Cache-Control":"no-store, private"})

    @app.put("/api/admin/intercom/personal-devices/{device_id}")
    async def admin_rename_personal_device(device_id: str, request: Request, payload: dict) -> Response:
        require_admin(request)
        if set(payload) != {"name"}:
            raise HTTPException(status_code=400, detail="Nome dispositivo non valido")
        async with personal_lock:
            records = personal_devices.load()
            if device_id not in records:
                raise HTTPException(status_code=404, detail="Dispositivo non trovato")
            old = records[device_id]
            new = {**old, "name": payload["name"]}
            try:
                personal_devices.validate({device_id: new})
                await provisioner_client.request("POST", "/v1/phones", {
                    "username": personal_devices.asterisk_username(device_id), "extension": new["extension"],
                    "password": new["password"], "name": new["name"],
                })
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            try:
                personal_devices.save({**records, device_id: new})
            except Exception:
                await provisioner_client.request("POST", "/v1/phones", {
                    "username": personal_devices.asterisk_username(device_id), "extension": old["extension"],
                    "password": old["password"], "name": old["name"],
                })
                raise
        return JSONResponse({"device_id": device_id, "name": new["name"]}, headers={"Cache-Control": "no-store, private"})

    @app.delete("/api/admin/intercom/personal-devices/{device_id}")
    async def admin_revoke_personal_device(device_id: str, request: Request) -> Response:
        require_admin(request)
        async with personal_lock:
            records = personal_devices.load()
            if device_id not in records:
                raise HTTPException(status_code=404, detail="Dispositivo non trovato")
            old = records[device_id]
            username = personal_devices.asterisk_username(device_id)
            personal_devices.revoke_id(device_id)
            try:
                await provisioner_client.request("DELETE", f"/v1/phones/{username}")
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            try:
                updated_records = {key: value for key, value in records.items() if key != device_id}
                await sync_default_intercom_group(updated_records)
                personal_devices.save(updated_records)
            except Exception:
                await provisioner_client.request("POST", "/v1/phones", {
                    "username": username, "extension": old["extension"],
                    "password": old["password"], "name": old["name"],
                })
                raise
        return JSONResponse({"removed": True}, headers={"Cache-Control": "no-store, private"})

    @app.get("/api/admin/intercom/sip/accounts")
    async def admin_sip_accounts(request: Request) -> dict:
        require_admin(request)
        assigned = sip_accounts.load()
        return {"users": [{**user, "extension": assigned.get(user["username"], {}).get("extension"), "provisioned": bool(assigned.get(user["username"], {}).get("provisioned"))} for user in user_auth.accounts() if user["username"] != "admin"]}

    @app.post("/api/admin/intercom/sip/accounts/{username}")
    async def admin_allocate_sip(username: str, request: Request, payload: dict) -> Response:
        require_admin(request)
        session = request.cookies.get(user_auth.COOKIE, "")
        key = hashlib.sha256(session.encode()).hexdigest()
        now = time.monotonic()
        attempts = [instant for instant in reveal_failures.get(key, []) if now - instant < 900]
        if len(attempts) >= 5:
            raise HTTPException(status_code=429, detail="Troppi tentativi. Riprova più tardi")
        if set(payload) != {"admin_password"} or not user_auth.verify("admin", str(payload["admin_password"])):
            reveal_failures[key] = attempts + [now]
            raise HTTPException(status_code=403, detail="Password admin non valida")
        reveal_failures.pop(key, None)
        user = user_auth.account(username)
        if not user or username == "admin" or not user["active"]:
            raise HTTPException(status_code=404, detail="Utente attivo non trovato")
        try:
            record = sip_accounts.allocate(username)
            stanza = sip_accounts.asterisk_stanza(record["extension"], record["password"], user["name"])
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return JSONResponse({"extension": record["extension"], "provisioned": record["provisioned"], "asterisk_config": stanza}, headers={"Cache-Control": "no-store, private"})

    @app.put("/api/admin/intercom/sip/accounts/{username}/provisioned")
    async def admin_confirm_sip(username: str, request: Request, payload: dict) -> dict:
        require_admin(request)
        if set(payload) != {"provisioned"} or not isinstance(payload["provisioned"], bool):
            raise HTTPException(status_code=400, detail="Conferma non valida")
        if not user_auth.account(username) or username == "admin":
            raise HTTPException(status_code=404, detail="Utente non trovato")
        try:
            record = sip_accounts.mark_provisioned(username, payload["provisioned"])
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"extension": record["extension"], "provisioned": record["provisioned"]}

    @app.post("/api/admin/intercom/doorbird/check")
    async def admin_check_doorbird(request: Request) -> Response:
        require_admin(request)
        account = credential_inventory.load().get("doorbird", {})
        if not account.get("username") or not account.get("password"):
            raise HTTPException(status_code=409, detail="Credenziale amministrazione DoorBird non configurata")
        settings = intercom_settings.load()
        result = await doorbird_api.check_identity(settings["doorbird_host"], settings["doorbird_port"], account["username"], account["password"])
        return JSONResponse(result, headers={"Cache-Control": "no-store, private"})

    def external_access(station_id: str) -> tuple[dict, dict]:
        station = external_stations.get(station_id)
        if station is None:
            raise HTTPException(status_code=404, detail="Postazione esterna non trovata")
        account = {"username": station.get("username", ""), "password": station.get("password", "")}
        if station_id == "ingresso" and not (account["username"] and account["password"]):
            account = credential_inventory.load().get("doorbird", {})
        if not account.get("username") or not account.get("password"):
            raise HTTPException(status_code=409, detail="Credenziale postazione esterna non configurata")
        return station, account

    async def home_assistant_get(path: str) -> httpx.Response:
        token = str(os.environ.get("SUPERVISOR_TOKEN") or "").strip()
        if not token: raise HTTPException(status_code=503, detail="Home Assistant non disponibile")
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            response = await client.get(f"http://supervisor/core/api/{path.lstrip('/')}", headers={"Authorization": f"Bearer {token}"})
        if response.status_code != 200: raise HTTPException(status_code=502, detail="Dato Home Assistant non disponibile")
        return response

    @app.get("/api/home/weather")
    async def home_weather() -> Response:
        response = await home_assistant_get("states")
        states = response.json()
        weather = next((item for item in states if str(item.get("entity_id", "")).startswith("weather.")), None)
        if not weather: raise HTTPException(status_code=404, detail="Entità meteo non trovata")
        attributes = weather.get("attributes") or {}
        return JSONResponse({"entity_id": weather["entity_id"], "state": weather.get("state"), "name": attributes.get("friendly_name") or "Meteo", "temperature": attributes.get("temperature"), "temperature_unit": attributes.get("temperature_unit") or "°C", "humidity": attributes.get("humidity"), "wind_speed": attributes.get("wind_speed"), "wind_speed_unit": attributes.get("wind_speed_unit")}, headers={"Cache-Control":"no-store, private"})

    @app.get("/api/home/camera-event")
    async def home_camera_event() -> Response:
        response = await home_assistant_get(f"camera_proxy/{load_home_camera_entity()}")
        return Response(response.content, media_type=response.headers.get("content-type", "image/jpeg"), headers={"Cache-Control":"no-store, private"})

    @app.get("/api/home/doorbird/{event}")
    async def home_doorbird_event(event: str) -> Response:
        station, account = external_access("ingresso")
        try: content = await doorbird_api.history_image(station["host"], station["http_port"], account["username"], account["password"], event)
        except (ValueError, PermissionError, ConnectionError, RuntimeError) as exc: raise HTTPException(status_code=502, detail=str(exc)) from exc
        if content is None: raise HTTPException(status_code=404, detail="Evento DoorBird non disponibile")
        return Response(content, media_type="image/jpeg", headers={"Cache-Control":"no-store, private"})

    @app.post("/api/intercom/external-stations/{station_id}/prepare-call")
    async def intercom_prepare_external_call(request: Request, station_id: str) -> dict:
        if not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        station, account = external_access(station_id)
        if not station["ready"]:
            raise HTTPException(status_code=409, detail="Rotta SIP della postazione non attiva")
        try:
            await doorbird_api.ensure_incoming_sip(
                station["id"], station["host"], station["http_port"], account["username"],
                account["password"], intercom_settings.load()["asterisk_host"])
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (OSError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {"ready": True, "extension": station["sip_extension"]}

    @app.get("/api/intercom/doorbird/image")
    @app.get("/api/intercom/external-stations/{station_id}/image")
    async def intercom_doorbird_image(request: Request, station_id: str = "ingresso") -> Response:
        if not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        station, account = external_access(station_id)
        try:
            frame = await doorbird_api.live_image(
                station["host"], station["http_port"], account["username"], account["password"]
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (ConnectionError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        headers = {"Cache-Control": "no-store, private", "Pragma": "no-cache", "X-Content-Type-Options": "nosniff"}
        if frame is None:
            return Response(status_code=204, headers=headers)
        return Response(content=frame, media_type="image/jpeg", headers=headers)

    @app.get("/api/intercom/doorbird/video")
    @app.get("/api/intercom/external-stations/{station_id}/video")
    async def intercom_doorbird_video(request: Request, station_id: str = "ingresso") -> Response:
        if not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        station, account = external_access(station_id)
        try:
            await asyncio.wait_for(doorbird_video_slots.acquire(), timeout=0.1)
        except asyncio.TimeoutError as exc:
            raise HTTPException(status_code=503, detail="Troppi flussi DoorBird aperti") from exc
        try:
            stream = await doorbird_api.live_video(
                station["host"], station["http_port"], account["username"], account["password"]
            )
        except PermissionError as exc:
            doorbird_video_slots.release()
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (ConnectionError, RuntimeError) as exc:
            doorbird_video_slots.release()
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except BaseException:
            doorbird_video_slots.release()
            raise
        if stream is None:
            doorbird_video_slots.release()
            return Response(status_code=204, headers={"Cache-Control": "no-store, private"})
        client, upstream, content_type = stream

        async def frames():
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
            finally:
                await upstream.aclose()
                await client.aclose()
                doorbird_video_slots.release()

        return StreamingResponse(
            frames(), media_type=content_type,
            headers={"Cache-Control": "no-store, private", "Pragma": "no-cache", "X-Content-Type-Options": "nosniff"},
        )

    @app.put("/api/admin/intercom")
    async def admin_save_intercom(request: Request, payload: dict) -> dict:
        require_admin(request)
        try:
            value = intercom_settings.save(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"settings": value, "sip_ready": False}

    @app.post("/api/admin/intercom/test")
    async def admin_test_intercom(request: Request) -> dict:
        require_admin(request)
        settings = intercom_settings.load()

        async def reachable(host: str, port: int) -> bool:
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=2)
                writer.close()
                await writer.wait_closed()
                return True
            except (OSError, asyncio.TimeoutError):
                return False

        asterisk, doorbird = await asyncio.gather(
            reachable(settings["asterisk_host"], settings["asterisk_port"]),
            reachable(settings["doorbird_host"], settings["doorbird_port"]),
        )
        return {"asterisk_reachable": asterisk, "doorbird_reachable": doorbird, "sip_ready": False}

    @app.post("/api/admin/intercom/ami/test")
    async def admin_test_asterisk_ami(request: Request, payload: dict) -> Response:
        require_admin(request)
        if set(payload) != {"secret"} or not isinstance(payload["secret"], str) or not payload["secret"].strip():
            raise HTTPException(status_code=400, detail="Password AMI richiesta")
        settings = intercom_settings.load()
        try:
            source_ip = await asterisk_ami.local_source_ip(settings["asterisk_host"], 5038)
        except (OSError, TimeoutError):
            return JSONResponse({"ami_connected": False, "issue": "network", "source_ip": ""}, headers={"Cache-Control": "no-store, private"})
        try:
            result = await asterisk_ami.read_8301_auth(settings["asterisk_host"], 5038, "eface", payload["secret"].strip())
        except asterisk_ami.AMIAuthenticationError:
            return JSONResponse({"ami_connected": False, "issue": "authentication", "source_ip": source_ip}, headers={"Cache-Control": "no-store, private"})
        except asterisk_ami.AMIActionError as exc:
            return JSONResponse({"ami_connected": True, "issue": "config_read", "reason": exc.reason, "source_ip": source_ip}, headers={"Cache-Control": "no-store, private"})
        except (OSError, TimeoutError, asterisk_ami.AMIError):
            return JSONResponse({"ami_connected": False, "issue": "protocol", "source_ip": source_ip}, headers={"Cache-Control": "no-store, private"})
        return JSONResponse({"ami_connected": True, "auth_8301_found": any(value == "username=8301" for value in result.values()), "source_ip": source_ip}, headers={"Cache-Control": "no-store, private"})

    @app.websocket("/api/intercom/sip")
    async def intercom_sip_socket(websocket: WebSocket) -> None:
        origin = websocket.headers.get("origin", "")
        if (
            not user_auth.enabled()
            or not user_auth.session_user(websocket.cookies.get(user_auth.COOKIE))
            or urlsplit(origin).netloc != websocket.headers.get("host")
        ):
            await websocket.close(code=1008)
            return
        if "sip" not in websocket.scope.get("subprotocols", []):
            await websocket.close(code=1002)
            return
        settings = intercom_settings.load()
        target = f'ws://{settings["asterisk_host"]}:{settings["asterisk_port"]}/ws'
        try:
            async with websockets.connect(target, subprotocols=["sip"], open_timeout=4, max_size=1024 * 1024) as upstream:
                if upstream.subprotocol != "sip":
                    await websocket.close(code=1011)
                    return
                await websocket.accept(subprotocol="sip")

                async def to_asterisk() -> None:
                    while True:
                        event = await websocket.receive()
                        if event["type"] == "websocket.disconnect":
                            return
                        payload = event.get("text") if event.get("text") is not None else event.get("bytes")
                        if payload is not None:
                            await upstream.send(payload)

                async def to_browser() -> None:
                    async for payload in upstream:
                        if isinstance(payload, str):
                            await websocket.send_text(payload)
                        else:
                            await websocket.send_bytes(payload)

                tasks = (asyncio.create_task(to_asterisk()), asyncio.create_task(to_browser()))
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                for task in done:
                    if not task.cancelled():
                        task.exception()
        except (OSError, asyncio.TimeoutError, websockets.exceptions.WebSocketException):
            await websocket.close(code=1011)

    @app.post("/api/auth/setup")
    async def auth_setup(request: Request, payload: dict) -> JSONResponse:
        if user_auth.enabled():
            raise HTTPException(status_code=409, detail="Account già inizializzato")
        if not valid_session(request.cookies.get(COOKIE)) or not load_settings().installer_password:
            raise HTTPException(status_code=401, detail="Accedi prima agli Strumenti con la password installatore")
        try:
            user_auth.create_admin(str(payload.get("password") or ""))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        response = JSONResponse({"ok": True})
        response.set_cookie(user_auth.COOKIE, user_auth.create_session("admin"), max_age=user_auth.SESSION_SECONDS,
                            expires=datetime.now(timezone.utc) + timedelta(seconds=user_auth.SESSION_SECONDS),
                            httponly=True, samesite="lax", secure=secure_cookie(request), path="/")
        return response

    @app.post("/api/auth/login")
    async def auth_login(request: Request, payload: dict) -> JSONResponse:
        username = str(payload.get("username") or "")
        password = str(payload.get("password") or "")
        key = ((request.client.host if request.client else "unknown"), username)
        now = time.monotonic()
        failures = [moment for moment in login_failures.get(key, []) if now - moment < 300]
        if len(failures) >= 5:
            raise HTTPException(status_code=429, detail="Troppi tentativi; riprova fra qualche minuto")
        if not user_auth.enabled() or len(password) > 256 or not user_auth.verify(username, password):
            login_failures[key] = [*failures, now]
            raise HTTPException(status_code=401, detail="Credenziali non valide")
        login_failures.pop(key, None)
        persistent = bool(user_auth.account(username).get("trusted_access"))
        lifetime = user_auth.TRUSTED_DEVICE_SECONDS if persistent else user_auth.SESSION_SECONDS
        response = JSONResponse({"ok": True})
        response.set_cookie(user_auth.COOKIE, user_auth.create_session(username, lifetime), max_age=lifetime,
                            expires=datetime.now(timezone.utc) + timedelta(seconds=lifetime),
                            httponly=True, samesite="lax", secure=secure_cookie(request), path="/")
        return response

    @app.post("/api/auth/logout")
    async def auth_logout() -> JSONResponse:
        response = JSONResponse({"ok": True})
        response.delete_cookie(user_auth.COOKIE, path="/")
        return response

    def themed_page(filename: str, body_class: str = "") -> str:
        selected = load_background()
        presets = {
            "teal": "linear-gradient(135deg,#84bfd5,#137073 58%,#0e4a4e)",
            "midnight": "radial-gradient(circle at 70% 20%,#263f61,#08121e 65%)",
            "graphite": "linear-gradient(145deg,#596066,#181c1f 65%)",
            "ocean": "radial-gradient(circle at 25% 20%,#43a8ca,#075079 48%,#03273e)",
            "warm": "radial-gradient(circle at 20% 20%,#b77955,#59372f 52%,#24191b)",
        }
        background = "linear-gradient(rgba(4,22,26,.28),rgba(4,22,26,.48)),url('api/user/background/image')" if selected["mode"] == "custom" else presets[selected["preset"]]
        page = (STATIC / filename).read_text(encoding="utf-8")
        initial_background = background
        if selected["mode"] == "custom":
            initial_background += ";--custom-background:url('api/user/background/image')"
        replacements = {
            "__INITIAL_BACKGROUND__": escape(initial_background, quote=True),
            "__TOOLS_BACKGROUND__": escape(background, quote=True),
            "__BACKGROUND_PRESET__": escape("custom" if selected["mode"] == "custom" else selected["preset"], quote=True),
            "__CARD_THEME__": escape(load_card_theme(), quote=True),
        }
        startup = startup_settings.load()
        replacements["__STARTUP_SPLASH_STYLE__"] = "" if startup["enabled"] else "display:none"
        replacements["__STARTUP_SPLASH_MS__"] = str(startup["duration_ms"] if startup["enabled"] else 0)
        for placeholder, value in replacements.items():
            page = page.replace(placeholder, value)
        page = page.replace('content="#263f48"', 'content="#181c1f"')
        page = page.replace("manifest.webmanifest?v=2.20.38", "manifest.webmanifest?v=2.21.59")
        page = page.replace("app.css?v=2.20.20", "app.css?v=2.21.73")
        page = page.replace("app.css?v=2.21.84", "app.css?v=2.21.113")
        page = page.replace("home-status.css?v=2.20.20", "home-status.css?v=2.21.113")
        page = page.replace("tools.js?v=2.21.1", "tools.js?v=2.21.113")
        page = page.replace("ui-theme-contract.css?v=2.21.27", "ui-theme-contract.css?v=2.21.29")
        page = page.replace("tools-dashboard.js?v=2.21.27", "tools-dashboard.js?v=2.21.33")
        page = page.replace("tools-dashboard.js?v=2.21.33", "tools-dashboard.js?v=2.21.34")
        page = page.replace("tools-dashboard.js?v=2.21.34", "tools-dashboard.js?v=2.21.36")
        page = page.replace("tools-dashboard.js?v=2.21.36", "tools-dashboard.js?v=2.21.38")
        page = page.replace("tools-dashboard.js?v=2.21.38", "tools-dashboard.js?v=2.21.41")
        page = page.replace("tools-dashboard.js?v=2.21.41", "tools-dashboard.js?v=2.21.42")
        page = page.replace("tools-dashboard.js?v=2.21.42", "tools-dashboard.js?v=2.21.113")
        page = page.replace("tools-dashboard.css?v=2.20.36", "tools-dashboard.css?v=2.21.113")
        page = page.replace("backgrounds.css?v=2.20.20", "backgrounds.css?v=2.21.43")
        page = page.replace("intercom.css?v=2.21.14", "intercom.css?v=2.21.46")
        page = page.replace("app.js?v=2.21.11", "app.js?v=2.21.29")
        page = page.replace("energy.css?v=2.20.20", "energy.css?v=2.21.30")
        page = page.replace("app.js?v=2.21.29", "app.js?v=2.21.30")
        page = page.replace("app.js?v=2.21.30", "app.js?v=2.21.31")
        page = page.replace("app.js?v=2.21.31", "app.js?v=2.21.32")
        page = page.replace("app.js?v=2.21.32", "app.js?v=2.21.60")
        page = page.replace("app.js?v=2.21.60", "app.js?v=2.21.73")
        page = re.sub(r"app\.js\?v=[0-9.]+", f"app.js?v={VERSION}", page)
        page = page.replace("home-comfort.css?v=2.20.20", "home-comfort.css?v=2.21.31")
        if "--initial-background:" not in page:
            page = page.replace('<html lang="it">', f'<html lang="it" style="background:var(--initial-background,#181c1f);--initial-background:{replacements["__INITIAL_BACKGROUND__"]}">', 1)
        if body_class and "<body>" in page:
            page = page.replace("<body>", f'<body class="{body_class}" data-background="{replacements["__BACKGROUND_PRESET__"]}" data-card-theme="{replacements["__CARD_THEME__"]}">', 1)
        return page

    @app.get("/login", include_in_schema=False)
    async def login_page() -> HTMLResponse:
        page = themed_page("login.html", "login-theme")
        theme_links = '<link rel="stylesheet" href="assets/card-themes.css?v=2.21.27"><link rel="stylesheet" href="assets/ui-theme-contract.css?v=2.21.27">'
        trusted = '<label class="trusted-device"><input id="remember" type="checkbox" checked> Mantieni l’accesso su questo dispositivo</label>'
        page = page.replace('<button>ACCEDI</button>', f'{trusted}<button>ACCEDI</button>', 1)
        page = page.replace("password:document.getElementById('password').value", "password:document.getElementById('password').value,remember:document.getElementById('remember').checked")
        page = page.replace('</style>', '.trusted-device{display:flex;align-items:center;gap:9px;margin-top:18px}.trusted-device input{width:19px;height:19px;accent-color:var(--ui-accent)}</style>', 1)
        return HTMLResponse(page.replace("</head>", f"{theme_links}</head>", 1), headers={"Cache-Control": "no-store"})

    @app.get("/service-worker.js", include_in_schema=False)
    async def service_worker() -> FileResponse:
        return FileResponse(STATIC / "service-worker.js", media_type="application/javascript",
                            headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})

    @app.get("/intercom", include_in_schema=False)
    async def intercom_page(request: Request) -> HTMLResponse:
        if not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        if request.query_params.get("admin") == "1":
            require_admin(request)
        return HTMLResponse(themed_page("intercom.html"), headers={"Cache-Control": "no-store"})

    @app.get("/wiim", include_in_schema=False)
    async def wiim_page(request: Request) -> HTMLResponse:
        require_admin(request)
        return HTMLResponse(themed_page("wiim.html", "wiim-theme"), headers={"Cache-Control": "no-store"})

    @app.get("/soundcloud", include_in_schema=False)
    async def soundcloud_page(request: Request) -> HTMLResponse:
        require_admin(request)
        return HTMLResponse(themed_page("soundcloud.html", "soundcloud-theme"), headers={"Cache-Control": "no-store"})

    async def resolved_provider(config, slug: str, port: int, timeout: float):
        manual = str(config.base_url or "").lower()
        if manual and "127.0.0.1" not in manual and "localhost" not in manual:
            return config
        discovered = await discover_addon_url(slug, port, timeout)
        return replace(config, base_url=discovered) if discovered else config

    def evoice_connector(settings):
        if settings.evoice.base_url and settings.evoice.installation_id:
            return EkonexMediaConnector(settings.evoice, settings.request_timeout_s)
        return EvoiceLocalMediaConnector(settings.request_timeout_s)

    def media_connectors(settings):
        result = []
        control4 = load_control4_config()
        if control4.get("username") and control4.get("password"):
            result.append(Control4MediaConnector(control4))
        if settings.evoice.enabled:
            result.append(evoice_connector(settings))
        return result or [EkonexMediaConnector(settings.evoice, settings.request_timeout_s)]

    def media_connector(settings, resource_id: str = ""):
        if str(resource_id).startswith(("c4", "c4room:")):
            control4 = load_control4_config()
            if control4.get("username") and control4.get("password"):
                return Control4MediaConnector(control4)
        if settings.evoice.enabled:
            return evoice_connector(settings)
        return media_connectors(settings)[0]

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True, "version": VERSION}

    @app.get("/api/sunmind/{proxy_path:path}", include_in_schema=False)
    async def sunmind_proxy(proxy_path: str, request: Request) -> Response:
        settings = load_settings()
        config = settings.sunmind
        if not config.enabled:
            raise HTTPException(status_code=503, detail="Dashboard energia non disponibile")
        clean_path = str(proxy_path or "").lstrip("/")
        if not clean_path or ".." in clean_path.split("/"):
            raise HTTPException(status_code=400, detail="Percorso dashboard non valido")
        manual = str(config.base_url or "").lower()
        candidates = []
        if manual and "127.0.0.1" not in manual and "localhost" not in manual:
            candidates.append(config.base_url)
        else:
            discovered, host_url = await asyncio.gather(
                discover_addon_url("e_sunmind", 1980, settings.request_timeout_s),
                discover_host_url(1980, settings.request_timeout_s),
            )
            candidates.extend(value for value in (discovered, host_url, config.base_url) if value and value not in candidates)
        upstream = None
        timeout = httpx.Timeout(max(20.0, settings.request_timeout_s), connect=min(3.0, settings.request_timeout_s))
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for base_url in candidates:
                target = f"{base_url.rstrip('/')}/{clean_path}"
                if request.url.query:
                    target = f"{target}?{request.url.query}"
                try:
                    candidate = await client.get(target, headers={"Accept": request.headers.get("accept", "*/*")})
                    candidate.raise_for_status()
                    upstream = candidate
                    break
                except httpx.HTTPError:
                    continue
        if upstream is None:
            raise HTTPException(status_code=502, detail="e-SunMind non raggiungibile")
        headers = {"Cache-Control": upstream.headers.get("cache-control", "no-cache")}
        return Response(upstream.content, status_code=upstream.status_code, media_type=upstream.headers.get("content-type"), headers=headers)

    @app.get("/api/bootstrap")
    async def bootstrap() -> dict:
        settings = load_settings()
        buspro_config, etherm_config, ksenia_config = await asyncio.gather(
            resolved_provider(settings.buspro, "e_hdl_buspro_mqtt", 8124, settings.request_timeout_s),
            resolved_provider(settings.etherm, "e_therm_plus_ks", 8080, settings.request_timeout_s),
            resolved_provider(settings.ksenia, "ksenia_lares_addon", 8080, settings.request_timeout_s),
        )
        connectors = [
            BusproConnector(buspro_config, settings.request_timeout_s),
            EThermConnector(etherm_config, settings.request_timeout_s),
            KseniaConnector(ksenia_config, settings.request_timeout_s),
            *media_connectors(settings),
        ]
        wiim_config = wiim_settings.load()
        wiim_task = asyncio.create_task(WiiMClient(wiim_config["host"]).snapshot()) if wiim_config.get("enabled") and wiim_config.get("host") else None
        providers = list(await asyncio.gather(*(connector.snapshot() for connector in connectors)))
        providers = [apply_preferences(provider) if provider.get("id") in {"evoice", "control4"} else provider for provider in providers]
        if wiim_task:
            try:
                native_snapshot = await wiim_task
                linked = overlay_wiim_on_control4(providers, native_snapshot, int(wiim_config.get("control4_source_id") or 0))
                providers.append({"id": "wiim", "name": "WiiM nativo", "status": "online", "items": [] if linked else [native_wiim_media_item(native_snapshot)]})
            except (httpx.HTTPError, RuntimeError, ValueError):
                providers.append({"id": "wiim", "name": "WiiM nativo", "status": "offline", "items": [], "reason": "WiiM non raggiungibile"})
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
            ksenia = next((item for item in providers if item.get("id") == "ksenia" and item.get("status") in {"online", "stale"}), None)
            if isinstance(ksenia, dict):
                dashboard["devices"].extend(ksenia.get("items", []))
            for media in (item for item in providers if item.get("id") in {"control4", "evoice", "wiim"} and item.get("status") in {"online", "stale"}):
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
                if device.get("kind") in {"alarm_partition", "alarm_scenario", "alarm_system"}:
                    continue
                room = str(device.get("room") or "").strip()
                if not room:
                    continue
                key = room.casefold()
                if key not in room_map:
                    if device.get("kind") == "media_player":
                        provider = str(device.get("provider") or "")
                        original_room = str(device.get("original_room") or "").strip()
                        manually_assigned = bool(original_room and original_room.casefold() != key)
                        if provider != "control4" and not manually_assigned:
                            continue
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
            "backgrounds": load_backgrounds(),
            "appearance": {"card_theme": load_card_theme(), "card_glow": load_card_glow(), "room_order": load_room_order(), "security_order": load_security_order(), "shortcuts": load_shortcuts(), "home_widgets": load_home_widgets(), "home_camera_entity": load_home_camera_entity()},
            "nav_icons": settings.nav_icons,
            "mode": "demo" if settings.demo_mode else "live",
            "dashboard": dashboard,
            "providers": providers,
        }

    def require_installer(request: Request) -> None:
        if user_auth.enabled():
            require_admin(request)
        elif not valid_session(request.cookies.get(COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso installatore richiesto")

    @app.get("/api/installer/status")
    async def installer_status(request: Request) -> dict:
        require_installer(request)
        return {"ok": True}

    @app.get("/tools", include_in_schema=False)
    @app.get("/installer", include_in_schema=False)
    async def tools_page() -> HTMLResponse:
        return HTMLResponse(themed_page("tools.html"), headers={"Cache-Control": "no-cache"})

    @app.post("/api/installer/login")
    async def installer_login(payload: dict) -> JSONResponse:
        configured = load_settings().installer_password
        if user_auth.enabled() and user_auth.verify("admin", str(payload.get("password") or "")):
            response = JSONResponse({"ok": True})
            response.set_cookie(COOKIE, create_session(), max_age=8 * 60 * 60, httponly=True, samesite="strict", secure=False, path="/")
            return response
        if not configured:
            raise HTTPException(status_code=503, detail="Imposta prima la password installatore nelle opzioni dell'add-on")
        if not hmac.compare_digest(str(payload.get("password") or ""), configured):
            raise HTTPException(status_code=401, detail="Password non valida")
        response = JSONResponse({"ok": True})
        response.set_cookie(COOKIE, create_session(), max_age=8 * 60 * 60, httponly=True, samesite="strict", secure=False, path="/")
        return response

    @app.post("/api/installer/logout")
    async def installer_logout() -> JSONResponse:
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE, path="/")
        return response

    @app.get("/api/user/background")
    async def user_background() -> dict:
        return {**load_backgrounds(), "presets": sorted(PRESETS)}

    @app.get("/api/user/card-theme")
    async def user_card_theme() -> dict:
        return {"theme": load_card_theme(), "themes": sorted(CARD_THEMES)}

    @app.get("/api/user/appearance")
    async def user_appearance() -> dict:
        return {"card_glow": load_card_glow(), "room_order": load_room_order(), "security_order": load_security_order(), "shortcuts": load_shortcuts(), "home_widgets": load_home_widgets(), "home_camera_entity": load_home_camera_entity()}

    @app.put("/api/user/appearance")
    async def user_save_appearance(payload: dict) -> dict:
        try:
            if "card_glow" in payload: save_card_glow(payload["card_glow"])
            if "room_order" in payload: save_room_order(payload["room_order"])
            if "security_order" in payload: save_security_order(payload["security_order"])
            if "shortcuts" in payload: save_shortcuts(payload["shortcuts"])
            if "home_widgets" in payload: save_home_widgets(payload["home_widgets"])
            if "home_camera_entity" in payload: save_home_camera_entity(payload["home_camera_entity"])
        except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
        return {"card_glow": load_card_glow(), "room_order": load_room_order(), "security_order": load_security_order(), "shortcuts": load_shortcuts(), "home_widgets": load_home_widgets(), "home_camera_entity": load_home_camera_entity()}

    @app.put("/api/user/card-theme")
    async def user_save_card_theme(payload: dict) -> dict:
        try: save_card_theme(str(payload.get("theme") or ""))
        except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True, "theme": load_card_theme()}

    @app.put("/api/user/background")
    async def user_save_background(payload: dict) -> dict:
        room = str(payload.get("room") or "").strip() or None
        try:
            if payload.get("mode") == "custom":
                save_background_image(str(payload.get("mime") or ""), str(payload.get("data") or ""), room)
            elif payload.get("mode") == "inherit" and room:
                save_inherit(room)
            else:
                save_preset(str(payload.get("preset") or ""), room)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True, **load_background(room)}

    @app.get("/api/user/background/image")
    async def user_background_image(room: str | None = None) -> Response:
        image = load_background_image(room)
        if not image:
            raise HTTPException(status_code=404, detail="Sfondo personalizzato non disponibile")
        return Response(image[1], media_type=image[0], headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"})

    @app.get("/api/installer/media-players")
    async def installer_media_players(request: Request) -> dict:
        require_installer(request)
        settings = load_settings()
        snapshots = await asyncio.gather(*(connector.snapshot() for connector in media_connectors(settings)))
        online = [snapshot for snapshot in snapshots if snapshot.get("status") == "online"]
        if not online:
            raise HTTPException(status_code=503, detail=next((snapshot.get("reason") for snapshot in snapshots if snapshot.get("reason")), "Player non disponibili"))
        saved = load_preferences()
        items = []
        all_players = [player for snapshot in online for player in snapshot.get("items", [])]
        for index, player in enumerate(all_players):
            registry_id = str(player.get("registry_id") or "")
            inferred = set(player.get("experiences") or [])
            selected = saved.get(registry_id, {"visible": True, "audio": "listen" in inferred, "video": "watch" in inferred, "tts": bool(player.get("tts_available")), "order": index, "name": "", "room": ""})
            original_name = str(player.get("name") or registry_id)
            original_room = str(player.get("room") or "Senza stanza")
            items.append({
                "registry_id": registry_id, "original_name": original_name, "original_room": original_room,
                "name": str(selected.get("name") or ""), "room": str(selected.get("room") or ""),
                "entity_id": str(player.get("entity_id") or ""), "device_type": str(player.get("device_type") or "media_player"),
                "provider": str(player.get("provider") or ""),
                "manufacturer": str(player.get("manufacturer") or ""), "tts_available": bool(player.get("tts_available")),
                "dnd_available": bool(player.get("dnd_available")),
                **{key: selected.get(key) for key in ("visible", "audio", "video", "tts", "order")},
            })
        items.sort(key=lambda item: int(item.get("order", 0)))
        return {"items": items, "configured": bool(saved)}

    @app.put("/api/installer/media-players")
    async def installer_save_media_players(request: Request, payload: dict) -> dict:
        require_installer(request)
        settings = load_settings()
        snapshots = await asyncio.gather(*(connector.snapshot() for connector in media_connectors(settings)))
        valid_players = {str(item.get("registry_id")): item for snapshot in snapshots for item in snapshot.get("items", []) if item.get("registry_id")}
        selections = payload.get("players")
        if isinstance(selections, dict):
            selections = {key: dict(value) if isinstance(value, dict) else value for key, value in selections.items()}
            for registry_id, selection in selections.items():
                if not isinstance(selection, dict):
                    continue
                player = valid_players.get(registry_id, {})
                if player.get("provider") != "evoice" or not player.get("tts_available"):
                    selection["tts"] = False
        try:
            saved = save_preferences(selections, set(valid_players))
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True, "players": len(saved)}

    @app.get("/api/installer/media-source-icons")
    async def installer_media_source_icons(request: Request) -> dict:
        require_installer(request)
        snapshots = await asyncio.gather(*(connector.snapshot() for connector in media_connectors(load_settings())))
        sources: dict[int, dict] = {}
        hidden_sources = hidden_source_ids()
        for player in (player for snapshot in snapshots for player in snapshot.get("items", [])):
            for source in player.get("source_options", []):
                source_id = int(source.get("source_id") or 0)
                if source_id > 0:
                    sources[source_id] = {"source_id": source_id, "name": str(source.get("label") or source_id), "custom": load_source_icon(source_id) is not None, "hidden": source_id in hidden_sources}
        return {"items": sorted(sources.values(), key=lambda item: item["name"].casefold())}

    @app.get("/api/control4/hidden-sources")
    async def control4_hidden_sources() -> dict:
        return {"ids": sorted(hidden_source_ids())}

    @app.put("/api/installer/media-source-icons/{source_id}/visibility")
    async def installer_media_source_visibility(source_id: int, request: Request, payload: dict) -> dict:
        require_installer(request)
        if not isinstance(payload.get("hidden"), bool):
            raise HTTPException(status_code=400, detail="Visibilità non valida")
        try:
            return {"ids": sorted(set_source_hidden(source_id, payload["hidden"]))}
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/installer/media-source-icons/{source_id}")
    async def installer_save_media_source_icon(source_id: int, request: Request, payload: dict) -> dict:
        require_installer(request)
        try:
            save_source_icon(source_id, str(payload.get("mime") or ""), str(payload.get("data") or ""))
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.delete("/api/installer/media-source-icons/{source_id}")
    async def installer_delete_media_source_icon(source_id: int, request: Request) -> dict:
        require_installer(request)
        return {"ok": True, "removed": delete_source_icon(source_id)}

    @app.get("/api/installer/control4")
    async def installer_control4(request: Request) -> dict:
        require_installer(request)
        return public_control4_config()

    @app.put("/api/installer/control4")
    async def installer_save_control4(request: Request, payload: dict) -> dict:
        require_installer(request)
        try:
            value = save_control4_config(payload)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True, "host": value["host"], "username": value["username"]}

    @app.post("/api/installer/control4/test")
    async def installer_test_control4(request: Request, payload: dict) -> dict:
        require_installer(request)
        try:
            config = save_control4_config(payload)
            return await test_control4_connection(config)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logging.warning("Control4 connection test failed: %s", type(exc).__name__)
            raise HTTPException(status_code=502, detail=f"Test Control4 fallito ({type(exc).__name__})")

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
        operation = str(payload.get("action") or "")
        wiim_actions = {
            "media_play": "play", "media_pause": "pause", "media_stop": "stop",
            "media_next": "next", "media_previous": "previous", "set_volume": "volume",
            "volume_mute": "mute", "volume_unmute": "unmute",
        }
        if device_id.startswith("wiim:"):
            action = wiim_actions.get(operation)
            if not action:
                raise HTTPException(status_code=400, detail="Comando WiiM non valido")
            try:
                client = configured_wiim()
                await client.player_action(action, int(payload.get("value")) if operation == "set_volume" else None)
                return {"ok": True, "provider": "wiim", "device": await client.snapshot()}
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except (httpx.HTTPError, RuntimeError) as exc:
                raise HTTPException(status_code=502, detail="Comando WiiM non riuscito") from exc
        if device_id.startswith(("ksenia-partition:", "ksenia-zone:", "ksenia-scenario:")):
            config = await resolved_provider(settings.ksenia, "ksenia_lares_addon", 8080, settings.request_timeout_s)
            if not config.enabled or not config.base_url:
                raise HTTPException(status_code=503, detail="Sistema di sicurezza non disponibile")
            kind = "partition" if device_id.startswith("ksenia-partition:") else "scenario" if device_id.startswith("ksenia-scenario:") else "zone"
            source_id = device_id.split(":", 1)[1]
            try:
                return await KseniaConnector(config, settings.request_timeout_s).command(kind, source_id, str(payload.get("action") or ""), str(payload.get("pin") or ""))
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
                raise HTTPException(status_code=502, detail="Centrale non raggiungibile")
            except httpx.HTTPStatusError as exc:
                raise HTTPException(status_code=502, detail=f"La centrale ha risposto con errore HTTP {exc.response.status_code}")
            except (ValueError, TypeError) as exc:
                raise HTTPException(status_code=400, detail=str(exc))
        if device_id.startswith(("media:", "c4media:")):
            config = settings.evoice
            control4 = load_control4_config()
            control4_enabled = bool(control4.get("username") and control4.get("password"))
            if not control4_enabled and not config.enabled:
                raise HTTPException(status_code=503, detail="Ekonex Media non disponibile")
            allowed = {"media_play", "media_pause", "media_stop", "turn_off", "media_next", "media_previous", "set_volume", "volume_mute", "volume_unmute", "select_source", "media_join", "media_unjoin", "video_remote", "tts", "set_dnd"}
            if operation not in allowed:
                raise HTTPException(status_code=400, detail="Comando multimedia non valido")
            if device_id.startswith("c4media:") and operation in {"tts", "set_dnd"}:
                raise HTTPException(status_code=400, detail="TTS e DND sono disponibili soltanto sui player e-Voice")
            # Linked WiiM owns metadata/transport only. Room volume and mute belong to Control4.
            # Never flatten room levels with WiiM's single hardware volume (TASK_VOLUME_MASTER_PROPORZIONALE.md).
            if device_id.startswith("c4media:") and operation in {"media_play", "media_pause", "media_stop", "media_next", "media_previous"}:
                wiim_config = wiim_settings.load()
                source_id = int(wiim_config.get("control4_source_id") or 0)
                if wiim_config.get("enabled") and wiim_config.get("host") and source_id > 0:
                    try:
                        room_id = int(device_id.split(":", 1)[1])
                        control4_snapshot = await Control4MediaConnector(control4).snapshot()
                        room = next((item for item in control4_snapshot.get("items", []) if str(item.get("registry_id")) == f"c4room:{room_id}"), None)
                        if room and int(room.get("active_source_id") or 0) == source_id:
                            client = WiiMClient(wiim_config["host"])
                            await client.player_action(wiim_actions[operation], int(payload.get("value")) if operation == "set_volume" else None)
                            return {"ok": True, "provider": "wiim", "device": await client.snapshot()}
                    except ValueError as exc:
                        raise HTTPException(status_code=400, detail=str(exc)) from exc
                    except (httpx.HTTPError, RuntimeError) as exc:
                        raise HTTPException(status_code=502, detail="Comando WiiM non riuscito") from exc
            arguments = {}
            if operation == "set_volume":
                arguments["volume_percent"] = int(payload.get("value"))
            elif operation == "select_source":
                arguments["source"] = str(payload.get("value") or "")
            elif operation == "media_join":
                arguments["member_registry_ids"] = payload.get("value")
            elif operation == "tts":
                message = str(payload.get("value") or "").strip()
                if not message or len(message) > 500:
                    raise HTTPException(status_code=400, detail="Messaggio TTS non valido")
                preferences = load_preferences().get(device_id.split(":", 1)[1], {})
                if not preferences.get("visible") or not preferences.get("tts"):
                    raise HTTPException(status_code=403, detail="TTS non abilitato per questo dispositivo")
                arguments["text"] = message
            elif operation == "set_dnd":
                arguments["enabled"] = bool(payload.get("value"))
            command = {"request_id": str(uuid.uuid4()), "operation": operation, "arguments": arguments, "expected_resource_revision": payload.get("resource_revision") if operation in {"media_join", "media_unjoin"} else None}
            try:
                connector = media_connector(settings, device_id)
                if operation == "media_join":
                    snapshot = await connector.snapshot()
                    valid_members = {str(item.get("registry_id")) for item in snapshot.get("items", []) if item.get("registry_id")}
                    requested_members = arguments.get("member_registry_ids")
                    if not isinstance(requested_members, list) or not set(map(str, requested_members)).issubset(valid_members):
                        raise ValueError("I player della sessione devono appartenere allo stesso provider")
                if isinstance(connector, Control4MediaConnector):
                    return await connector.command(f"c4room:{device_id.split(':', 1)[1]}", operation, payload.get("value"))
                return await connector.command(device_id.split(":", 1)[1], command)
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
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc))
        if device_id.startswith("therm:"):
            config = await resolved_provider(settings.etherm, "e_therm_plus_ks", 8080, settings.request_timeout_s)
            if not config.enabled or not config.base_url:
                raise HTTPException(status_code=503, detail="Connettore e-Therm non disponibile")
            try:
                connector = EThermConnector(config, settings.request_timeout_s)
                thermostat = next((item for item in (await connector.snapshot()).get("items", []) if item.get("id") == device_id), None)
                if thermostat and thermostat.get("read_only"):
                    raise ValueError("Termostato configurato in sola visualizzazione")
                return await connector.command(device_id.split(":", 1)[1], str(payload.get("action") or ""), payload.get("value"))
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
        connector = media_connector(settings, registry_id)
        if not config.enabled and not isinstance(connector, Control4MediaConnector):
            raise HTTPException(status_code=503, detail="Ekonex Media non disponibile")
        try:
            upstream = await connector.artwork(registry_id, fingerprint, if_none_match)
        except httpx.HTTPError:
            raise HTTPException(status_code=502, detail="Ekonex Media non raggiungibile")
        if upstream.status_code == 304:
            return Response(status_code=304, headers={"Cache-Control": "private, max-age=300"})
        if upstream.status_code != 200:
            raise HTTPException(status_code=upstream.status_code, detail="Copertina non disponibile")
        media_type = artwork_media_type(upstream.headers.get("content-type", ""), upstream.content)
        if not media_type or len(upstream.content) > 700_000:
            raise HTTPException(status_code=415, detail="Copertina non valida")
        headers = {"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"}
        if upstream.headers.get("etag"):
            headers["ETag"] = upstream.headers["etag"]
        return Response(upstream.content, media_type=media_type, headers=headers)

    @app.get("/api/control4/recently-played")
    async def control4_recently_played(room_id: int | None = Query(None, gt=0), limit: int = Query(20, ge=1, le=20)) -> dict:
        config = load_control4_config()
        if not config.get("username") or not config.get("password"):
            raise HTTPException(status_code=503, detail="Control4 non configurato")
        connector = Control4MediaConnector(config)
        try:
            if room_id is None:
                snapshot = await connector.snapshot()
                room_ids = [int(str(item["registry_id"]).removeprefix("c4room:")) for item in snapshot.get("items", [])]
            else:
                room_ids = [room_id]
            history = await connector.recently_played(room_ids, limit)
            enrich_recent_favorites(history)
            items, hidden_count = filter_recents(history)
            return {"items": items, "hidden_items": hidden_recents(history), "hidden_count": hidden_count}
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logging.warning("Control4 recently played non disponibile: %s", type(exc).__name__)
            raise HTTPException(status_code=502, detail="Ascoltati di recente Control4 non disponibili")

    @app.post("/api/control4/recently-played/select")
    async def control4_select_recent(payload: dict) -> dict:
        config = load_control4_config()
        if not config.get("username") or not config.get("password"):
            raise HTTPException(status_code=503, detail="Control4 non configurato")
        try:
            return await Control4MediaConnector(config).select_recent(int(payload.get("room_id") or 0), str(payload.get("key") or ""))
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception:
            raise HTTPException(status_code=502, detail="Riproduzione recente Control4 non disponibile")

    @app.post("/api/control4/recently-played/hide")
    async def control4_hide_recent(request: Request, payload: dict) -> dict:
        if user_auth.enabled() and not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        try:
            return {"hidden_count": hide_recent(str(payload.get("key") or ""))}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/control4/recently-played/restore")
    async def control4_restore_recents(request: Request) -> dict:
        if user_auth.enabled() and not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        restore_recents()
        return {"hidden_count": 0}

    @app.post("/api/control4/recently-played/restore-one")
    async def control4_restore_one_recent(request: Request, payload: dict) -> dict:
        if user_auth.enabled() and not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        try:
            return {"hidden_count": restore_recent(str(payload.get("key") or ""))}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/control4/source-icon/{source_id}", include_in_schema=False)
    async def control4_source_icon(source_id: int) -> Response:
        if source_id <= 0:
            raise HTTPException(status_code=404, detail="Icona Control4 non disponibile")
        custom = load_source_icon(source_id)
        if custom:
            return Response(custom[1], media_type=custom[0], headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"})
        builtin = load_builtin_source_icon_by_id(source_id) or load_builtin_source_icon(cached_control4_source_label(source_id))
        if builtin:
            return Response(builtin[1], media_type=builtin[0], headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"})
        cached = cached_control4_icon(source_id)
        if cached:
            return Response(cached[1], media_type=cached[0], headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"})
        config = load_control4_config()
        if not config.get("username") or not config.get("password"):
            raise HTTPException(status_code=404, detail="Control4 non configurato")
        try:
            director, _ = await control4_director(config)
            path = cached_control4_icon_path(source_id) or control4_icon_path(await director.get_item_info(source_id))
            if not path:
                raise HTTPException(status_code=404, detail="Icona Control4 non disponibile")
            async with httpx.AsyncClient(verify=False, timeout=8, follow_redirects=False) as client:
                upstream = await client.get(director.base_url + path, headers=director.headers)
            media_type = upstream.headers.get("content-type", "").split(";", 1)[0]
            if upstream.status_code != 200 or media_type not in {"image/png", "image/jpeg", "image/gif", "image/webp"} or len(upstream.content) > 300_000:
                raise HTTPException(status_code=404, detail="Icona Control4 non disponibile")
            return Response(upstream.content, media_type=media_type, headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"})
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=502, detail="Icona Control4 non raggiungibile")

    @app.post("/api/media/groups/{group_id}/command")
    async def media_group_command(group_id: str, payload: dict) -> dict:
        settings = load_settings()
        connector = media_connector(settings, group_id)
        config = settings.evoice
        if not isinstance(connector, Control4MediaConnector) and not config.enabled:
            raise HTTPException(status_code=503, detail="Ekonex Media non disponibile")
        operation = str(payload.get("action") or "")
        if operation != "set_group_volume":
            raise HTTPException(status_code=400, detail="Comando gruppo non valido")
        command = {"request_id": str(uuid.uuid4()), "operation": operation, "arguments": {"volume_percent": int(payload.get("value"))}, "expected_resource_revision": payload.get("resource_revision")}
        try:
            if isinstance(connector, Control4MediaConnector):
                return await connector.group_volume(group_id, int(payload.get("value")))
            return await connector.group_command(group_id, command)
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail="Comando gruppo Ekonex Media rifiutato")
        except httpx.HTTPError:
            raise HTTPException(status_code=502, detail="Ekonex Media non raggiungibile")
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    @app.websocket("/api/realtime")
    async def realtime(websocket: WebSocket) -> None:
        if user_auth.enabled() and not user_auth.session_user(websocket.cookies.get(user_auth.COOKIE)):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        settings = load_settings()
        buspro, etherm, ksenia = await asyncio.gather(
            resolved_provider(settings.buspro, "e_hdl_buspro_mqtt", 8124, settings.request_timeout_s),
            resolved_provider(settings.etherm, "e_therm_plus_ks", 8080, settings.request_timeout_s),
            resolved_provider(settings.ksenia, "ksenia_lares_addon", 8080, settings.request_timeout_s),
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

        async def ksenia_events() -> None:
            retry_delay = 1
            while True:
                try:
                    async with httpx.AsyncClient(timeout=None, follow_redirects=False) as client:
                        async with client.stream("GET", f"{ksenia.base_url}/api/stream") as response:
                            response.raise_for_status()
                            async for line in response.aiter_lines():
                                if not line.startswith("data:"):
                                    continue
                                try:
                                    payload = json.loads(line[5:].strip())
                                except (TypeError, json.JSONDecodeError):
                                    continue
                                items = normalize_ksenia(payload)
                            if items:
                                await queue.put({"type": "ksenia_state", "data": {"items": items}})
                                retry_delay = 1
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log_reconnect_warning("Ksenia")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 30)

        async def media_events(connector) -> None:
            retry_delay = 2
            while True:
                try:
                    async for event in connector.events():
                        retry_delay = 2
                        event_type = str(event.get("type") or "")
                        if event_type == "local.player_updated":
                            await queue.put({"type": "media_state", "data": event.get("data") or {}})
                            continue
                        if event_type != "heartbeat":
                            await queue.put({"type": "media_changed", "event_type": event_type})
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log_reconnect_warning(connector.id)
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 30)

        tasks = []
        if buspro.enabled and buspro.base_url:
            tasks.append(asyncio.create_task(buspro_events()))
        if etherm.enabled and etherm.base_url:
            tasks.append(asyncio.create_task(etherm_events()))
        if ksenia.enabled and ksenia.base_url:
            tasks.append(asyncio.create_task(ksenia_events()))
        for connector in media_connectors(settings):
            if connector.id == "control4" or settings.evoice.enabled:
                tasks.append(asyncio.create_task(media_events(connector)))
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
                "room": str(item.get("room") or item.get("room_name") or item.get("area") or ""),
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
    async def frontend(path: str) -> HTMLResponse:
        return HTMLResponse(themed_page("index.html", "app-theme"), headers={"Cache-Control": "no-cache"})

    return app


def main() -> None:
    uvicorn.run(create_app(), host="0.0.0.0", port=8099, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
