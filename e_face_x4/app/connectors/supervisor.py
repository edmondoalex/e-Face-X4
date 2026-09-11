from __future__ import annotations

import os
from typing import Any

import httpx


def find_addon_url(payload: dict[str, Any], target_slug: str, port: int) -> str:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    addons = data.get("addons") if isinstance(data, dict) else None
    if not isinstance(addons, list):
        return ""
    target = target_slug.strip().lower()
    for addon in addons:
        if not isinstance(addon, dict):
            continue
        slug = str(addon.get("slug") or "").strip().lower()
        if slug == target or slug.endswith(f"_{target}"):
            return f"http://{slug.replace('_', '-')}:{port}"
    return ""


async def discover_addon_url(target_slug: str, port: int, timeout_s: float) -> str:
    token = str(os.environ.get("SUPERVISOR_TOKEN") or "").strip()
    if not token:
        return ""
    try:
        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=False) as client:
            response = await client.get(
                "http://supervisor/addons",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            payload = response.json()
        return find_addon_url(payload, target_slug, port) if isinstance(payload, dict) else ""
    except (httpx.HTTPError, ValueError):
        return ""
