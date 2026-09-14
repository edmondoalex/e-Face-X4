"""Restricted local HTTP interface for the future Asterisk-side provisioner.

This module is deliberately not started by the current Asterisk add-on.
The add-on must supply its own endpoint/reload adapter and per-site token.
"""

from __future__ import annotations

import hmac
import ipaddress
import json
import re
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from .managed_config import ManagedConfig
from .external_routes import ExternalRoutes, reload_dialplan, extension_exists
from .control4_routes import Control4Routes

_USER = re.compile(r"[a-z][a-z0-9_-]{2,31}\Z")
_MAX_BODY = 4096


def make_handler(
    config: ManagedConfig,
    token: str,
    reload_pjsip: Callable[[], None],
    endpoint_exists: Callable[[str], bool],
    external_routes: ExternalRoutes | None = None,
    control4_routes: Control4Routes | None = None,
) -> type[BaseHTTPRequestHandler]:
    if len(token) < 32:
        raise ValueError("Token provisioner mancante o troppo corto")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            # Paths, headers and request bodies may contain installation data.
            pass

        def _reply(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            supplied = self.headers.get("Authorization", "")
            if not hmac.compare_digest(supplied, f"Bearer {token}"):
                self._reply(401, {"error": "Non autorizzato"})
                return False
            return True

        def _json_body(self) -> dict | None:
            try:
                length = int(self.headers.get("Content-Length", ""))
                if not 0 < length <= _MAX_BODY:
                    raise ValueError
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict):
                    raise ValueError
                return value
            except (ValueError, UnicodeDecodeError):
                self._reply(400, {"error": "Richiesta non valida"})
                return None

        def do_POST(self) -> None:
            if not self._authorized():
                return
            if self.path not in ("/v1/phones", "/v1/voip-phones"):
                self._reply(404, {"error": "Operazione sconosciuta"})
                return
            payload = self._json_body()
            if payload is None:
                return
            voip = self.path == "/v1/voip-phones"
            expected = {"username", "extension", "password", "name", "profile"} if voip else {"username", "extension", "password", "name"}
            if set(payload) != expected or not all(
                isinstance(value, str) for value in payload.values()
            ):
                self._reply(400, {"error": "Campi non validi"})
                return
            try:
                config.upsert(**payload, reload_pjsip=reload_pjsip, endpoint_exists=endpoint_exists)
            except ValueError:
                self._reply(400, {"error": "Interno non valido o già assegnato"})
                return
            except Exception:
                self._reply(503, {"error": "Provisioning non confermato"})
                return
            self._reply(200, {"extension": payload["extension"], "provisioned": True})

        def do_GET(self) -> None:
            if not self._authorized():
                return
            if self.path == "/v1/voip-phones":
                phones = config.load()
                self._reply(200, {"phones": [
                    {"extension": record["extension"], "name": record["name"], "profile": record["profile"]}
                    for record in phones.values() if record.get("profile", "browser") != "browser"
                ]})
                return
            if self.path == "/v1/external-stations" and external_routes is not None:
                self._reply(200, {"stations": external_routes.load()})
            elif self.path == "/v1/control4-tablets" and control4_routes is not None:
                self._reply(200, {"tablets": control4_routes.load()})
            else:
                self._reply(404, {"error": "Operazione sconosciuta"})

        def do_PUT(self) -> None:
            if not self._authorized():
                return
            if self.path not in ("/v1/external-stations", "/v1/control4-tablets"):
                self._reply(404, {"error": "Operazione sconosciuta"})
                return
            if self.path == "/v1/control4-tablets":
                if control4_routes is None:
                    self._reply(404, {"error": "Operazione sconosciuta"})
                    return
                payload = self._json_body()
                if payload is None:
                    return
                if set(payload) != {"tablets"}:
                    self._reply(400, {"error": "Elenco tablet non valido"})
                    return
                try:
                    tablets = control4_routes.replace(payload["tablets"])
                except ValueError as exc:
                    self._reply(400, {"error": str(exc)})
                    return
                except Exception:
                    self._reply(503, {"error": "Rotte Control4 non confermate"})
                    return
                self._reply(200, {"tablets": tablets, "provisioned": True})
                return
            if external_routes is None:
                self._reply(404, {"error": "Operazione sconosciuta"})
                return
            payload = self._json_body()
            if payload is None:
                return
            if set(payload) != {"stations"}:
                self._reply(400, {"error": "Elenco postazioni non valido"})
                return
            try:
                external_routes.replace(payload["stations"], reload_dialplan, extension_exists)
            except ValueError as exc:
                self._reply(400, {"error": str(exc)})
                return
            except Exception:
                self._reply(503, {"error": "Rotte SIP non confermate"})
                return
            self._reply(200, {"stations": external_routes.load(), "provisioned": True})

        def do_DELETE(self) -> None:
            if not self._authorized():
                return
            voip = self.path.startswith("/v1/voip-phones/")
            prefix = "/v1/voip-phones/" if voip else "/v1/phones/"
            username = self.path[len(prefix):] if self.path.startswith(prefix) else ""
            if not _USER.fullmatch(username):
                self._reply(404, {"error": "Operazione sconosciuta"})
                return
            if voip and not username.startswith("voip_"):
                self._reply(404, {"error": "Operazione sconosciuta"})
                return
            if not voip and username.startswith("voip_"):
                self._reply(404, {"error": "Operazione sconosciuta"})
                return
            try:
                removed = config.revoke(username, reload_pjsip, endpoint_exists)
            except Exception:
                self._reply(503, {"error": "Revoca non confermata"})
                return
            self._reply(200, {"removed": removed})

    return Handler


def serve_local(
    config: ManagedConfig,
    token: str,
    reload_pjsip: Callable[[], None],
    endpoint_exists: Callable[[str], bool],
    port: int,
) -> None:
    """Bind only loopback; external exposure requires a separate trusted proxy."""
    handler = make_handler(config, token, reload_pjsip, endpoint_exists)
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        server.serve_forever()


def make_https_server(
    config: ManagedConfig,
    token: str,
    reload_pjsip: Callable[[], None],
    endpoint_exists: Callable[[str], bool],
    bind_host: str,
    port: int,
    certificate: Path,
    private_key: Path,
    external_routes: ExternalRoutes | None = None,
    control4_routes: Control4Routes | None = None,
) -> ThreadingHTTPServer:
    """Create a TLS-only service on one explicit local IPv4 address.

    Pairing, certificate pin distribution and firewalling are installer tasks.
    This function never binds a wildcard address or serves plaintext HTTP.
    """
    address = ipaddress.IPv4Address(bind_host)
    if address.is_unspecified or address.is_multicast or not (address.is_private or address.is_loopback):
        raise ValueError("Indirizzo provisioner non locale")
    if not 0 <= port <= 65535:
        raise ValueError("Porta provisioner non valida")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(str(certificate), str(private_key))
    server = ThreadingHTTPServer((bind_host, port), make_handler(config, token, reload_pjsip, endpoint_exists, external_routes, control4_routes))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    return server
