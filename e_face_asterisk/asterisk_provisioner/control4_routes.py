"""Isolated Control4 tablet routes; never rewrites the existing 8290-8292 beta routes."""

from __future__ import annotations

import json
import re
import subprocess
import threading
from pathlib import Path

from .managed_config import _atomic_write
from .external_routes import reload_dialplan

_LOCK = threading.RLock()
_EXTENSION = re.compile(r"829[3-9]\Z")
_SIP_USER = re.compile(r"[A-Za-z0-9_.-]{3,64}\Z")
_INCLUDE = "#include /config/asterisk/eface/control4_routes.conf"
_PROXY = "control4-t3-ufficio-test"


def validate(routes: object) -> list[dict[str, str]]:
    if not isinstance(routes, list) or len(routes) > 7:
        raise ValueError("Massimo sette rotte tablet Control4")
    result = []
    seen: set[str] = set()
    for route in routes:
        if not isinstance(route, dict) or set(route) != {"extension", "sip_user"}:
            raise ValueError("Dati rotta Control4 incompleti")
        extension, sip_user = route["extension"], route["sip_user"]
        if not isinstance(extension, str) or not _EXTENSION.fullmatch(extension) or extension in seen:
            raise ValueError("Interno tablet non valido o duplicato")
        if not isinstance(sip_user, str) or not _SIP_USER.fullmatch(sip_user):
            raise ValueError("SIP User Name non valido")
        seen.add(extension)
        result.append({"extension": extension, "sip_user": sip_user})
    return sorted(result, key=lambda item: item["extension"])


def render(routes: object) -> str:
    lines = ["; Rotte tablet Control4 generate da e-Face.\n"]
    for route in validate(routes):
        lines.append(f"exten => {route['extension']},1,Dial(PJSIP/{route['sip_user']}@{_PROXY},40)\n")
    return "".join(lines)


def _cli(command: str) -> str:
    result = subprocess.run(["asterisk", "-rx", command], capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError("Verifica Asterisk non riuscita")
    return result.stdout


def proxy_exists() -> bool:
    return any(line.strip().startswith(f"Endpoint:  {_PROXY} ") for line in _cli(f"pjsip show endpoint {_PROXY}").splitlines())


def route_matches(extension: str, sip_user: str) -> bool:
    result = subprocess.run(["asterisk", "-rx", f"dialplan show {extension}@eface-test"], capture_output=True, text=True, timeout=10)
    return result.returncode == 0 and f"'{extension}' =>" in result.stdout and f"PJSIP/{sip_user}@{_PROXY}" in result.stdout


def extension_exists(extension: str) -> bool:
    result = subprocess.run(["asterisk", "-rx", f"dialplan show {extension}@eface-test"], capture_output=True, text=True, timeout=10)
    if result.returncode and "There is no existence" not in result.stdout:
        raise RuntimeError("Verifica interno Control4 non riuscita")
    return f"'{extension}' =>" in result.stdout


class Control4Routes:
    def __init__(self, config_root: Path):
        self.directory = config_root / "eface"
        self.source = config_root / "custom" / "extensions.conf"
        self.state = self.directory / "control4_routes.json"
        self.generated = self.directory / "control4_routes.conf"
        self.backup = self.directory / "extensions.before-control4-routes.bak"

    def load(self) -> list[dict[str, str]]:
        try:
            return validate(json.loads(self.state.read_text(encoding="utf-8")))
        except FileNotFoundError:
            return []

    def ensure(self, reload=reload_dialplan) -> None:
        with _LOCK:
            self.directory.mkdir(parents=True, exist_ok=True)
            expected = render(self.load())
            if not self.generated.exists() or self.generated.read_text(encoding="utf-8") != expected:
                _atomic_write(self.generated, expected)
            current = self.source.read_text(encoding="utf-8")
            if _INCLUDE in current.splitlines():
                return
            if self.backup.exists():
                raise RuntimeError("Include Control4 rimosso dopo installazione")
            lines = current.splitlines(keepends=True)
            start = next((i for i, line in enumerate(lines) if line.strip() == "[eface-test]"), -1)
            if start < 0:
                raise RuntimeError("Contesto eface-test non trovato")
            end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
            _atomic_write(self.backup, current)
            lines.insert(end, _INCLUDE + "\n")
            try:
                _atomic_write(self.source, "".join(lines))
                reload()
            except Exception:
                _atomic_write(self.source, current)
                self.backup.unlink(missing_ok=True)
                raise

    def replace(self, routes: object, reload=reload_dialplan) -> list[dict[str, str]]:
        updated = validate(routes)
        with _LOCK:
            if updated and not proxy_exists():
                raise RuntimeError("Proxy SIP Control4 non presente in Asterisk")
            self.ensure(reload)
            previous = self.load()
            if updated == previous:
                return updated
            for route in updated:
                if route["extension"] not in {old["extension"] for old in previous} and extension_exists(route["extension"]):
                    raise ValueError("Interno già presente fuori da e-Face")
            try:
                _atomic_write(self.state, json.dumps(updated, ensure_ascii=False))
                _atomic_write(self.generated, render(updated))
                reload()
                if not all(route_matches(route["extension"], route["sip_user"]) for route in updated):
                    raise RuntimeError("Asterisk non vede le rotte Control4")
            except Exception:
                _atomic_write(self.state, json.dumps(previous, ensure_ascii=False))
                _atomic_write(self.generated, render(previous))
                reload()
                raise
            return updated
