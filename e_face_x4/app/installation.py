"""Read-only installation checks; no SIP or device configuration is changed."""

from __future__ import annotations

import asyncio
import secrets
import socket
from urllib.parse import urlsplit

from . import intercom_settings


async def _tcp_reachable(host: str, port: int) -> bool:
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=2)
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


def _stun_binding(host: str, port: int) -> bool:
    """A STUN response proves that UDP 3478 is reachable, not TURN authentication."""
    transaction = secrets.token_bytes(12)
    request = b"\x00\x01\x00\x00\x21\x12\xa4\x42" + transaction
    try:
        addresses = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_DGRAM)
        for family, kind, protocol, _, address in addresses:
            with socket.socket(family, kind, protocol) as udp:
                udp.settimeout(2)
                udp.sendto(request, address)
                response, sender = udp.recvfrom(2048)
                if (
                    sender[0] == address[0]
                    and len(response) >= 20
                    and response[:2] == b"\x01\x01"
                    and response[4:8] == b"\x21\x12\xa4\x42"
                    and response[8:20] == transaction
                ):
                    return True
    except (OSError, TimeoutError):
        return False
    return False


async def preflight() -> dict:
    settings = intercom_settings.load()
    turn = intercom_settings.load_turn()
    asterisk, doorbird = await asyncio.gather(
        _tcp_reachable(settings["asterisk_host"], settings["asterisk_port"]),
        _tcp_reachable(settings["doorbird_host"], settings["doorbird_port"]),
    )
    turn_configured = bool(turn["turn_url"] and turn["turn_username"] and turn["turn_password"])
    turn_udp = False
    turn_udp_tested = False
    if turn_configured and turn["turn_url"].startswith("turn:"):
        parsed = urlsplit("turn://" + turn["turn_url"][5:])
        if parsed.hostname and (parsed.query in ("", "transport=udp")):
            try:
                port = parsed.port or 3478
            except ValueError:
                port = None
            if port:
                turn_udp_tested = True
                turn_udp = await asyncio.to_thread(_stun_binding, parsed.hostname, port)
    return {
        "asterisk_tcp": asterisk,
        "doorbird_tcp": doorbird,
        "turn_configured": turn_configured,
        "turn_udp": turn_udp,
        "turn_udp_tested": turn_udp_tested,
        "provisioning_available": False,
        "audio_call_tested": False,
    }
