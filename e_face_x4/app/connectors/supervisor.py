from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx
import ipaddress


_host_cache: dict[int, tuple[float, str]] = {}
_host_tasks: dict[int, asyncio.Task[str]] = {}
HOST_CACHE_TTL = 300.0
HOST_FAILURE_TTL = 30.0


def clear_discovery_cache() -> None:
    """Clear process-local discovery state (also useful for isolated tests)."""
    _host_cache.clear()
    _host_tasks.clear()


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
    """Legacy hook retained for callers; add-on inventory is not available to apps.

    Runtime discovery must use configured URLs or the permitted host-network
    endpoint.  Calling ``/addons`` from an add-on produces a permanent 401 loop.
    """
    return ""


async def installed_addons(timeout_s: float) -> list[dict[str, Any]]:
    """Add-on inventory is intentionally unavailable to an app-scoped token."""
    return []


def find_host_url(payload: dict[str, Any], port: int) -> str:
    """Return the first usable e-Control host address from Supervisor data."""
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    interfaces = data.get("interfaces") if isinstance(data, dict) else None
    if not isinstance(interfaces, list):
        return ""
    for interface in interfaces:
        if not isinstance(interface, dict) or interface.get("enabled") is False:
            continue
        ipv4 = interface.get("ipv4")
        addresses = ipv4.get("address") if isinstance(ipv4, dict) else None
        if isinstance(addresses, str):
            addresses = [addresses]
        if not isinstance(addresses, list):
            continue
        for value in addresses:
            try:
                address = ipaddress.ip_interface(str(value)).ip
            except ValueError:
                continue
            if not address.is_loopback and not address.is_link_local:
                return f"http://{address}:{port}"
    return ""


async def discover_host_url(port: int, timeout_s: float) -> str:
    token = str(os.environ.get("SUPERVISOR_TOKEN") or "").strip()
    if not token:
        return ""
    now = time.monotonic()
    cached = _host_cache.get(port)
    if cached and now - cached[0] < (HOST_CACHE_TTL if cached[1] else HOST_FAILURE_TTL):
        return cached[1]

    async def fetch() -> str:
        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=False) as client:
            response = await client.get(
                "http://supervisor/network/info",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            payload = response.json()
        return find_host_url(payload, port) if isinstance(payload, dict) else ""

    task = _host_tasks.get(port)
    if task is None or task.done():
        task = asyncio.create_task(fetch())
        _host_tasks[port] = task
    try:
        result = await asyncio.shield(task)
    except (httpx.HTTPError, ValueError):
        result = cached[1] if cached else ""
    finally:
        if _host_tasks.get(port) is task and task.done():
            _host_tasks.pop(port, None)
    _host_cache[port] = (time.monotonic(), result)
    return result
