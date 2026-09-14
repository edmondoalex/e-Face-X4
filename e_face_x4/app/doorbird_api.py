"""Read-only DoorBird LAN checks using the per-installation credential."""

from __future__ import annotations

import httpx
import re

MAX_IMAGE_BYTES = 2 * 1024 * 1024
VIDEO_CONTENT_TYPE = re.compile(r"multipart/x-mixed-replace\s*;\s*boundary=[A-Za-z0-9_-]{1,70}\Z", re.I)


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
