"""DoorBird LAN media checks and bounded SIP setup using server-side credentials."""

from __future__ import annotations

import httpx
import re
import json
import os
import secrets
from urllib.parse import urlsplit, urlunsplit
from collections.abc import AsyncIterator
from pathlib import Path

MAX_IMAGE_BYTES = 2 * 1024 * 1024
VIDEO_CONTENT_TYPE = re.compile(r"multipart/x-mixed-replace\s*;\s*boundary=[A-Za-z0-9_-]{1,70}\Z", re.I)
SENSITIVE_FIELD = re.compile(r"password|passwd|secret|token|credential", re.I)


def _event_image_path(event: str) -> Path:
    if event not in {"doorbell", "motionsensor"}:
        raise ValueError("Evento DoorBird non valido")
    return Path(os.environ.get("EFACE_DOORBIRD_EVENT_DIR", "/data/doorbird-events")) / f"{event}.jpg"


def load_event_image(event: str) -> bytes | None:
    try:
        content = _event_image_path(event).read_bytes()
    except OSError:
        return None
    return content if content.startswith(b"\xff\xd8\xff") and len(content) <= MAX_IMAGE_BYTES else None


def save_event_image(event: str, content: bytes) -> None:
    if not content.startswith(b"\xff\xd8\xff") or not 16 <= len(content) <= MAX_IMAGE_BYTES:
        raise ValueError("Immagine DoorBird non valida")
    target = _event_image_path(event)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(content)
    os.chmod(temporary, 0o600)
    temporary.replace(target)


def _safe_configuration(value, key: str = "", reveal: bool = False):
    """Bound DoorBird data and hide secrets unless an admin explicitly re-authenticated."""
    if SENSITIVE_FIELD.search(key) and not reveal:
        return "configurato" if value not in (None, "", [], {}) else "non configurato"
    if isinstance(value, dict):
        return {str(k)[:80]: _safe_configuration(v, str(k), reveal) for k, v in list(value.items())[:100]}
    if isinstance(value, list):
        return [_safe_configuration(item, key, reveal) for item in value[:100]]
    if isinstance(value, str):
        text = value[:1000]
        if not reveal and "://" in text:
            try:
                parsed = urlsplit(text)
                if parsed.username or parsed.password:
                    host = parsed.hostname or ""
                    if parsed.port: host = f"{host}:{parsed.port}"
                    text = urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))
            except ValueError:
                return "valore oscurato"
        return text
    return value if isinstance(value, (int, float, bool)) or value is None else str(value)[:1000]


def _doorbell_sip_route(favorites, schedules, expected: str) -> dict:
    """Resolve doorbell schedule SIP IDs to their favorite destinations."""
    favorite_root = favorites.get("BHA", {}).get("FAVORITES", favorites) if isinstance(favorites, dict) else {}
    sip_root = favorite_root.get("sip", {}) if isinstance(favorite_root, dict) else {}
    sip_favorites = {}
    if isinstance(sip_root, dict):
        sip_favorites = {str(key): value for key, value in sip_root.items() if isinstance(value, dict)}
    elif isinstance(sip_root, list):
        sip_favorites = {str(value.get("id", index)): value for index, value in enumerate(sip_root) if isinstance(value, dict)}
    elif isinstance(favorite_root, list):
        sip_favorites = {str(value.get("id", index)): value for index, value in enumerate(favorite_root)
                         if isinstance(value, dict) and str(value.get("type", "")).lower() == "sip"}

    schedule_root = schedules.get("BHA", {}).get("SCHEDULE", schedules) if isinstance(schedules, dict) else schedules
    rules = schedule_root if isinstance(schedule_root, list) else []
    actions = []
    for rule in rules:
        if not isinstance(rule, dict) or str(rule.get("input", "")).lower() != "doorbell":
            continue
        for output in rule.get("output", []):
            if not isinstance(output, dict) or str(output.get("event", "")).lower() != "sip":
                continue
            favorite_id = str(output.get("param", ""))
            favorite = sip_favorites.get(favorite_id, {})
            destination = str(favorite.get("value", ""))
            active = str(output.get("enabled", "1")).lower() not in {"0", "false", "off"}
            normalized = destination.removeprefix("sip:").rstrip("/").lower()
            expected_normalized = expected.removeprefix("sip:").rstrip("/").lower()
            actions.append({
                "pulsante": str(rule.get("param", "1") or "1"),
                "azione_abilitata": active,
                "preferito_sip_id": favorite_id or "mancante",
                "titolo_preferito": favorite.get("title", "non trovato"),
                "destinazione": destination or "preferito non trovato",
                "destinazione_eface": bool(destination) and normalized == expected_normalized,
                "fasce_orarie": output.get("schedule", "non dichiarate"),
            })
    active = [action for action in actions if action["azione_abilitata"]]
    routes_eface = [action for action in active if action["destinazione_eface"]]
    if routes_eface:
        verdict = "SÌ: il pulsante ha un'azione SIP attiva verso e-Face"
    elif active:
        verdict = "NO: il pulsante chiama via SIP, ma verso una destinazione diversa da e-Face"
    elif actions:
        verdict = "NO: l'azione SIP del pulsante esiste ma è disabilitata"
    else:
        verdict = "NO: nella programmazione del pulsante non esiste alcuna azione SIP"
    return {
        "esito": verdict,
        "destinazione_eface_attesa": expected,
        "genera_chiamata_sip": bool(active),
        "genera_chiamata_sip_verso_eface": bool(routes_eface),
        "azioni_sip_pulsante": actions,
        "avvertenza": "La configurazione prova l'instradamento previsto; la ricezione effettiva si conferma soltanto premendo il pulsante e verificando un INVITE SIP su Asterisk.",
    }


