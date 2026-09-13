"""Small, bounded AMI client for the e-Face SIP credential workflow.

No AMI connection is opened unless explicitly requested by an administrator.
The manager account must be restricted to the e-Face host by Asterisk ACL.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping


class AMIError(RuntimeError):
    pass


_FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9-]*$")


def _request(fields: Mapping[str, str]) -> bytes:
    lines = []
    for key, value in fields.items():
        if not _FIELD.fullmatch(key) or any(character in value for character in "\r\n\x00"):
            raise ValueError("Campo AMI non valido")
        lines.append(f"{key}: {value}\r\n")
    return ("".join(lines) + "\r\n").encode("utf-8")


async def _response(reader: asyncio.StreamReader) -> dict[str, str]:
    result: dict[str, str] = {}
    while True:
        line = await reader.readline()
        if not line:
            raise AMIError("Connessione AMI interrotta")
        if line == b"\r\n":
            return result
        key, separator, value = line.decode("utf-8", errors="replace").partition(": ")
        if separator:
            result[key] = value.rstrip("\r\n")


async def action(host: str, port: int, username: str, secret: str, fields: Mapping[str, str], *, timeout: float = 5) -> dict[str, str]:
    """Perform one AMI action; never log the login secret or response fields."""
    if not username or not secret or not 1 <= port <= 65535:
        raise ValueError("Configurazione AMI incompleta")
    async with asyncio.timeout(timeout):
        reader, writer = await asyncio.open_connection(host, port)
        try:
            greeting = await reader.readline()
            if not greeting.startswith(b"Asterisk Call Manager/"):
                raise AMIError("Server AMI non riconosciuto")
            writer.write(_request({"Action": "Login", "Username": username, "Secret": secret, "Events": "off"}))
            await writer.drain()
            login = await _response(reader)
            if login.get("Response") != "Success":
                raise AMIError("Autenticazione AMI non riuscita")
            writer.write(_request(fields))
            await writer.drain()
            result = await _response(reader)
            if result.get("Response") != "Success":
                raise AMIError(result.get("Message", "Azione AMI non riuscita"))
            return result
        finally:
            writer.close()
            await writer.wait_closed()


async def read_8301_auth(host: str, port: int, username: str, secret: str) -> dict[str, str]:
    """Read only the persistent e-Face auth category, never the other SIP users."""
    return await action(host, port, username, secret, {
        "Action": "GetConfig", "Filename": "pjsip_custom.conf", "Category": "8301",
        "Filter": "username=8301",
    })
