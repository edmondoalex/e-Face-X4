"""Pinned-TLS client for the controlled Asterisk e-Face provisioner."""

from __future__ import annotations

import asyncio
import hashlib
import http.client
import ipaddress
import json
import os
import re
import secrets
import ssl
from pathlib import Path

from .intercom_settings import PRIVATE_NETWORKS


def _path() -> Path:
    return Path(os.environ.get("EFACE_PROVISIONER_SETTINGS", "/data/asterisk_provisioner.json"))


def load() -> dict:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def public() -> dict:
    data = load()
    return {"configured": bool(data.get("token") and data.get("fingerprint")),
            "host": data.get("host", ""), "port": data.get("port", 9443),
            "fingerprint": data.get("fingerprint", "")}


def validate(payload: dict) -> dict:
    if set(payload) != {"host", "port", "token", "fingerprint"}:
        raise ValueError("Associazione Asterisk incompleta")
    host = str(payload["host"]).strip()
    try:
        ip = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("IP Asterisk non valido") from exc
    if ip.version != 4 or not any(ip in network for network in PRIVATE_NETWORKS):
        raise ValueError("Usa un IP Asterisk privato")
    port = payload["port"]
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("Porta Asterisk non valida")
    token = str(payload["token"]).strip() or load().get("token", "")
    fingerprint = str(payload["fingerprint"]).strip().lower().replace(":", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{48,128}", token) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ValueError("Token o impronta TLS non validi")
    return {"host": host, "port": port, "token": token, "fingerprint": fingerprint}


def save(payload: dict) -> dict:
    value = validate(payload)
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"asterisk_provisioner.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            os.chmod(temporary, 0o600)
            json.dump(value, file)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return public()


def _request(method: str, path: str, payload: dict | None = None, config: dict | None = None) -> dict:
    config = config or load()
    if not config.get("token") or not config.get("fingerprint"):
        raise RuntimeError("Asterisk non associato a e-Face")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # Exact certificate pin checked before sending the token.
    connection = http.client.HTTPSConnection(config["host"], config["port"], timeout=8, context=context)
    try:
        connection.connect()
        certificate = connection.sock.getpeercert(binary_form=True)
        if not certificate or hashlib.sha256(certificate).hexdigest() != config["fingerprint"]:
            raise RuntimeError("Impronta TLS Asterisk diversa: associazione rifiutata")
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        connection.request(method, path, body=body, headers={
            "Authorization": f"Bearer {config['token']}", "Content-Type": "application/json"})
        response = connection.getresponse()
        raw = response.read(8192)
        data = json.loads(raw) if raw else {}
        if response.status != 200:
            raise RuntimeError(str(data.get("error") or f"Provisioner Asterisk: HTTP {response.status}"))
        return data
    finally:
        connection.close()


async def request(method: str, path: str, payload: dict | None = None, config: dict | None = None) -> dict:
    return await asyncio.to_thread(_request, method, path, payload, config)