async def configuration(host: str, port: int, username: str, password: str,
                        asterisk_host: str, ring_extension: str, reveal: bool = False) -> dict:
    """Read every configuration block exposed by the official DoorBird LAN API."""
    if not username or not password:
        raise ValueError("Credenziale DoorBird non configurata")
    resources = {
        "dispositivo": ("info.cgi", None),
        "sip": ("sip.cgi", {"action": "status"}),
        "preferiti": ("favorites.cgi", None),
        "programmazione": ("schedule.cgi", None),
    }
    result = {}
    async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
        for label, (path, params) in resources.items():
            try:
                response = await client.get(f"http://{host}:{port}/bha-api/{path}", params=params,
                                            auth=httpx.DigestAuth(username, password))
            except httpx.HTTPError as exc:
                raise ConnectionError("DoorBird non raggiungibile") from exc
            if response.status_code == 401:
                raise PermissionError("La credenziale DoorBird non ha il permesso API operator")
            if response.status_code != 200:
                result[label] = {"errore": f"HTTP {response.status_code}"}
                continue
            if len(response.content) > 256_000:
                result[label] = {"errore": "Risposta troppo grande"}
                continue
            try:
                result[label] = _safe_configuration(response.json(), reveal=reveal)
            except ValueError:
                result[label] = {"errore": "Risposta non JSON"}
    try:
        sip = result["sip"]["BHA"]["SIP"][0]
    except (KeyError, IndexError, TypeError):
        sip = {}
    expected = f"sip:{ring_extension}@{asterisk_host}"
    result["verifica_pulsante_sip"] = _doorbell_sip_route(
        result.get("preferiti", {}), result.get("programmazione", []), expected,
    )
    proxy = str(sip.get("URL") or sip.get("PROXY") or sip.get("SIP_PROXY") or "")
    autocall = str(sip.get("AUTOCALL_DOORBELL_URL") or "")
    authorized = str(sip.get("INCOMING_CALL_USER") or "")
    result["verifica_eface"] = {
        "destinazione_attesa": expected,
        "proxy_sip": proxy or "non dichiarato",
        "asterisk_autorizzato": asterisk_host in re.split(r"[,;\s]+", authorized),
        "chiamata_automatica_legacy": autocall or "none",
        "destinazione_legacy_corretta": autocall == expected,
        "nota": "La destinazione legacy non dimostra che la programmazione moderna del pulsante sia attiva.",
    }
    try:
        version = result["dispositivo"]["BHA"]["VERSION"][0]
    except (KeyError, IndexError, TypeError):
        version = {}
    result["rele_e_controller"] = {
        "rele_esposti": version.get("RELAYS", []),
        "nota": "Comprende i relè fisici e gli eventuali Door Controller abbinati dichiarati da info.cgi.",
    }
    result["copertura_api_lan"] = {
        "letti": [
            "Dispositivo, firmware, MAC, modello e relè/controller (info.cgi)",
            "Configurazione e stato SIP (sip.cgi?action=status)",
            "Tutti i preferiti SIP e HTTP (favorites.cgi)",
            "Tutte le regole per campanello, movimento, RFID, impronta, notifiche, SIP, HTTP e relè (schedule.cgi)",
        ],
        "non_esposti_da_doorbird": [
            "Password SIP in chiaro, se il firmware non la restituisce nello stato SIP",
            "Impostazioni disponibili soltanto nel portale/app DoorBird (cloud, utenti, badge/PIN completi, rete e parametri Esperto non presenti nei quattro endpoint ufficiali)",
        ],
        "sola_lettura": True,
    }
    return result


