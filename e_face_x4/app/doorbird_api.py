"""DoorBird LAN media checks and bounded SIP setup using server-side credentials."""

from __future__ import annotations

import httpx
import re
import json
import os
import secrets
from pathlib import Path

MAX_IMAGE_BYTES = 2 * 1024 * 1024
VIDEO_CONTENT_TYPE = re.compile(r"multipart/x-mixed-replace\s*;\s*boundary=[A-Za-z0-9_-]{1,70}\Z", re.I)


async def sip_status(host: str, port: int, username: str, password: str) -> dict:
    """Read SIP status with API-operator credentials, without changing settings."""
    async with httpx.AsyncClient(timeout=8, follow_redirects=False, trust_env=False) as client:
        response = await client.get(f"http://{host}:{port}/bha-api/sip.cgi",
                                    params={"action": "status"}, auth=httpx.DigestAuth(username, password))
    if response.status_code == 401:
        raise PermissionError("La credenziale DoorBird non ha il permesso API operator")
    if response.status_code != 200:
        raise RuntimeError("Stato SIP DoorBird non disponibile")
    try:
        return response.json()["BHA"]["SIP"][0]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Risposta SIP DoorBird non valida") from exc


async def _sip_settings(host: str, port: int, username: str, password: str, settings: dict) -> None:
    async with httpx.AsyncClient(timeout=8, follow_redirects=False, trust_env=False) as client:
        response = await client.get(f"http://{host}:{port}/bha-api/sip.cgi",
                                    params={"action": "settings", **settings}, auth=httpx.DigestAuth(username, password))
    if response.status_code == 401:
        raise PermissionError("La credenziale DoorBird non ha il permesso API operator")
    if response.status_code != 200:
        raise RuntimeError("Configurazione SIP DoorBird rifiutata")


async def ensure_incoming_sip(station_id: str, host: str, port: int, username: str,
                              password: str, asterisk_host: str,
                              ring_extension: str = "8290") -> dict | None:
    """Authorize Asterisk and route doorbell presses to the e-Face ring group."""
    before = await sip_status(host, port, username, password)
    previous = {"enable": str(before.get("ENABLE", "0")),
                "incoming_call_enable": str(before.get("INCOMING_CALL_ENABLE", "0")),
                "incoming_call_user": str(before.get("INCOMING_CALL_USER", "")),
                "autocall_doorbell_url": str(before.get("AUTOCALL_DOORBELL_URL", "none"))}
    desired = {"enable": "1", "incoming_call_enable": "1", "incoming_call_user": asterisk_host,
               "autocall_doorbell_url": f"sip:{ring_extension}@{asterisk_host}"}
    if previous == desired:
        return None
    directory = Path(os.environ.get("EFACE_DOORBIRD_SIP_BACKUPS", "/data/doorbird_sip_backups"))
    directory.mkdir(parents=True, exist_ok=True)
    backup = directory / f"{station_id}.{secrets.token_hex(8)}.json"
    with backup.open("x", encoding="utf-8") as file:
        os.chmod(backup, 0o600)
        json.dump(before, file)
        file.flush()
        os.fsync(file.fileno())
    try:
        await _sip_settings(host, port, username, password, desired)
        after = await sip_status(host, port, username, password)
        if any(str(after.get(field, "none" if field == "AUTOCALL_DOORBELL_URL" else "")) != value for field, value in
               (("ENABLE", "1"), ("INCOMING_CALL_ENABLE", "1"), ("INCOMING_CALL_USER", asterisk_host),
                ("AUTOCALL_DOORBELL_URL", desired["autocall_doorbell_url"]))):
            raise RuntimeError("DoorBird non ha confermato l'instradamento SIP del pulsante")
    except Exception:
        try:
            await restore_incoming_sip(host, port, username, password, previous)
        except Exception:
            pass  # The persistent backup remains available for recovery.
        raise
    return previous


async def restore_incoming_sip(host: str, port: int, username: str, password: str, previous: dict) -> None:
    await _sip_settings(host, port, username, password, previous)


async def live_video(host: str, port: int, username: str, password: str):
    """Open DoorBird MJPEG; caller must close both the response and client."""
    if not username or not password:
        raise ValueError("Credenziale DoorBird non configurata")
    client = httpx.AsyncClient(timeout=httpx.Timeout(10, read=12), follow_redirects=False, trust_env=False)
    try:
        request = client.build_request("GET", f"http://{host}:{port}/bha-api/video.cgi")
        response = await client.send(request, auth=httpx.DigestAuth(username, password), stream=True)
        if response.status_code == 204:
            await response.aclose()
            await client.aclose()
            return None
        if response.status_code == 401:
            raise PermissionError("Credenziale DoorBird rifiutata")
        content_type = response.headers.get("content-type", "").strip()
        if response.status_code != 200 or not VIDEO_CONTENT_TYPE.fullmatch(content_type):
            raise RuntimeError("Video DoorBird non disponibile")
        return client, response, content_type
    except (PermissionError, RuntimeError):
        if "response" in locals():
            await response.aclose()
        await client.aclose()
        raise
    except httpx.HTTPError as exc:
        if "response" in locals():
            await response.aclose()
        await client.aclose()
        raise ConnectionError("DoorBird non raggiungibile") from exc
    except BaseException:
        if "response" in locals():
            await response.aclose()
        await client.aclose()
        raise


