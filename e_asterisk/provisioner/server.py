"""Local-only development API for the e-Face Asterisk provisioner."""

from __future__ import annotations

import hmac
import json
import os
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from managed_config import ManagedConfig

MAX_BODY = 4096
PHONE_PATH = re.compile(r"/v1/phones/([a-z][a-z0-9_-]{2,31})\Z")
CONFIG = ManagedConfig(Path("/config/asterisk/eface"))
INCLUDE = "#include /config/asterisk/eface/pjsip.conf"


def _include_ready() -> bool:
    try:
        return INCLUDE in Path("/etc/asterisk/pjsip.conf").read_text(encoding="utf-8")
    except OSError:
        return False


def _token() -> str:
    try:
        options = json.loads(Path("/data/options.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    value = options.get("eface_provision_token", "")
    return value if isinstance(value, str) and len(value) >= 32 else ""


def _asterisk(*args: str) -> str:
    result = subprocess.run(["asterisk", "-rx", " ".join(args)], capture_output=True, text=True, timeout=8, check=False)
    if result.returncode:
        raise RuntimeError("Asterisk CLI non disponibile")
    return result.stdout


def _reload() -> None:
    _asterisk("pjsip", "reload")


def _endpoint_exists(extension: str) -> bool:
    output = _asterisk("pjsip", "show", "endpoint", extension)
    return bool(re.search(rf"(?m)^\s*Endpoint:\s+{re.escape(extension)}(?:/|\s)", output))


class Handler(BaseHTTPRequestHandler):
    server_version = "e-Face-Provisioner"

    def log_message(self, format: str, *args: object) -> None:
        pass  # Never log URLs, credentials or request payloads.

    def _reply(self, status: int, value: dict) -> None:
        body = json.dumps(value, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        token = _token()
        value = self.headers.get("Authorization", "")
        if not token or not value.startswith("Bearer ") or not hmac.compare_digest(value[7:], token):
            self._reply(401, {"error": "unauthorized"})
            return False
        return True

    def _username(self) -> str | None:
        match = PHONE_PATH.fullmatch(self.path)
        if not match:
            self._reply(404, {"error": "not_found"})
            return None
        return match.group(1)

    def do_GET(self) -> None:
        if self.path != "/v1/health":
            self._reply(404, {"error": "not_found"})
            return
        try:
            _asterisk("core", "show", "uptime")
            ready = _include_ready() and bool(_token())
            self._reply(200 if ready else 503, {"ready": ready})
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            self._reply(503, {"ready": False})

    def do_PUT(self) -> None:
        if not self._authorized():
            return
        if not _include_ready():
            self._reply(503, {"error": "managed_include_missing"})
            return
        username = self._username()
        if username is None:
            return
        length = self.headers.get("Content-Length", "")
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json" or not length.isdigit() or not 1 <= int(length) <= MAX_BODY:
            self._reply(400, {"error": "invalid_request"})
            return
        try:
            payload = json.loads(self.rfile.read(int(length)))
            if not isinstance(payload, dict) or set(payload) != {"extension", "password", "name"}:
                raise ValueError("Campi non validi")
        except (ValueError, TypeError):
            self._reply(400, {"error": "invalid_phone"})
            return
        try:
            CONFIG.upsert(username, str(payload["extension"]), str(payload["password"]), str(payload["name"]), _reload, _endpoint_exists)
        except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError, TypeError, KeyError, json.JSONDecodeError):
            self._reply(503, {"error": "provisioning_failed"})
            return
        self._reply(200, {"extension": payload["extension"], "active": True})

    def do_DELETE(self) -> None:
        if not self._authorized():
            return
        if not _include_ready():
            self._reply(503, {"error": "managed_include_missing"})
            return
        username = self._username()
        if username is None:
            return
        try:
            removed = CONFIG.revoke(username, _reload, _endpoint_exists)
        except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError, KeyError, json.JSONDecodeError):
            self._reply(503, {"error": "revocation_failed"})
            return
        self._reply(200, {"removed": removed})


def main() -> None:
    CONFIG.reconcile_file()
    if not _token():
        raise SystemExit("e-Face provisioner disabled: unique token missing")
    host = os.environ.get("EFACE_PROVISION_BIND", "172.30.32.1")
    ThreadingHTTPServer((host, 8350), Handler).serve_forever()


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    main()
