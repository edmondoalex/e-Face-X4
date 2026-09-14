"""Persistent, isolated outbound routes for DoorBird external stations."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import subprocess
import threading
from pathlib import Path

from .managed_config import _atomic_write


_LOCK = threading.RLock()
_EXT = re.compile(r"82(?:0[2-9]|[1-8][0-9])\Z")
_PRIVATE = tuple(ipaddress.ip_network(net) for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
_INCLUDE = "#include /config/asterisk/eface/external_routes.conf"


def _validate(stations: list[dict]) -> list[dict]:
    if not isinstance(stations, list) or len(stations) > 7:
        raise ValueError("Massimo sette postazioni esterne aggiuntive")
    result = []
    used: set[str] = set()
    for item in stations:
        if not isinstance(item, dict) or set(item) != {"extension", "host"}:
            raise ValueError("Dati rotta SIP incompleti")
        extension = item["extension"]
        host = item["host"]
        if not isinstance(extension, str) or not _EXT.fullmatch(extension) or extension in used:
            raise ValueError("Interno SIP esterno non valido o duplicato")
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError("IP postazione non valido") from exc
        if address.version != 4 or not any(address in network for network in _PRIVATE):
            raise ValueError("IP postazione non privato")
        result.append({"extension": extension, "host": host})
        used.add(extension)
    return sorted(result, key=lambda item: item["extension"])


def _render(stations: list[dict]) -> str:
    lines = ["; Rotte postazioni esterne generate da e-Face.\n"]
    for station in _validate(stations):
        lines.append(f"exten => {station['extension']},1,Dial(PJSIP/doorbird-p2p-test/sip:{station['host']}:5060,40)\n")
    return "".join(lines)


class ExternalRoutes:
    def __init__(self, config_root: Path):
        self.root = config_root
        self.directory = config_root / "eface"
        self.source = config_root / "custom" / "extensions.conf"
        self.state = self.directory / "external_stations.json"
        self.generated = self.directory / "external_routes.conf"
        self.backup = self.directory / "extensions.before-external-routes.bak"

    def load(self) -> list[dict]:
        try:
            value = json.loads(self.state.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        return _validate(value)

    def ensure(self, reload_dialplan=None) -> None:
        """Install one include inside eface-test, preserving a byte-exact backup."""
        with _LOCK:
            self.directory.mkdir(parents=True, exist_ok=True)
            expected = _render(self.load())
            if not self.generated.exists() or self.generated.read_text(encoding="utf-8") != expected:
                _atomic_write(self.generated, expected)
            current = self.source.read_text(encoding="utf-8")
            if _INCLUDE in current.splitlines():
                return
            if self.backup.exists():
                raise RuntimeError("Include esterno rimosso dopo l'installazione")
            lines = current.splitlines(keepends=True)
            start = next((i for i, line in enumerate(lines) if line.strip() == "[eface-test]"), -1)
            if start < 0:
                raise RuntimeError("Contesto eface-test non trovato")
            end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
            _atomic_write(self.backup, current)
            lines.insert(end, _INCLUDE + "\n")
            try:
                _atomic_write(self.source, "".join(lines))
                if reload_dialplan:
                    reload_dialplan()
            except Exception:
                _atomic_write(self.source, current)
                self.backup.unlink(missing_ok=True)
                raise

    def replace(self, stations: list[dict], reload_dialplan, extension_exists) -> None:
        updated = _validate(stations)
        with _LOCK:
            self.ensure(reload_dialplan)
            previous = self.load()
            if updated == previous:
                return
            existing = {station["extension"] for station in previous}
            for station in updated:
                if station["extension"] not in existing and extension_exists(station["extension"]):
                    raise ValueError("Interno già presente fuori da e-Face")
            old_state = json.dumps(previous, ensure_ascii=False)
            old_generated = _render(previous)
            try:
                _atomic_write(self.state, json.dumps(updated, ensure_ascii=False))
                _atomic_write(self.generated, _render(updated))
                reload_dialplan()
                for station in updated:
                    if not route_matches(station["extension"], station["host"]):
                        raise RuntimeError("Asterisk non vede la rotta esterna corretta")
            except Exception:
                _atomic_write(self.state, old_state)
                _atomic_write(self.generated, old_generated)
                reload_dialplan()
                raise


def reload_dialplan() -> None:
    result = subprocess.run(["asterisk", "-rx", "dialplan reload"], capture_output=True, text=True, timeout=15)
    if result.returncode or "No such command" in result.stdout + result.stderr:
        raise RuntimeError("Ricarica dialplan fallita")


def extension_exists(extension: str) -> bool:
    if not _EXT.fullmatch(extension):
        raise ValueError("Interno esterno non valido")
    result = subprocess.run(["asterisk", "-rx", f"dialplan show {extension}@eface-test"],
                            capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise RuntimeError("Verifica dialplan fallita")
    return f"'{extension}' =>" in result.stdout


def route_matches(extension: str, host: str) -> bool:
    if not _EXT.fullmatch(extension):
        raise ValueError("Interno esterno non valido")
    result = subprocess.run(["asterisk", "-rx", f"dialplan show {extension}@eface-test"],
                            capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise RuntimeError("Verifica rotta SIP fallita")
    return f"'{extension}' =>" in result.stdout and f"PJSIP/doorbird-p2p-test/sip:{host}:5060" in result.stdout