async def live_image(host: str, port: int, username: str, password: str) -> bytes | None:
    """Fetch one bounded JPEG frame; None means DoorBird denies viewing right now."""
    if not username or not password:
        raise ValueError("Credenziale DoorBird non configurata")
    url = f"http://{host}:{port}/bha-api/image.cgi"
    try:
        async with httpx.AsyncClient(timeout=6, follow_redirects=False, trust_env=False) as client:
            async with client.stream("GET", url, auth=httpx.DigestAuth(username, password)) as response:
                if response.status_code == 204:
                    return None
                if response.status_code == 401:
                    raise PermissionError("Credenziale DoorBird rifiutata")
                if response.status_code != 200 or response.headers.get("content-type", "").split(";", 1)[0].lower() != "image/jpeg":
                    raise RuntimeError("Immagine DoorBird non disponibile")
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_IMAGE_BYTES:
                        raise RuntimeError("Immagine DoorBird troppo grande")
    except httpx.HTTPError as exc:
        raise ConnectionError("DoorBird non raggiungibile") from exc
    if not content.startswith(b"\xff\xd8\xff"):
        raise RuntimeError("Risposta DoorBird non JPEG")
    return bytes(content)

async def history_image(host: str, port: int, username: str, password: str, event: str) -> bytes | None:
    """Fetch the latest bounded DoorBird doorbell or motion history JPEG."""
    if event not in {"doorbell", "motionsensor"}: raise ValueError("Evento DoorBird non valido")
    if not username or not password: raise ValueError("Credenziale DoorBird non configurata")
    url = f"http://{host}:{port}/bha-api/history.cgi"
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False, trust_env=False) as client:
            # Omitting ``event`` is DoorBird's canonical request for the latest
            # ring image and is compatible with older firmware/models.
            params = {"index": 1} if event == "doorbell" else {"event": event, "index": 1}
            async with client.stream("GET", url, params=params, auth=httpx.DigestAuth(username, password)) as response:
                if response.status_code == 204: return None
                if response.status_code == 401: raise PermissionError("Credenziale o permesso cronologia DoorBird rifiutato")
                if response.status_code != 200 or response.headers.get("content-type", "").split(";", 1)[0].lower() != "image/jpeg": raise RuntimeError("Cronologia DoorBird non disponibile")
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_IMAGE_BYTES: raise RuntimeError("Immagine DoorBird troppo grande")
    except httpx.HTTPError as exc: raise ConnectionError("DoorBird non raggiungibile") from exc
    if not content.startswith(b"\xff\xd8\xff"): raise RuntimeError("Risposta DoorBird non JPEG")
    return bytes(content)


async def check_identity(host: str, port: int, username: str, password: str) -> dict[str, str | bool]:
    """Authenticate without changing DoorBird configuration or exposing the secret."""
    if not username or not password:
        raise ValueError("Credenziale DoorBird non configurata")
    url = f"http://{host}:{port}/bha-api/info.cgi"
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=False, trust_env=False) as client:
            challenge = await client.get(url)
            if challenge.status_code != 200 and challenge.status_code != 401:
                return {"reachable": True, "authenticated": False, "reason": "http_error"}
            if challenge.status_code != 401:
                return {"reachable": True, "authenticated": False, "reason": "no_auth_challenge"}
            response = await client.get(url, auth=httpx.DigestAuth(username, password))
    except httpx.HTTPError:
        return {"reachable": False, "authenticated": False, "reason": "network"}
    if response.status_code == 401:
        return {"reachable": True, "authenticated": False, "reason": "authentication"}
    if response.status_code != 200:
        return {"reachable": True, "authenticated": False, "reason": "http_error"}
    try:
        data = response.json()
    except ValueError:
        return {"reachable": True, "authenticated": False, "reason": "invalid_response"}
    if not isinstance(data, dict) or not isinstance(data.get("BHA"), dict) or data["BHA"].get("RETURNCODE") != "1":
        return {"reachable": True, "authenticated": False, "reason": "invalid_response"}
    return {"reachable": True, "authenticated": True, "reason": "ok"}
