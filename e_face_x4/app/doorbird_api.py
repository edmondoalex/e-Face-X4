"""Read-only DoorBird LAN checks using the per-installation credential."""

from __future__ import annotations

import httpx


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
