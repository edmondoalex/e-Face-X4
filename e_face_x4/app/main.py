from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
import uuid
from html import escape
from pathlib import Path
from dataclasses import replace
from urllib.parse import urlsplit

import httpx
import uvicorn
import websockets
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

from .config import load_settings
from .control4 import control4_director, load_control4_config, public_control4_config, save_control4_config, test_control4_connection
from .installer_auth import COOKIE, create_session, valid_session
from . import user_auth
from . import intercom_settings
from . import installation
from . import credential_inventory
from . import sip_accounts
from . import asterisk_ami
from . import doorbird_api
from .media_preferences import apply_preferences, load_preferences, save_preferences
from .source_icons import delete_source_icon, load_builtin_source_icon, load_source_icon, save_source_icon
from .backgrounds import CARD_THEMES, PRESETS, load_background, load_background_image, load_backgrounds, load_card_theme, load_card_glow, load_room_order, load_security_order, save_background_image, save_card_theme, save_card_glow, save_room_order, save_security_order, save_inherit, save_preset
from .connectors import BusproConnector, Control4MediaConnector, EThermConnector, EkonexMediaConnector, EvoiceLocalMediaConnector, KseniaConnector
from .connectors.ksenia import normalize_ksenia
from .connectors.control4_media import cached_control4_icon, cached_control4_icon_path, cached_control4_source_label, control4_icon_path
from .connectors.supervisor import discover_addon_url, discover_host_url
from .demo import dashboard as demo_dashboard