async def monitor_events(host: str, port: int, username: str, password: str) -> AsyncIterator[str]:
    """Yield DoorBird LAN ring events from one long-lived monitor connection."""
    if not username or not password:
        raise ValueError("Credenziale DoorBird non configurata")
    url = f"http://{host}:{port}/bha-api/monitor.cgi"
    timeout = httpx.Timeout(10, read=None)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            async with client.stream("GET", url, params={"ring": "doorbell,motionsensor"},
                                     auth=httpx.DigestAuth(username, password)) as response:
                if response.status_code == 401:
                    raise PermissionError("Credenziale DoorBird rifiutata")
                if response.status_code != 200:
                    raise RuntimeError(f"Monitor DoorBird non disponibile (HTTP {response.status_code})")
                pending = ""
                async for chunk in response.aiter_text():
                    pending = (pending + chunk)[-4096:]
                    while True:
                        match = re.search(r"(doorbell|motionsensor):([HL])", pending, re.I)
                        if not match:
                            break
                        pending = pending[match.end():]
                        if match.group(2).upper() == "H":
                            yield match.group(1).lower()
    except httpx.HTTPError as exc:
        raise ConnectionError("DoorBird non raggiungibile") from exc


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


async def make_call(host: str, port: int, username: str, password: str, sip_url: str) -> None:
    """Ask DoorBird to place a SIP call to a validated local target."""
    if not re.fullmatch(r"sip:[0-9]{2,6}@[A-Za-z0-9.-]{1,253}", sip_url):
        raise ValueError("Destinazione SIP DoorBird non valida")
    async with httpx.AsyncClient(timeout=8, follow_redirects=False, trust_env=False) as client:
        response = await client.get(f"http://{host}:{port}/bha-api/sip.cgi",
                                    params={"action": "makecall", "url": sip_url},
                                    auth=httpx.DigestAuth(username, password))
    if response.status_code == 401:
        raise PermissionError("Credenziale DoorBird rifiutata")
    if response.status_code != 200:
        raise RuntimeError(f"Chiamata DoorBird rifiutata (HTTP {response.status_code})")


async def save_http_favorite(host: str, port: int, username: str, password: str,
                             title: str, value: str) -> str:
    """Create a DoorBird HTTP favorite and return its assigned id."""
    async with httpx.AsyncClient(timeout=8, follow_redirects=False, trust_env=False) as client:
        response = await client.get(
            f"http://{host}:{port}/bha-api/favorites.cgi",
            params={"action": "save", "type": "http", "title": title, "value": value},
            auth=httpx.DigestAuth(username, password),
        )
    if response.status_code == 401: raise PermissionError("Credenziale DoorBird rifiutata")
    if response.status_code != 200: raise RuntimeError(f"Preferito DoorBird rifiutato (HTTP {response.status_code})")
    favorite_id = str(response.headers.get("favoriteid") or "").strip()
    if not favorite_id.isdigit(): raise RuntimeError("DoorBird non ha restituito l'identificativo del preferito")
    return favorite_id


async def save_schedule(host: str, port: int, username: str, password: str, schedule: dict) -> None:
    """Replace one DoorBird input schedule with the supplied complete definition."""
    async with httpx.AsyncClient(timeout=8, follow_redirects=False, trust_env=False) as client:
        response = await client.post(
            f"http://{host}:{port}/bha-api/schedule.cgi", json=schedule,
            auth=httpx.DigestAuth(username, password),
        )
    if response.status_code == 401: raise PermissionError("Credenziale DoorBird rifiutata")
    if response.status_code != 200: raise RuntimeError(f"Programmazione DoorBird rifiutata (HTTP {response.status_code})")


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
                if response.status_code in {204, 404}:
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
            # DoorBird LAN API defines exactly these two history values:
            # ``doorbell`` for calls and ``motionsensor`` for motion events.
            params = {"event": event, "index": 1}
            async with client.stream("GET", url, params=params, auth=httpx.DigestAuth(username, password)) as response:
                if response.status_code == 204:
                    # Some models keep ring history only in the DoorBird cloud
                    # (visible in the app) and expose no local historical JPEG.
                    # Return the current protected camera frame so the Home
                    # widget remains useful instead of showing an empty card.
                    content = await live_image(host, port, username, password) if event == "doorbell" else None
                    if content:
                        save_event_image(event, content)
                    return content
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
