"""Pinned-TLS client for the future Asterisk-side SIP provisioner.

Not wired to user provisioning yet. The certificate fingerprint and Bearer
token must come from an authenticated, per-installation pairing process.
"""

from __future__ import annotations

import hashlib
import hmac
import http.client
import ipaddress
import json
import re
import ssl

_USER = re.compile(r"[a-z][a-z0-9_-]{2,31}\Z")
_FINGERPRINT = re.compile(r"[0-9a-fA-F]{64}\Z")


class ProvisionerClient:
    def __init__(self, host: str, port: int, certificate_sha256: str, token: str) -> None:
        address = ipaddress.IPv4Address(host)
        if address.is_unspecified or address.is_multicast or not (address.is_private or address.is_loopback):
            raise ValueError("Indirizzo Asterisk non locale")
        if not 1 <= port <= 65535:
            raise ValueError("Porta Asterisk non valida")
        if not _FINGERPRINT.fullmatch(certificate_sha256):
            raise ValueError("Impronta certificato non valida")
        if len(token) < 32:
            raise ValueError("Token provisioner non valido")
        self.host = host
        self.port = port
        self.certificate_sha256 = certificate_sha256.lower()
        self.token = token

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE  # Exact certificate pin is verified before any HTTP bytes.
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        connection = http.client.HTTPSConnection(self.host, self.port, context=context, timeout=6)
        try:
            connection.connect()
            certificate = connection.sock.getpeercert(binary_form=True) if connection.sock else None
            actual = hashlib.sha256(certificate).hexdigest() if certificate else ""
            if not hmac.compare_digest(actual, self.certificate_sha256):
                raise RuntimeError("Certificato Asterisk diverso da quello associato")
            body = json.dumps(payload).encode("utf-8") if payload is not None else None
            connection.request(
                method, path, body=body,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                    "Cache-Control": "no-store",
                },
            )
            response = connection.getresponse()
            content = response.read(8193)
            if len(content) > 8192 or response.status != 200:
                raise RuntimeError("Provisioning Asterisk non confermato")
            result = json.loads(content)
            if not isinstance(result, dict):
                raise RuntimeError("Risposta provisioner non valida")
            return result
        finally:
            connection.close()

    def upsert(self, username: str, extension: str, password: str, name: str) -> None:
        if not _USER.fullmatch(username):
            raise ValueError("Nome utente non valido")
        result = self._request("POST", "/v1/phones", {
            "username": username, "extension": extension, "password": password, "name": name,
        })
        if result.get("extension") != extension or result.get("provisioned") is not True:
            raise RuntimeError("Interno Asterisk non confermato")

    def revoke(self, username: str) -> bool:
        if not _USER.fullmatch(username):
            raise ValueError("Nome utente non valido")
        result = self._request("DELETE", f"/v1/phones/{username}")
        if not isinstance(result.get("removed"), bool):
            raise RuntimeError("Revoca Asterisk non confermata")
        return result["removed"]
