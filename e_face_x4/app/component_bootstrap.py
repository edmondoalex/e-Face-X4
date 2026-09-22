"""Load the bundled Home Assistant companion after a fresh app install."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DOMAIN = "eface_alexa"
SUPERVISOR = "http://supervisor"
MARKER = Path(os.environ.get("EFACE_DATA", "/data")) / ".eface_alexa_core_restart"
MANIFEST = Path(os.environ.get("EFACE_HA_CONFIG_ROOT", "/homeassistant")) / "custom_components/eface_alexa/manifest.json"


def _request(path: str, token: str, method: str = "GET") -> tuple[int, bytes]:
    request = Request(
        f"{SUPERVISOR}{path}",
        method=method,
        headers={"Authorization": f"Bearer {token}"},
    )
    with urlopen(request, timeout=15) as response:
        return response.status, response.read()


def _component_version() -> str:
    try:
        return str(json.loads(MANIFEST.read_text(encoding="utf-8")).get("version") or "unknown")
    except (OSError, ValueError):
        return "unknown"


def _service_loaded(token: str) -> bool:
    status, payload = _request("/core/api/services", token)
    if status != 200:
        return False
    services = json.loads(payload)
    return any(item.get("domain") == DOMAIN for item in services if isinstance(item, dict))


def main() -> None:
    token = str(os.environ.get("SUPERVISOR_TOKEN") or "").strip()
    if not token or not MANIFEST.is_file():
        return
    version = _component_version()
    try:
        if _service_loaded(token):
            return
    except (HTTPError, URLError, TimeoutError, ValueError):
        return
    try:
        if MARKER.read_text(encoding="utf-8").strip() == version:
            return
    except OSError:
        pass
    time.sleep(10)
    try:
        status, _ = _request("/core/api/services/homeassistant/restart", token, "POST")
        if status in {200, 201}:
            MARKER.parent.mkdir(parents=True, exist_ok=True)
            MARKER.write_text(version, encoding="utf-8")
            print("[e-Face] Riavvio Home Assistant Core richiesto una sola volta per caricare il componente Alexa.", flush=True)
    except (HTTPError, URLError, TimeoutError):
        print("[e-Face] Riavvio automatico non riuscito; riavviare Home Assistant Core manualmente.", flush=True)


if __name__ == "__main__":
    main()