VERSION = "2.20.66"
STATIC = Path(__file__).parent / "static"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [e-face-x4] %(message)s")


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
    control4_support_tokens: dict[str, float] = {}

    def secure_cookie(request: Request) -> bool:
        return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https"

    @app.middleware("http")
    async def user_login_guard(request: Request, call_next):
        path = request.url.path
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and urlsplit(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Origine non consentita"}, status_code=403)
        if not user_auth.enabled() or path == "/health" or path == "/login" or path.startswith("/api/auth/") or path.startswith("/assets/") or path.startswith("/api/support/control4/artwork/"):
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
        return {"enabled": user_auth.enabled(), "user": username, "role": user_auth.account(username)["role"] if username else None}

    def require_admin(request: Request) -> str:
        username = user_auth.session_user(request.cookies.get(user_auth.COOKIE))
        if username != "admin":
            raise HTTPException(status_code=403, detail="Accesso amministratore richiesto")
        return username

    @app.get("/api/admin/installation/preflight")
    async def admin_installation_preflight(request: Request) -> dict:
        require_admin(request)
        return await installation.preflight()

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
        try:
            user = user_auth.create_account(str(payload.get("username") or ""), str(payload.get("name") or ""), str(payload.get("password") or ""))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"user": user}

    @app.patch("/api/admin/users/{username}")
    async def admin_update_user(username: str, request: Request, payload: dict) -> dict:
        require_admin(request)
        if not payload or set(payload) - {"name", "password", "active"}:
            raise HTTPException(status_code=400, detail="Campi non validi")
        if "active" in payload and not isinstance(payload["active"], bool):
            raise HTTPException(status_code=400, detail="Stato non valido")
        if "name" in payload and not isinstance(payload["name"], str):
            raise HTTPException(status_code=400, detail="Nome non valido")
        if "password" in payload and not isinstance(payload["password"], str):
            raise HTTPException(status_code=400, detail="Password non valida")
        try:
            user = user_auth.update_account(username, name=payload.get("name"), password=payload.get("password"), active=payload.get("active"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"user": user}

    @app.get("/api/admin/intercom")
    async def admin_intercom(request: Request) -> dict:
        require_admin(request)
        turn = intercom_settings.load_turn()
        return {"settings": intercom_settings.load(), "turn": {"turn_url": turn["turn_url"], "turn_username": turn["turn_username"], "password_configured": bool(turn["turn_password"])}, "sip_ready": False}

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

    async def control4_service_discovery() -> dict:
        config = load_control4_config()
        if not config.get("username") or not config.get("password"):
            raise HTTPException(status_code=409, detail="Control4 non configurato in e-Face")
        try:
            director, _ = await control4_director(config)
            ui, all_items = await asyncio.gather(director.get_ui_configuration(), director.get_all_item_info())
        except Exception as exc:
            logging.warning("Ricognizione servizi Control4: %s", type(exc).__name__)
            raise HTTPException(status_code=502, detail="Servizi Control4 non raggiungibili") from exc
        item_info = {str(item.get("id")): item for item in all_items if isinstance(item, dict) and item.get("id") is not None} if isinstance(all_items, list) else {}
        experiences = ui.get("experiences", []) if isinstance(ui, dict) else []
        if isinstance(experiences, dict):
            experiences = experiences.get("experience", [])
        sources: dict[int, dict] = {}
        for experience in experiences if isinstance(experiences, list) else []:
            if not isinstance(experience, dict) or experience.get("type") != "listen":
                continue
            raw = experience.get("sources", {})
            entries = raw.get("source", []) if isinstance(raw, dict) else []
            if isinstance(entries, dict):
                entries = [entries]
            for source in entries if isinstance(entries, list) else []:
                if not isinstance(source, dict) or not str(source.get("id") or "").isdigit():
                    continue
                source_id = int(source["id"])
                if source_id > 0 and len(sources) < 60:
                    info = item_info.get(str(source_id), {})
                    sources[source_id] = {"source_id": source_id, "name": str(source.get("name") or info.get("name") or source_id)[:100], "source_type": str(source.get("type") or "")[:60]}
        semaphore = asyncio.Semaphore(4)

        def field_names(items: object, keys: tuple[str, ...]) -> list[str]:
            if not isinstance(items, list):
                return []
            return sorted({str(value)[:80] for item in items if isinstance(item, dict) for key in keys if (value := item.get(key)) and isinstance(value, (str, int))})[:100]

        async def inspect(source_id: int, source: dict) -> dict:
            async with semaphore:
                variables, commands = await asyncio.gather(director.get_item_variables(source_id), director.get_item_commands(source_id), return_exceptions=True)
            info = item_info.get(str(source_id), {})
            return {**source, "state": "unknown", "variable_names": field_names(variables, ("varName", "variableName", "name")), "command_names": field_names(commands, ("name", "command", "commandName", "label")), "item_fields": sorted(str(key)[:80] for key in info)[:100]}

        account_services = ("tunein", "tidal", "deezer", "qobuz", "amazon music", "apple music", "soundmachine")
        candidates = {}
        for item in all_items if isinstance(all_items, list) else []:
            if not isinstance(item, dict) or not str(item.get("id") or "").isdigit():
                continue
            name = str(item.get("name") or "")
            if any(service in name.casefold() for service in account_services) and len(candidates) < 60:
                item_id = int(item["id"])
                candidates[item_id] = {"source_id": item_id, "name": name[:100], "source_type": str(item.get("proxy") or item.get("type") or "")[:60]}
        return {"services": await asyncio.gather(*(inspect(source_id, source) for source_id, source in sources.items())), "driver_candidates": await asyncio.gather(*(inspect(item_id, candidate) for item_id, candidate in candidates.items())), "note": "Solo nomi dei campi e comandi; nessuna password, token o valore di account. Stato non ancora verificato."}

    @app.get("/api/admin/control4/service-discovery")
    async def admin_control4_service_discovery(request: Request) -> Response:
        require_admin(request)
        return JSONResponse(await control4_service_discovery(), headers={"Cache-Control": "no-store, private"})

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
    async def control4_artwork_support(token: str, services: bool = Query(False)) -> Response:
        expires = control4_support_tokens.pop(token, 0)
        if expires < time.monotonic():
            raise HTTPException(status_code=404, detail="Link diagnostico scaduto o già usato")
        result = await control4_service_discovery() if services else await control4_artwork_diagnostic()
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
        response.set_cookie(user_auth.COOKIE, user_auth.create_session("admin"), max_age=user_auth.SESSION_SECONDS, httponly=True, samesite="strict", secure=secure_cookie(request), path="/")
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
        response = JSONResponse({"ok": True})
        response.set_cookie(user_auth.COOKIE, user_auth.create_session(username), max_age=user_auth.SESSION_SECONDS, httponly=True, samesite="strict", secure=secure_cookie(request), path="/")
        return response

    @app.post("/api/auth/logout")
    async def auth_logout() -> JSONResponse:
        response = JSONResponse({"ok": True})
        response.delete_cookie(user_auth.COOKIE, path="/")
        return response

    @app.get("/login", include_in_schema=False)
    async def login_page() -> FileResponse:
        return FileResponse(STATIC / "login.html", headers={"Cache-Control": "no-store"})

    @app.get("/intercom", include_in_schema=False)
    async def intercom_page(request: Request) -> FileResponse:
        if not user_auth.session_user(request.cookies.get(user_auth.COOKIE)):
            raise HTTPException(status_code=401, detail="Accesso richiesto")
        return FileResponse(STATIC / "intercom.html", headers={"Cache-Control": "no-store"})

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
        providers = list(await asyncio.gather(*(connector.snapshot() for connector in connectors)))
        providers = [apply_preferences(provider) if provider.get("id") in {"evoice", "control4"} else provider for provider in providers]
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
            for media in (item for item in providers if item.get("id") in {"control4", "evoice"} and item.get("status") in {"online", "stale"}):
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
            "appearance": {"card_theme": load_card_theme(), "card_glow": load_card_glow(), "room_order": load_room_order(), "security_order": load_security_order()},
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
        selected = load_background()
        presets = {
            "teal": "linear-gradient(135deg,#84bfd5,#137073 58%,#0e4a4e)",
            "midnight": "radial-gradient(circle at 70% 20%,#263f61,#08121e 65%)",
            "graphite": "linear-gradient(145deg,#596066,#181c1f 65%)",
            "ocean": "radial-gradient(circle at 25% 20%,#43a8ca,#075079 48%,#03273e)",
            "warm": "radial-gradient(circle at 20% 20%,#b77955,#59372f 52%,#24191b)",
        }
        background = "linear-gradient(rgba(4,22,26,.28),rgba(4,22,26,.48)),url('api/user/background/image')" if selected["mode"] == "custom" else presets[selected["preset"]]
        page = (STATIC / "tools.html").read_text(encoding="utf-8")
        page = page.replace("__TOOLS_BACKGROUND__", escape(background, quote=True)).replace("__CARD_THEME__", escape(load_card_theme(), quote=True))
        return HTMLResponse(page, headers={"Cache-Control": "no-cache"})

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
        return {"card_glow": load_card_glow(), "room_order": load_room_order(), "security_order": load_security_order()}

    @app.put("/api/user/appearance")
    async def user_save_appearance(payload: dict) -> dict:
        try:
            if "card_glow" in payload: save_card_glow(payload["card_glow"])
            if "room_order" in payload: save_room_order(payload["room_order"])
            if "security_order" in payload: save_security_order(payload["security_order"])
        except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
        return {"card_glow": load_card_glow(), "room_order": load_room_order(), "security_order": load_security_order()}

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
        for player in (player for snapshot in snapshots for player in snapshot.get("items", [])):
            for source in player.get("source_options", []):
                source_id = int(source.get("source_id") or 0)
                if source_id > 0:
                    sources[source_id] = {"source_id": source_id, "name": str(source.get("label") or source_id), "custom": load_source_icon(source_id) is not None}
        return {"items": sorted(sources.values(), key=lambda item: item["name"].casefold())}

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
            operation = str(payload.get("action") or "")
            allowed = {"media_play", "media_pause", "media_stop", "turn_off", "media_next", "media_previous", "set_volume", "volume_mute", "volume_unmute", "select_source", "media_join", "media_unjoin", "video_remote", "tts", "set_dnd"}
            if operation not in allowed:
                raise HTTPException(status_code=400, detail="Comando multimedia non valido")
            if device_id.startswith("c4media:") and operation in {"tts", "set_dnd"}:
                raise HTTPException(status_code=400, detail="TTS e DND sono disponibili soltanto sui player e-Voice")
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
            return {"items": await connector.recently_played(room_ids, limit)}
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

    @app.get("/api/control4/source-icon/{source_id}", include_in_schema=False)
    async def control4_source_icon(source_id: int) -> Response:
        if source_id <= 0:
            raise HTTPException(status_code=404, detail="Icona Control4 non disponibile")
        custom = load_source_icon(source_id)
        if custom:
            return Response(custom[1], media_type=custom[0], headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"})
        builtin = load_builtin_source_icon(cached_control4_source_label(source_id))
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
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logging.warning("Ksenia realtime disconnected; retrying")
                    await asyncio.sleep(1)

        async def media_events(connector) -> None:
            while True:
                try:
                    async for event in connector.events():
                        event_type = str(event.get("type") or "")
                        if event_type == "local.player_updated":
                            await queue.put({"type": "media_state", "data": event.get("data") or {}})
                            continue
                        if event_type != "heartbeat":
                            await queue.put({"type": "media_changed", "event_type": event_type})
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logging.warning("%s realtime disconnected; retrying", connector.id)
                    await asyncio.sleep(2)

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
    async def frontend(path: str) -> FileResponse:
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    return app


def main() -> None:
    uvicorn.run(create_app(), host="0.0.0.0", port=8099, access_log=False)


if __name__ == "__main__":
    main()
